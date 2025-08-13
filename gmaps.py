import time
import random
import urllib.parse
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging
from datetime import datetime
import sys

# Logging
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

def wait_for_results(driver):
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"], div.m6QErb.DxyBCb')))
        return True
    except:
        logger.error("Timeout en attente des résultats")
        return False

def extract_all_businesses(driver):
    return driver.find_elements(By.CSS_SELECTOR, '[role="article"], div.Nv2PK.THOPZb.CpccDe')

def scroll_to_load_results(driver, max_results):
    last_height = 0
    scroll_attempts = 0
    max_scroll_attempts = 15
    while len(extract_all_businesses(driver)) < max_results and scroll_attempts < max_scroll_attempts:
        driver.execute_script("""
            const sidebar = document.querySelector('div[role="feed"]');
            if (sidebar) sidebar.scrollTop = sidebar.scrollHeight;
        """)
        time.sleep(random.uniform(2, 3))
        current_height = driver.execute_script("""
            const sidebar = document.querySelector('div[role="feed"]');
            return sidebar ? sidebar.scrollHeight : 0;
        """)
        if current_height == last_height:
            scroll_attempts += 1
        else:
            scroll_attempts = 0
            last_height = current_height

def extract_business_details(driver):
    details = {}
    selectors = {
        "Nom": 'h1.DUwDvf',
        "Adresse": 'button[data-item-id="address"] div.Io6YTe',
        "Téléphone": 'button[data-item-id^="phone:"] div.Io6YTe',
        "Site Web": 'a[data-item-id="authority"] div.Io6YTe',
        "Menu": 'a[data-item-id="menu"] div.Io6YTe',
        "Commander": 'a[data-item-id^="action:4"] div.Io6YTe',
        "Plus Code": 'button[data-item-id="oloc"] div.Io6YTe',
        "Horaires": 'button[data-item-id="oh"] div.Io6YTe',
        "Note": 'div.F7nice span[aria-hidden="true"]',
        "Prix": 'span[aria-label*="€"], span[aria-label*="prix"]'
    }
    for key, selector in selectors.items():
        try:
            elem = driver.find_element(By.CSS_SELECTOR, selector)
            text = elem.text.strip()
            if text:
                details[key] = text
        except:
            continue
    details["Heure de scraping"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return details
def handle_panel_closure(driver, url):
    """Gère la fermeture du panneau détaillé avec plusieurs méthodes de secours"""
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Méthode 1: Bouton de fermeture standard
            try:
                close_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Fermer"], button[aria-label="Close"]'))
                )
                close_btn.click()
                time.sleep(1)
                return True
            except:
                pass

            # Méthode 2: Clic sur le fond (si overlay présent)
            try:
                overlay = driver.find_element(By.CSS_SELECTOR, 'div[role="dialog"] > div[aria-modal="true"]')
                ActionChains(driver).move_to_element_with_offset(overlay, 10, 10).click().perform()
                time.sleep(1)
                return True
            except:
                pass

            # Méthode 3: Touche Échap
            try:
                driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                time.sleep(1)
                return True
            except:
                pass

            # Méthode 4: Rechargement complet (dernier recours)
            if attempt == max_attempts - 1:
                driver.get(url)
                wait_for_results(driver)
                time.sleep(3)
                return True

        except Exception as e:
            logger.warning(f"Tentative {attempt + 1} échouée: {str(e)[:100]}...")
    
    return False


def scrape_google_maps(query, location, max_results=50):
    driver = None
    try:
        driver = configure_driver()
        encoded_query = urllib.parse.quote_plus(query)
        encoded_location = urllib.parse.quote_plus(location)
        url = f"https://www.google.com/maps/search/{encoded_query}+{encoded_location}"
        logger.info(f"Recherche: {query} à {location}")
        driver.get(url)

        time.sleep(random.uniform(3, 5))
        if not wait_for_results(driver):
            return []

        scroll_to_load_results(driver, max_results)

        results = []
        seen_names = set()

        for idx in range(max_results):
            try:
                items = extract_all_businesses(driver)
                if idx >= len(items):
                    break

                item = items[idx]
                # Scroll plus doux et centré
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", item)
                time.sleep(0.8)
                item.click()

                # Attente des détails
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.DUwDvf'))
                )
                time.sleep(2)  # Délai accru pour le chargement

                # Extraction des données
                business_data = extract_business_details(driver)

                if business_data.get('Nom') and business_data['Nom'] not in seen_names:
                    seen_names.add(business_data['Nom'])
                    results.append(business_data)
                    logger.info(f"{idx+1}/{max_results}: {business_data['Nom']}")

                # Fermeture du panneau détaillé
                try:
                    close_btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Fermer"]'))
                    )
                    close_btn.click()
                    time.sleep(1)
                    
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"]'))
                    )
                except Exception as e:
                    logger.warning(f"Échec de fermeture standard: {str(e)[:100]}...")
                    # Méthodes de secours
                    try:
                        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                        time.sleep(1)
                    except:
                        logger.warning("Échec de ESC, tentative de rechargement")
                        driver.get(url)
                        wait_for_results(driver)
                        time.sleep(3)

                time.sleep(random.uniform(1, 1.5))

            except Exception as e:
                logger.error(f"Erreur sur l'élément {idx+1}: {str(e)}")
                continue

        return results

    except Exception as e:
        logger.error(f"Erreur majeure: {str(e)}", exc_info=True)
        return []
    finally:
        if driver:
            driver.quit()

def save_results(results, query, location):
    if not results:
        logger.warning("Aucune donnée à sauvegarder")
        return None
    try:
        df = pd.DataFrame(results)
        cols_to_check = [col for col in df.columns if col not in ['Heure de scraping']]
        df = df.dropna(subset=cols_to_check, how='all')
        if df.empty:
            logger.warning("Aucune donnée valide après nettoyage")
            return None
        safe_query = "".join(x for x in query if x.isalnum() or x in " _-")
        safe_location = "".join(x for x in location if x.isalnum() or x in " _-")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"google_maps_{safe_query}_{safe_location}_{timestamp}.xlsx"
        df.to_excel(filename, index=False, engine='openpyxl')
        logger.info(f"Données sauvegardées dans {filename} ({len(df)} entrées valides)")
        return filename
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde: {str(e)}", exc_info=True)
        return None
