import time
import random
import urllib.parse
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
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

def wait_for_results(driver):
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"], div.m6QErb.DxyBCb'))
        )
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

def close_details_panel(driver):
    """Ferme la fiche en gérant mode desktop et mobile"""
    try:
        # Essai 1 : bouton Fermer (desktop)
       

        # Essai 2 : bouton Retour (mobile)
        back_btn = driver.find_elements(By.CSS_SELECTOR, 'button[aria-label="Retour"]')
        if back_btn:
            back_btn[0].click()
            logger.info("Retour à la liste (mobile).")
            return True

        # Essai 3 : touche Échap
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        logger.info("Fermeture via ESC.")
        return True

    except Exception as e:
        logger.warning(f"Impossible de fermer la fiche : {e}")
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

        idx = 0
        while idx < max_results:
            try:
                items = extract_all_businesses(driver)
                if idx >= len(items):
                    break

                item = items[idx]
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", item)
                time.sleep(0.8)
                item.click()

                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.DUwDvf'))
                )
                time.sleep(1.5)

                business_data = extract_business_details(driver)

                if business_data.get('Nom') and business_data['Nom'] not in seen_names:
                    seen_names.add(business_data['Nom'])
                    results.append(business_data)
                    logger.info(f"{len(results)}/{max_results}: {business_data['Nom']}")

                # Fermeture propre du panneau
                if not close_details_panel(driver):
                    logger.warning(f"Saut de l'élément {idx+1} (fermeture impossible)")
                else:
                    try:
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"]'))
                        )
                    except:
                        logger.warning("Liste non réapparue, saut forcé")

                time.sleep(random.uniform(0.8, 1.3))

            except Exception as e:
                logger.error(f"Erreur sur l'élément {idx+1}: {str(e)}")
            finally:
                idx += 1  # Passe à l'élément suivant quoi qu'il arrive

        return results

    except Exception as e:
        logger.error(f"Erreur majeure: {str(e)}", exc_info=True)
        return []
    finally:
        if driver:
            driver.quit()


def save_results(results, query, location):
    
    return None
