from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from gmaps import scrape_google_maps, scrape_by_label, save_results,gmaps_in_progress
from pagesjaunes import scrape_pages_jaunes, save_pj_results, pj_in_progress
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
from typing import Optional
from passlib.context import CryptContext
import asyncio


security = HTTPBasic()


SECRET_KEY = "altra-call@2025"  # change en secret fort
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

REFRESH_TOKEN_EXPIRE_DAYS = 7
refresh_tokens_store = {} 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    "http://localhost:4200",
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


class RegisterRequest(BaseModel):
    username: str
    password: str
    
    
    

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_user(username: str, password: str):
    hashed = hash_password(password)
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
        (username, hashed)
    )
    db.commit()
    print(f"✅ Utilisateur {username} créé")
    
    
# --- créer le token ---
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_tokens(username: str):
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_access_token(
        data={"sub": username}, 
        expires_delta=access_token_expires
    )
    refresh_token = create_access_token(
        data={"sub": username, "type": "refresh"}, 
        expires_delta=refresh_token_expires
    )

    # Sauvegarde côté serveur (DB idéalement)
    refresh_tokens_store[refresh_token] = username

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }



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
def login(form_data: OAuth2PasswordRequestForm = Depends(), device_info: str = Query(None)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (form_data.username,))
    user = cursor.fetchone()

    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Nom utilisateur ou mot de passe incorrect")

    # Création des tokens
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_access_token(
        data={"sub": user["username"], "type": "refresh"},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    refresh_token_expires = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Enregistrement dans user_tokens
    cursor.execute("""
        INSERT INTO user_tokens (user_id, refresh_token, expires_at, device_info)
        VALUES (%s, %s, %s, %s)
    """, (user["id"], refresh_token, refresh_token_expires, device_info))
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


# --- Endpoint Refresh ---
@app.post("/refresh")
def refresh_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token invalide")

        username = payload.get("sub")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=401, detail="Utilisateur inexistant")

        # Vérifie que le refresh token existe et n’est pas expiré
        cursor.execute("""
            SELECT * FROM user_tokens
            WHERE user_id=%s AND refresh_token=%s AND expires_at > NOW()
        """, (user["id"], token))
        token_entry = cursor.fetchone()

        if not token_entry:
            raise HTTPException(status_code=401, detail="Refresh token invalide ou expiré")

        # Nouveau access token
        new_access_token = create_access_token(
            {"sub": username},
            timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": new_access_token, "token_type": "bearer"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")



