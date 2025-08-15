from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from gmaps import scrape_google_maps, scrape_by_label, save_results
from pagesjaunes import scrape_pages_jaunes, save_pj_results

app = FastAPI()

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
