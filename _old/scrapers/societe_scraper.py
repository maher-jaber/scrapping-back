import requests
from bs4 import BeautifulSoup

def scrape_societe_com(secteur=None, ville=None):
    results = []
    base_url = "https://www.societe.com/cgi-bin/search"

    params = {}
    if secteur:
        params['recherche'] = secteur
    if ville:
        params['cp'] = ville  # ou autre paramètre

    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0 Safari/537.36"
    }
    response = requests.get(base_url, params=params, headers=headers)
    print("URL appelée:", response.url)
    print("Status:", response.status_code)
    print("HTML extrait (début):", response.text[:1000])

    soup = BeautifulSoup(response.text, 'html.parser')

    # Mets ici le sélecteur exact que tu trouves dans la page inspectée
    entreprises = soup.select("div.result-item")  

    print(f"{len(entreprises)} entreprises trouvées")

    for ent in entreprises:
        nom_el = ent.select_one(".company-name")
        tel_el = ent.select_one(".phone-number")
        ville_el = ent.select_one(".company-city")

        nom = nom_el.get_text(strip=True) if nom_el else None
        tel = tel_el.get_text(strip=True) if tel_el else None
        ville_res = ville_el.get_text(strip=True) if ville_el else None

        if nom:
            results.append({
                "nom": nom,
                "telephone": tel,
                "ville": ville_res,
                "source": "societe.com"
            })

    return results
