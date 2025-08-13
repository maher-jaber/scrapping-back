from fastapi import FastAPI, Query, HTTPException
from typing import List, Optional
import traceback

app = FastAPI(title="Scraping API France")

@app.get("/scrape")
async def scrape(
    secteur: Optional[str] = None,
    ville: Optional[str] = None,
    sources: List[str] = Query(...)
):
    try:
        results = []
        if "societe" in sources:
            from scrapers import societe_scraper
            # Comme c’est synchrone, on peut faire directement l’appel
            results.extend(societe_scraper.scrape_societe_com(secteur=secteur, ville=ville))

        # Optionnel: ajouter autres sources

        return {"count": len(results), "results": results}

    except Exception:
        tb = "".join(traceback.format_exception(*sys.exc_info()))
        print("Exception dans /scrape:", tb)
        raise HTTPException(status_code=500, detail=tb)
