from fastapi import FastAPI
from pydantic import BaseModel
from gmaps import scrape_google_maps, save_results
from pagesjaunes import scrape_pages_jaunes, save_pj_results

app = FastAPI()

class SearchRequest(BaseModel):
    query: str
    location: str
    max_results: int = 20

@app.post("/scrape/googlemaps")
def scrape_gmaps(request: SearchRequest):
    results = scrape_google_maps(
        query=request.query,
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
