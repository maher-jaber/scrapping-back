from playwright.sync_api import sync_playwright

def scrape_pagesjaunes_sync(secteur=None, ville=None):
    results = []
    base_url = "https://www.pagesjaunes.fr/recherche"
    query = secteur or ""
    location = ville or ""

    search_url = f"{base_url}?quoiqui={query}&ou={location}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(search_url, timeout=60000)
        page.wait_for_selector(".bi-bloc", timeout=30000)

        blocs = page.query_selector_all(".bi-bloc")

        for bloc in blocs:
            name_el = bloc.query_selector(".denomination-links a")
            name = name_el.inner_text() if name_el else None

            phone_el = bloc.query_selector(".num-contact .coord-numero")
            phone_raw = phone_el.inner_text() if phone_el else None

            city_el = bloc.query_selector(".zone-commune")
            city = city_el.inner_text() if city_el else None

            if name:
                results.append({
                    "nom": name.strip(),
                    "telephone": phone_raw.strip() if phone_raw else None,
                    "ville": city.strip() if city else None,
                    "source": "pagesjaunes.fr"
                })

        browser.close()
    return results
