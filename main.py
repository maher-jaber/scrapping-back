from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from gmaps import scrape_google_maps, scrape_by_label, save_results
from pagesjaunes import scrape_pages_jaunes, save_pj_results
import os
import glob
from fastapi.responses import JSONResponse
from datetime import datetime
import json
import mysql.connector
import hashlib
from fastapi import Query
from fastapi import Query as FQuery 
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import timedelta



security = HTTPBasic()


SECRET_KEY = "supersecretkey"  # change en secret fort
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")



db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="scrapping_db"
)
cursor = db.cursor(dictionary=True)


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

DATA_DIR = "data"
# --- CORS ---
origins = [
    "*",
    "http://localhost:8000",  # Ton front Symfony
    "http://127.0.0.1:8000",  # Variante localhost
    # Tu peux ajouter d'autres domaines si besoin
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],   # GET, POST, etc.
    allow_headers=["*"],   # Autorise tous les headers
)
# --- /CORS ---

class SearchRequest(BaseModel):
    query: str
    location: str
    max_results: int = 20




# --- créer le token ---
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- vérifier token ---
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

# --- endpoint login ---
@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Ici tu peux vérifier en DB
    if form_data.username == "admin" and form_data.password == "admin":
        access_token = create_access_token({"sub": form_data.username}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Nom utilisateur ou mot de passe incorrect")



@app.post("/scrape/googlemaps")
def scrape_gmaps(request: SearchRequest, user: str = Depends(get_current_user)):
    results = scrape_by_label(
        label=request.query,
        location=request.location,
        max_results=request.max_results
    )
    if not results:
        return {"status": "error", "message": "Aucun résultat trouvé"}
    
    normalized = [normalize_result(r) for r in results]
    
    saved = save_to_db(normalized, request.query, request.location, source="gmaps")
    return {
        "status": "success",
        **saved
    }

@app.post("/scrape/pagesjaunes")
def scrape_pj(request: SearchRequest, user: str = Depends(get_current_user)):
    results = scrape_pages_jaunes(
        query=request.query,
        location=request.location,
        max_results=request.max_results
    )
    if not results:
        return {"status": "error", "message": "Aucun résultat trouvé"}
    
    normalized = [normalize_result(r) for r in results]
    
    saved = save_to_db(normalized, request.query, request.location, source="pagesjaunes")
    return {
        "status": "success",
        **saved
    }






@app.get("/historique/all")
def list_all_historique( user: str = Depends(get_current_user)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT h.id AS history_id, h.scraped_at, h.query, h.location, h.source,
               d.id AS data_id, d.name, d.address, d.phone, d.website, d.plus_code, 
               d.note, d.horaires
        FROM scrape_history h
        JOIN scraped_data d ON h.scraped_data_id = d.id
        ORDER BY h.scraped_at DESC
    """)
    rows = cursor.fetchall()
    return {"historique": rows}


@app.get("/historique")
def list_historique_paginated(
    page: int = FQuery(1, ge=1),
    per_page: int = FQuery(10, ge=1),
    query: str = FQuery(None),
    location: str = FQuery(None),
    source: str = FQuery(None),
    date_from: str = FQuery(None),  # format attendu: yyyy-mm-dd
    date_to: str = FQuery(None), 
    user: str = Depends(get_current_user)
):
    offset = (page - 1) * per_page
    cursor = db.cursor(dictionary=True)

    # Construction dynamique du WHERE
    filters = []
    params = []

    if query:
        filters.append("h.query LIKE %s")
        params.append(f"%{query}%")
    if location:
        filters.append("h.location LIKE %s")
        params.append(f"%{location}%")
    if source:
        filters.append("h.source LIKE %s")
        params.append(f"%{source}%")

    # Filtre date
    if date_from and date_to:
        filters.append("h.scraped_at BETWEEN %s AND %s")
        params.append(f"{date_from} 00:00:00")
        params.append(f"{date_to} 23:59:59")
    elif date_from:
        filters.append("h.scraped_at >= %s")
        params.append(f"{date_from} 00:00:00")
    elif date_to:
        filters.append("h.scraped_at <= %s")
        params.append(f"{date_to} 23:59:59")

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    # Total entries pour pagination
    cursor.execute(f"SELECT COUNT(*) AS total FROM scrape_history h {where_clause}", params)
    total = cursor.fetchone()['total']

    # Récupère uniquement la page demandée
    cursor.execute(f"""
        SELECT h.id AS history_id, h.scraped_at, h.query, h.location, h.source,
               d.id AS data_id, d.name, d.address, d.phone, d.website, d.plus_code, 
               d.note, d.horaires
        FROM scrape_history h
        JOIN scraped_data d ON h.scraped_data_id = d.id
        {where_clause}
        ORDER BY h.scraped_at DESC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    rows = cursor.fetchall()

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "historique": rows
    }


def save_to_db(results, query, location, source="gmaps"):
    cursor = db.cursor(dictionary=True)
    inserted_ids = []
    already_scraped_ids = []
    full_results = []  # <-- Ici on va stocker les enregistrements complets
     
    for r in results:
        name = r.get("name")
        address = r.get("address")
        phone = r.get("phone")
        website = r.get("website")
        plus_code = r.get("plus_code")
        note = r.get("note", None)
        horaires = r.get("horaires", "")

        unique_hash = hashlib.md5(f"{name}{address}{phone}".encode("utf-8")).hexdigest()

        # Vérifier si déjà en base AVANT insert
        cursor.execute("SELECT * FROM scraped_data WHERE unique_hash=%s", (unique_hash,))
        existing = cursor.fetchone()

        if existing:
            scraped_data_id = existing["id"]
            already_scraped_ids.append(scraped_data_id)

            # ✅ on met à jour already_scrapped=True
            cursor.execute("UPDATE scraped_data SET already_scrapped=TRUE WHERE id=%s", (scraped_data_id,))
            db.commit()

            existing["already_scrapped"] = True
            full_results.append(existing)
        else:
            cursor.execute("""
                INSERT INTO scraped_data (name, address, phone, website, plus_code, note, horaires, unique_hash, already_scrapped,scraped_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, NOW())
            """, (name, address, phone, website, plus_code, note, horaires, unique_hash))
            scraped_data_id = cursor.lastrowid
            inserted_ids.append(scraped_data_id)

            # Récupérer le record complet inséré
            cursor.execute("SELECT * FROM scraped_data WHERE id=%s", (scraped_data_id,))
            new_record = cursor.fetchone()
            new_record["already_scrapped"] = False
            full_results.append(new_record)

        # Historique (toujours tracé, même si déjà existant)
        cursor.execute("""
            INSERT INTO scrape_history (scraped_data_id, source, query, location)
            VALUES (%s, %s, %s, %s)
        """, (scraped_data_id, source, query, location))

    db.commit()
    return {
        "results": full_results,
        "new_ids": inserted_ids,
        "already_scraped_ids": already_scraped_ids
    }



def normalize_result(r: dict) -> dict:
    """Convertit les clés FR -> EN pour correspondre à la DB"""
    return {
        "name": r.get("Nom"),
        "address": r.get("Adresse"),
        "phone": r.get("Téléphone"),
        "website": r.get("Site Web"),
        "note": r.get("Note"),
        "reviews": r.get("Nombre d'avis"),
        "scraped_at": r.get("Heure de scraping"),
        "plus_code": r.get("Plus Code", None),
        "horaires": r.get("Horaires", "")
    }
    
    
    
def get_current_user_docs(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = "admin"
    correct_password = "admin"
    if credentials.username != correct_username or credentials.password != correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Accès refusé",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# Route protégée pour Swagger UI
@app.get("/secure-docs", include_in_schema=False)
def custom_swagger_ui(user: str = Depends(get_current_user_docs)):
    return get_swagger_ui_html(
        openapi_url="/secure-openapi.json",
        title="Docs sécurisées"
    )


# Route protégée pour OpenAPI JSON
@app.get("/secure-openapi.json", include_in_schema=False)
def custom_openapi(user: str = Depends(get_current_user_docs)):
    return app.openapi()


