import time
import random
import urllib.parse
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging
from datetime import datetime
import sys
import json
import os



scraping_active_gmaps = {
    "gmaps": {}
}

gmaps_in_progress = {}
# ==== Chargement fichier NAF enrichi ====
with open("naf-activity-gmaps.json", "r", encoding="utf-8") as f:
    naf_keywords_map = json.load(f)

def get_keywords_for_label(label):
    """Retourne la liste des mots-clés Google Maps pour un label NAF donné."""
    for entry in naf_keywords_map:
        if entry["label"].lower() == label.lower():
            return entry["gmaps_keywords"]
    return [label]  # fallback

# ==== Logging ====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('google_maps_scraper.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger('WDM').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15'
]

def configure_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--output=/dev/null")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=390,844")

    service = Service(
        ChromeDriverManager().install(),
        service_args=['--disable-logging', '--silent']
    )

    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
            window.chrome = {runtime: {}};
        '''
    })
    return driver

def ___configure_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=390,844")
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

    service = Service("/usr/local/bin/chromedriver")  # chemin fixe sous Docker/Linux
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Anti-détection
    driver.execute_cdp_cmd(
        'Page.addScriptToEvaluateOnNewDocument',
        {'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'}
    )

    return driver

def wait_for_results(driver):
    try:
        WebDriverWait(driver, 20).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[aria-label^="Résultats pour"]')),
                EC.presence_of_element_located((By.CSS_SELECTOR, '[role="article"], div.Nv2PK.THOPZb.CpccDe'))
            )
        )
        return True
    except:
        logger.error("Timeout en attente des résultats")
        return False

def extract_all_businesses(driver):
    """Extracts all business cards from the results page, handling both formats."""
    try:
        # First try the standard container
        container = driver.find_element(By.CSS_SELECTOR, 'div[aria-label^="Résultats pour"]')
        
        # Try both types of business cards
        business_cards = container.find_elements(
            By.CSS_SELECTOR, 
            '[role="article"], div.Nv2PK.THOPZb.CpccDe, div.Nv2PK.tH5CWc.THOPZb'
        )
        
        # For dental cabinets, sometimes there's an additional wrapper
        if not business_cards:
            business_cards = container.find_elements(
                By.CSS_SELECTOR, 
                'div.Nv2PK.tH5CWc.THOPZb > a.hfpxzc'
            )
        
        return business_cards
    
    except Exception as e:
        logger.warning(f"Error finding business cards: {str(e)}")
        return []

def scroll_to_load_results(driver, max_results):
    try:
        container = driver.find_element(By.CSS_SELECTOR, 'div[aria-label^="Résultats pour"]')
        last_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 15  # Augmenté

        while scroll_attempts < max_scroll_attempts:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
            time.sleep(random.uniform(1.5, 3.0))
            
            items = extract_all_businesses(driver)
            current_count = len(items)
            
            if current_count >= max_results:
                break
                
            if current_count == last_count:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_count = current_count
                
            # Faire un scroll supplémentaire pour déclencher le chargement
            driver.execute_script("window.scrollBy(0, 500)")
            time.sleep(0.5)
            
    except Exception as e:
        logger.warning(f"Erreur pendant le scroll: {str(e)}")

def extract_business_details(driver):
    """Extracts business details, handling both café and dental cabinet formats."""
    details = {}
    
    # Name extraction
    try:
        name = driver.find_element(
            By.CSS_SELECTOR, 
            'h1.DUwDvf, div.qBF1Pd.fontHeadlineSmall, h1.fontHeadlineLarge'
        ).text.strip()
        details["Nom"] = name
    except:
        pass
    
    # Address extraction
    try:
        address = driver.find_element(
            By.CSS_SELECTOR, 
            'button[data-item-id="address"] div.Io6YTe, '
            'div.W4Efsd > span:nth-child(2), '
            'div.W4Efsd > span > span:nth-child(3)'
        ).text.strip()
        details["Adresse"] = address
    except:
        pass
    
    # Phone extraction
    try:
        phone = driver.find_element(
            By.CSS_SELECTOR, 
            'button[data-item-id^="phone:"] div.Io6YTe, '
            'span.UsdlK, '
            'div[aria-label*="Téléphone"]'
        ).text.strip()
        details["Téléphone"] = phone
    except:
        pass
    
    # Website extraction
    try:
        website = driver.find_element(
            By.CSS_SELECTOR, 
            'a[data-item-id="authority"] div.Io6YTe, '
            'a.lcr4fd.S9kvJb div.R8c4Qb'
        ).text.strip()
        details["Site Web"] = website
    except:
        pass
    
    # Rating extraction
    try:
        rating = driver.find_element(
            By.CSS_SELECTOR, 
            'div.F7nice span[aria-hidden="true"], '
            'span.MW4etd'
        ).text.strip()
        details["Note"] = rating
    except:
        pass
    
    # Review count extraction
    try:
        reviews = driver.find_element(
            By.CSS_SELECTOR, 
            'div.F7nice span[aria-label*="avis"], '
            'span.UY7F9'
        ).text.strip()
        details["Nombre d'avis"] = reviews
    except:
        pass
    
    # Business type extraction
    try:
        business_type = driver.find_element(
            By.CSS_SELECTOR, 
            'div.W4Efsd > span > span:first-child, '
            'div.W4Efsd > span:first-child > span:first-child'
        ).text.strip()
        details["Type"] = business_type
    except:
        pass
    
    # Opening hours extraction
    try:
        hours = driver.find_element(
            By.CSS_SELECTOR, 
            'div.W4Efsd > span > span > span, '
            'div[aria-label*="Heures"]'
        ).text.strip()
        details["Horaires"] = hours
    except:
        pass
    
    details["Heure de scraping"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return details

def close_details_panel(driver):
    try:
        back_btn = driver.find_elements(By.CSS_SELECTOR, 'button[aria-label="Retour"]')
        if back_btn:
            back_btn[0].click()
            logger.info("Retour à la liste (mobile).")
            return True
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        logger.info("Fermeture via ESC.")
        return True
    except Exception as e:
        logger.warning(f"Impossible de fermer la fiche : {e}")
        return False

def __scrape_google_maps(query, location, max_results, user=None):
    driver = None
    try:
        driver = configure_driver()
        encoded_query = urllib.parse.quote_plus(query)
        encoded_location = urllib.parse.quote_plus(location)
        url = f"https://www.google.com/maps/search/{encoded_query}+{encoded_location}+France"
        logger.info(f"Recherche: {query} à {location}")
        driver.get(url)

        time.sleep(random.uniform(3, 5))
        if not wait_for_results(driver):
            return []

        # Charger plus de résultats que nécessaire car certains ne seront pas cliquables
        scroll_to_load_results(driver, max_results * 2)  # Charger 2x plus que nécessaire

        results = []
        seen_names = set()
        idx = 0
        max_attempts = max_results * 2  # Donner plus de chances

        while len(results) < max_results and idx < max_attempts:
            try:
                items = extract_all_businesses(driver)
                if idx >= len(items):
                    logger.warning(f"Index {idx} dépasse le nombre d'items ({len(items)})")
                    break

                item = items[idx]
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", item)
                time.sleep(random.uniform(0.8, 1.5))
                
                try:
                    item.click()
                except:
                    # Essayer de cliquer via JavaScript si le click normal échoue
                    driver.execute_script("arguments[0].click();", item)

                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.DUwDvf, h1.fontHeadlineLarge'))
                )
                time.sleep(random.uniform(1.0, 2.0))

                business_data = extract_business_details(driver)

                if business_data.get('Nom') and business_data['Nom'] not in seen_names:
                    seen_names.add(business_data['Nom'])
                    results.append(business_data)
                    logger.info(f"{len(results)}/{max_results}: {business_data['Nom']}")
                                        # --- Mise à jour de la progression ---
                    if user:
                        if user not in gmaps_in_progress or not isinstance(gmaps_in_progress[user], dict):
                            gmaps_in_progress[user] = {
                                "name": business_data["Nom"],
                                "phone": business_data.get("Téléphone"),
                                "address": business_data.get("Adresse"),
                                "status": "en cours",
                                "current_index": 0,
                                "total": max_results
                            }
                        gmaps_in_progress[user]["name"] = business_data["Nom"]
                        gmaps_in_progress[user]["phone"] = business_data.get("Téléphone")
                        gmaps_in_progress[user]["address"] = business_data.get("Adresse")
                        gmaps_in_progress[user]["current_index"] = len(results)

                if not close_details_panel(driver):
                    # Si on ne peut pas fermer, on recharge la page
                    logger.warning("Rechargement de la page après échec de fermeture")
                    driver.get(url)
                    time.sleep(3)
                    scroll_to_load_results(driver, max_results * 2)
                    idx = 0  # Réinitialiser l'index après rechargement
                    continue

                time.sleep(random.uniform(0.5, 1.2))

            except Exception as e:
                logger.error(f"Erreur sur l'élément {idx+1}: {str(e)}")
                # Essayer de continuer malgré l'erreur
            finally:
                idx += 1
                
        # --- Fin du scraping ---
        if user:
            if user not in gmaps_in_progress:
                gmaps_in_progress[user] = {
                    "name": None,
                    "phone": None,
                    "address": None,
                    "status": "terminé",
                    "current_index": len(results),
                    "total": max_results
                }
            else:
                gmaps_in_progress[user]["status"] = "terminé"
                
        return results[:max_results]  # Au cas où on aurait dépassé

    except Exception as e:
        logger.error(f"Erreur majeure: {str(e)}", exc_info=True)
        return []
    finally:
        if driver:
            driver.quit()


# ==== Scraping multi-requêtes à partir d'un label NAF ====
def ___scrape_by_label(label, location, max_results, user=None):
    keywords = get_keywords_for_label(label)
    all_results = []
    seen_names = set()
    if user:
       gmaps_in_progress.clear()
    
    for kw in keywords:
        logger.info(f"--- Recherche pour mot-clé: {kw} ---")
        results = scrape_google_maps(kw, location, max_results - len(all_results), user=user)
        for r in results:
            if r['Nom'] not in seen_names:
                seen_names.add(r['Nom'])
                all_results.append(r)
                if len(all_results) >= max_results:
                    break  # on sort juste de la boucle du mot-clé
        if len(all_results) >= max_results:
            break  # on sort si le quota global est atteint
    # Mise à jour finale
    if user:
        if user not in gmaps_in_progress:
            gmaps_in_progress[user] = {"status": "terminé", "current_index": len(all_results), "total": max_results}
        else:
            gmaps_in_progress[user]["status"] = "terminé"
            
    gmaps_in_progress.clear()        
    
    return all_results


def scrape_label_fusion(label, location, max_results, user=None):
    # Initialiser l'état pour cet utilisateur
    if user:
        scraping_active_gmaps["gmaps"][user] = True
    
    keywords = get_keywords_for_label(label)
    results = []
    seen_names = set()
    if user:
        gmaps_in_progress.clear()

    try:
        for kw in keywords:
            driver = configure_driver()
            try:
                encoded_query = urllib.parse.quote_plus(kw)
                encoded_location = urllib.parse.quote_plus(location)
                url = f"https://www.google.com/maps/search/{encoded_query}+{encoded_location}+France"
                driver.get(url)
                time.sleep(random.uniform(3, 5))
                
                if not wait_for_results(driver):
                    continue

                scroll_to_load_results(driver, max_results * 2)
                idx = 0
                max_attempts = max_results * 2

                while len(results) < max_results and idx < max_attempts:
                    # Vérifier régulièrement si on doit arrêter
                    if user and not scraping_active_gmaps["gmaps"].get(user, True):
                        print(f"🛑 Scrapping arrêté par l'utilisateur {user}")
                        return results[:max_results]

                    items = extract_all_businesses(driver)
                    if idx >= len(items):
                        break

                    item = items[idx]
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", item)
                    time.sleep(random.uniform(0.8, 1.5))

                    try:
                        item.click()
                    except:
                        driver.execute_script("arguments[0].click();", item)

                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.DUwDvf, h1.fontHeadlineLarge'))
                    )
                    time.sleep(random.uniform(1.0, 2.0))

                    business_data = extract_business_details(driver)
                    if business_data.get("Nom") and business_data["Nom"] not in seen_names:
                        seen_names.add(business_data["Nom"])
                        results.append(business_data)
                        logger.info(f"{len(results)}/{max_results}: {business_data['Nom']}")
                        
                        # Vérifier à nouveau après l'ajout
                        if user and not scraping_active_gmaps["gmaps"].get(user, True):
                            print(f"🛑 Scrapping arrêté par l'utilisateur {user}")
                            return results[:max_results]
                            
                        # --- MAJ progression ---
                        if user:
                            gmaps_in_progress[user] = {
                                "current_index": len(results),
                                "total": max_results,
                                "name": business_data["Nom"],
                                "phone": business_data.get("Téléphone"),
                                "address": business_data.get("Adresse"),
                                "status": "en cours" if len(results) < max_results else "terminé"
                            }

                    if not close_details_panel(driver):
                        driver.get(url)
                        time.sleep(3)
                        scroll_to_load_results(driver, max_results * 2)
                        idx = 0
                        continue

                    time.sleep(random.uniform(0.5, 1.2))
                    idx += 1

            except Exception as e:
                logger.error(f"Erreur lors du scraping pour le mot-clé '{kw}': {e}")
            finally:
                # Fermer le driver pour ce mot-clé
                if driver:
                    driver.quit()

            if len(results) >= max_results:
                break

    finally:
        # Nettoyer l'état UNIQUEMENT à la fin de tout le scraping
        if user and user in scraping_active_gmaps["gmaps"]:
            del scraping_active_gmaps["gmaps"][user]

    # --- Fin ---
    if user:
        if user not in gmaps_in_progress:
            gmaps_in_progress[user] = {
                "current_index": len(results), 
                "total": max_results, 
                "status": "terminé"
            }
        else:
            gmaps_in_progress[user]["status"] = "terminé"

    return results[:max_results]


def save_results(results, query, location):
    """
    Sauvegarde les résultats dans un fichier JSON sous data/ avec horodatage.
    """
    # Crée le dossier data s'il n'existe pas
    os.makedirs("data", exist_ok=True)

    # Timestamp pour rendre le fichier unique
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Nom du fichier : query_location_timestamp.json
    safe_query = query.replace(" ", "_").replace("/", "-")
    safe_location = location.replace(" ", "_").replace("/", "-")
    filename = f"data/{safe_query}_{safe_location}_{timestamp}.json"

    # Sauvegarde en JSON lisible
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"Résultats sauvegardés dans {filename}")
    return filename