# --- Endpoint Logout (révocation) ---
@app.post("/logout")
def logout(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Utilisateur inexistant")

        # Supprime ce refresh token uniquement
        cursor.execute("""
            DELETE FROM user_tokens
            WHERE user_id=%s AND refresh_token=%s
        """, (user["id"], token))
        db.commit()
        return {"status": "logged_out"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")


@app.post("/register")
def register(user_data: RegisterRequest, current_user: str = Depends(get_current_user)):
    cursor = db.cursor(dictionary=True)

    # Vérifier si username existe déjà
    cursor.execute("SELECT id FROM users WHERE username=%s", (user_data.username,))
    existing = cursor.fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")

    # Hash du mot de passe
    hashed = hash_password(user_data.password)

    # Insert en DB
    cursor.execute(
        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
        (user_data.username, hashed)
    )
    db.commit()

    return {"status": "success", "message": f"Utilisateur {user_data.username} créé avec succès"}



@app.post("/scrape/googlemaps")
async def scrape_gmaps(request: SearchRequest, user: str = Depends(get_current_user)):
    # 1️⃣ Exécute le scraping dans un thread séparé pour ne pas bloquer
    results = await asyncio.to_thread(
        scrape_by_label,
        request.query,
        request.location,
        request.max_results,
        user
    )

    if not results:
        return {"status": "error", "message": "Aucun résultat trouvé"}

    # 2️⃣ Normalisation des résultats
    normalized = [normalize_result(r) for r in results]

    # 3️⃣ Sauvegarde en DB (également dans un thread séparé)
    saved = await asyncio.to_thread(
        save_to_db,
        normalized,
        request.query,
        request.location,
        "gmaps"
    )

    return {"status": "success", **saved}

@app.post("/scrape/pagesjaunes")
async def scrape_pj(request: SearchRequest, user: str = Depends(get_current_user)):
    results = await asyncio.to_thread(
        scrape_pages_jaunes,
        request.query,
        request.location,
        request.max_results,
        user
    )

    if not results:
        return {"status": "error", "message": "Aucun résultat trouvé"}

    normalized = [normalize_result(r) for r in results]

    saved = await asyncio.to_thread(
        save_to_db,
        normalized,
        request.query,
        request.location,
        "pagesjaunes"
    )

    return {"status": "success", **saved}


@app.get("/scrape/pagesjaunes/status")
def get_pj_status(user: str = Depends(get_current_user)):
    # Retourne la liste des entreprises en cours ou terminées pour l'utilisateur
    return {"in_progress": pj_in_progress.get(user, [])}


@app.get("/scrape/googlemaps/status")
def get_pj_status(user: str = Depends(get_current_user)):
    # Retourne la liste des entreprises en cours ou terminées pour l'utilisateur
    return {"in_progress": gmaps_in_progress.get(user, [])}

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

@app.get("/scraped_data")
def list_scraped_data(
    page: int = FQuery(1, ge=1),
    per_page: int = FQuery(10, ge=1),
    name: str = FQuery(None),
    address: str = FQuery(None),
    phone: str = FQuery(None),
    website: str = FQuery(None),
    source: str = FQuery(None),
    date_from: str = FQuery(None),  # yyyy-mm-dd
    date_to: str = FQuery(None),
    user: str = Depends(get_current_user)
):
    offset = (page - 1) * per_page
    cursor = db.cursor(dictionary=True)

    filters = []
    params = []

    if name:
        filters.append("name LIKE %s")
        params.append(f"%{name}%")
    if address:
        filters.append("address LIKE %s")
        params.append(f"%{address}%")
    if phone:
        filters.append("phone LIKE %s")
        params.append(f"%{phone}%")
    if website:
        filters.append("website LIKE %s")
        params.append(f"%{website}%")
    if source:
        filters.append("source LIKE %s")
        params.append(f"%{source}%")

    if date_from and date_to:
        filters.append("scraped_at BETWEEN %s AND %s")
        params.append(f"{date_from} 00:00:00")
        params.append(f"{date_to} 23:59:59")
    elif date_from:
        filters.append("scraped_at >= %s")
        params.append(f"{date_from} 00:00:00")
    elif date_to:
        filters.append("scraped_at <= %s")
        params.append(f"{date_to} 23:59:59")

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    # Total entries
    cursor.execute(f"SELECT COUNT(*) AS total FROM scraped_data {where_clause}", params)
    total = cursor.fetchone()["total"]

    # Récupérer la page
    cursor.execute(f"""
        SELECT * 
        FROM scraped_data
        {where_clause}
        ORDER BY scraped_at DESC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    rows = cursor.fetchall()

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "data": rows
    }


@app.get("/historique")
def list_historique_paginated(
    page: int = FQuery(1, ge=1),
    per_page: int = FQuery(10, ge=1),
    query: str = FQuery(None),
    location: str = FQuery(None),
    source: str = FQuery(None),
    date_from: str = FQuery(None),
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

    # 1️⃣ Total distinct (name, phone, address) pour pagination
    cursor.execute(f"""
        SELECT COUNT(*) AS total
        FROM (
            SELECT d.name, d.phone, d.address
            FROM scrape_history h
            JOIN scraped_data d ON h.scraped_data_id = d.id
            {where_clause}
            GROUP BY d.name, d.phone, d.address
        ) AS sub
    """, params)
    total = cursor.fetchone()["total"]

    # 2️⃣ Récupère uniquement la dernière entrée par combinaison (name, phone, address)
    cursor.execute(f"""
        SELECT h.id AS history_id, h.scraped_at, h.query, h.location, h.source,
               d.id AS data_id, d.name, d.phone, d.address, d.website, d.plus_code, 
               d.note, d.horaires
        FROM scrape_history h
        JOIN scraped_data d ON h.scraped_data_id = d.id
        INNER JOIN (
            SELECT d.name, d.phone, d.address, MAX(h.scraped_at) AS max_date
            FROM scrape_history h
            JOIN scraped_data d ON h.scraped_data_id = d.id
            {where_clause}
            GROUP BY d.name, d.phone, d.address
        ) latest 
            ON d.name = latest.name 
           AND d.phone = latest.phone 
           AND d.address = latest.address
           AND h.scraped_at = latest.max_date
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


