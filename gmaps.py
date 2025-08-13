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

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('google_maps_scraper.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Désactiver les logs inutiles
logging.getLogger('WDM').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)

# Configuration avancée
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15'
]

def configure_driver():
    """Configuration optimisée du driver Chrome"""
    chrome_options = Options()
    
    # Paramètres anti-bot
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    
    # Optimisation des performances
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--output=/dev/null")
    
    # Mode headless avec nouvelle syntaxe
    chrome_options.add_argument("--headless=new")
    
    # Configuration du service
    service = Service(
        ChromeDriverManager().install(),
        service_args=['--disable-logging', '--silent']
    )
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Masquer le WebDriver
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
            window.chrome = {
                runtime: {},
            };
        '''
    })
    
    return driver

def wait_for_results(driver):
    """Nouvelle version avec timeout adaptatif"""
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"], div.m6QErb.DxyBCb')))
        return True
    except:
        logger.error("Timeout en attente des résultats")
        return False

def extract_all_businesses(driver):
    """Récupère tous les éléments business (sponsorisés et organiques)"""
    return driver.find_elements(
        By.CSS_SELECTOR, 
        '[role="article"], div.Nv2PK.THOPZb.CpccDe'
    )
    
def extract_business_data(item):
    """Version améliorée avec détection du type de résultat"""
    is_sponsored = "Sponsorisé" in item.get_attribute('innerHTML')
    
    data = {
        'Nom': extract_with_selectors(item, [
            'div.qBF1Pd.fontHeadlineSmall',
            'h1', 'h2', 'h3'
        ]),
        'Adresse': extract_with_selectors(item, [
            'div.W4Efsd > span:nth-of-type(2)',
            '[aria-label*="adresse"]',
            'div.fontBodyMedium > div'
        ]),
        'Téléphone': extract_phone(item),
        'Site Web': extract_website(item),
        'Note': extract_rating(item),
        'Prix': extract_price(item),
        'Sponsorisé': is_sponsored,
        'Heure de scraping': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    return {k: v for k, v in data.items() if v is not None}

def extract_with_selectors(item, selectors):
    """Helper pour extraire avec plusieurs sélecteurs"""
    for selector in selectors:
        try:
            element = item.find_element(By.CSS_SELECTOR, selector)
            text = element.text.strip()
            if text:
                return text
        except:
            continue
    return None
def extract_phone(item):
    """Extraction spécialisée du téléphone"""
    try:
        phone_btn = item.find_element(
            By.CSS_SELECTOR, 'button[aria-label*="phone"], button[aria-label*="téléphone"]')
        return phone_btn.get_attribute('aria-label').replace('Téléphone: ', '')
    except:
        return None
def extract_website(item):
    """Extraction robuste du site web"""
    try:
        website_btn = item.find_element(
            By.CSS_SELECTOR, 'a[href*="url?q="], a[aria-label*="site web"]')
        url = website_btn.get_attribute('href')
        if url and 'url?q=' in url:
            return urllib.parse.unquote(url.split('url?q=')[1].split('&')[0])
    except:
        return None

def extract_rating(item):
    """Extraction de la note"""
    try:
        rating_elem = item.find_element(
            By.CSS_SELECTOR, 'span.MW4etd, span.ZkP5Je')
        return rating_elem.text.strip()
    except:
        return None

def extract_price(item):
    """Extraction de la fourchette de prix"""
    try:
        price_elem = item.find_element(
            By.CSS_SELECTOR, 'span[aria-label*="€"], span[aria-label*="prix"]')
        return price_elem.get_attribute('aria-label')
    except:
        return None
      
def scrape_google_maps(query, location, max_results=50):
    """Fonction principale révisée"""
    driver = None
    try:
        driver = configure_driver()
        encoded_query = urllib.parse.quote_plus(query)
        encoded_location = urllib.parse.quote_plus(location)
        url = f"https://www.google.com/maps/search/{encoded_query}+{encoded_location}"
        
        logger.info(f"Recherche: {query} à {location}")
        driver.get(url)
        
        # Attente intelligente
        time.sleep(random.uniform(3, 5))
        
        if not wait_for_results(driver):
            return []

        # Nouvelle méthode de scroll
        last_height = 0
        scroll_attempts = 0
        max_attempts = 15
        
        while scroll_attempts < max_attempts:
            # Scroll spécifique à la sidebar
            driver.execute_script("""
                const sidebar = document.querySelector('div[role="feed"]');
                if (sidebar) sidebar.scrollTop = sidebar.scrollHeight;
            """)
            
            time.sleep(random.uniform(2, 4))
            
            # Vérification du chargement
            current_height = driver.execute_script("""
                const sidebar = document.querySelector('div[role="feed"]');
                return sidebar ? sidebar.scrollHeight : 0;
            """)
            
            if current_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_height = current_height
            
            # Vérification du nombre de résultats
            items = extract_all_businesses(driver)
            if len(items) >= max_results:
                break

        # Extraction finale
        items = extract_all_businesses(driver)[:max_results]
        logger.info(f"{len(items)} entreprises trouvées (dont {sum('Sponsorisé' in i.get_attribute('innerHTML') for i in items)} sponsorisées)")
        
        results = []
        seen_names = set()
        
        for idx, item in enumerate(items, 1):
            try:
                business_data = extract_business_data(item)
                
                # Filtrage des doublons et entrées incomplètes
                if (business_data['Nom'] and 
                    business_data['Nom'] not in seen_names and
                    (business_data['Adresse'] or business_data['Téléphone'])):
                    
                    seen_names.add(business_data['Nom'])
                    results.append(business_data)
                    logger.info(f"{idx}/{len(items)}: {business_data['Nom']} {'(Sponsorisé)' if business_data.get('Sponsorisé') else ''}")
                
                # Délai aléatoire
                time.sleep(random.uniform(0.5, 1.5))
                
            except Exception as e:
                logger.error(f"Erreur sur l'élément {idx}: {str(e)[:100]}...")
                continue
        
        return results

    except Exception as e:
        logger.error(f"Erreur majeure: {str(e)}", exc_info=True)
        return []
    finally:
        if driver:
            driver.quit()

def save_results(results, query, location):
    """Sauvegarde des résultats avec gestion des erreurs"""
    if not results:
        logger.warning("Aucune donnée à sauvegarder")
        return None
    
    try:
        df = pd.DataFrame(results)
        
        # Supprimer les lignes où toutes les colonnes (sauf l'heure de scraping) sont None
        cols_to_check = ['Nom', 'Adresse', 'Téléphone', 'Site Web']
        df = df.dropna(subset=cols_to_check, how='all')
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"google_maps_{query}_{location}_{timestamp}.xlsx"
        
        # Correction pour l'export Excel (erreur d'encoding dans les logs)
        df.to_excel(filename, index=False, engine='openpyxl')
        logger.info(f"Données sauvegardées dans {filename} ({len(df)} entrées valides)")
        
        return filename
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde: {str(e)}")
        return None

