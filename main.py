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


app = FastAPI()

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

@app.post("/scrape/googlemaps")
def scrape_gmaps(request: SearchRequest):
    results = scrape_by_label(
        label=request.query,
        location=request.location,
        max_results=request.max_results
    )
    if not results:
        return {"status": "error", "message": "Aucun résultat trouvé"}
    
    file_path = save_results(results, request.query, request.location)
    return {
        "status": "success",
        "results": results,
        "saved_file": file_path
    }

@app.post("/scrape/pagesjaunes")
def scrape_pj(request: SearchRequest):
    results = scrape_pages_jaunes(
        query=request.query,
        location=request.location,
        max_results=request.max_results
    )
    if not results:
        return {"status": "error", "message": "Aucun résultat trouvé"}
    
    file_path = save_pj_results(results, request.query, request.location)
    return {
        "status": "success",
        "results": results,
        "saved_file": file_path
    }


@app.get("/historique/list")
def list_historique():
    os.makedirs(DATA_DIR, exist_ok=True)
    files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    files.sort(key=os.path.getmtime, reverse=True)

    historique = []
    for f in files:
        mtime = os.path.getmtime(f)
        historique.append({
            "filename": os.path.basename(f),
            "path": f,
            "created": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "mtime": mtime  # utile côté front si besoin
        })
    return JSONResponse(content={"files": historique})

@app.get("/historique/{filename}")
def get_historique_file(filename: str):
    # Sécurité simple : pas de sous-dossiers
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")
    full_path = os.path.join(DATA_DIR, filename)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    with open(full_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Normalise la réponse : {"results": [ ... ]}
    return JSONResponse(content={"results": data})