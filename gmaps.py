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
    """Attente intelligente des résultats avec timeout progressif"""
    selectors = [
        ('div[role="feed"]', "Conteneur principal"),
        ('div[role="article"]', "Fiche entreprise"),
        ('div.Q2HXcd', "Conteneur résultats"),
        ('div.m6QErb', "Conteneur résultats alternatif")
    ]
    
    for selector, description in selectors:
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            logger.info(f"Élément trouvé: {description}")
            return True
        except:
            continue
    
    logger.error("Aucun sélecteur valide trouvé")
    return False

def extract_business_data(item):
    """Extraction robuste des données avec gestion des erreurs"""
    data = {
        'Nom': None,  # Changé à None au lieu de "Non disponible"
        'Adresse': None,
        'Téléphone': None,
        'Site Web': None,
        'Heure de scraping': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Extraction du nom
    name_selectors = [
        'div.fontHeadlineSmall',
        'h1', 'h2', 'h3',
        '[aria-label*="nom"]',
        '[aria-label*="title"]'
    ]
    for selector in name_selectors:
        try:
            name = item.find_element(By.CSS_SELECTOR, selector).text.strip()
            if name:  # Vérifie que le nom n'est pas vide
                data['Nom'] = name
                break
        except:
            continue
    
    # Extraction de l'adresse
    address_selectors = [
        'div.fontBodyMedium > div:nth-of-type(1)',
        '[aria-label*="adresse"]',
        '[aria-label*="address"]',
        'div.W4Efsd:nth-of-type(1)'
    ]
    for selector in address_selectors:
        try:
            address = item.find_element(By.CSS_SELECTOR, selector).text.strip()
            if address:  # Vérifie que l'adresse n'est pas vide
                data['Adresse'] = address
                break
        except:
            continue
    
    # Extraction du téléphone
    phone_selectors = [
        'div.fontBodyMedium > div:nth-of-type(2)',
        '[aria-label*="téléphone"]',
        '[aria-label*="phone"]',
        'div.W4Efsd:nth-of-type(2)',
        'button[aria-label*="phone"]'
    ]
    for selector in phone_selectors:
        try:
            phone_text = item.find_element(By.CSS_SELECTOR, selector).text.strip()
            if any(c.isdigit() for c in phone_text):  # Vérifie qu'il y a des chiffres
                data['Téléphone'] = phone_text
                break
        except:
            continue
    
    # Extraction du site web
    try:
        website_elem = item.find_element(By.CSS_SELECTOR, 'a[href*="https://www.google.com/url"]')
        website_url = website_elem.get_attribute('href')
        if website_url:
            decoded_url = urllib.parse.unquote(website_url.split('url=')[1].split('&')[0])
            if decoded_url.startswith(('http://', 'https://')):
                data['Site Web'] = decoded_url
    except:
        pass
    
    return data

def scrape_google_maps(query, location, max_results=20):
    """Fonction principale de scraping"""
    driver = None
    try:
        driver = configure_driver()
        encoded_query = urllib.parse.quote_plus(query)
        encoded_location = urllib.parse.quote_plus(location)
        url = f"https://www.google.com/maps/search/{encoded_query}+{encoded_location}"
        
        logger.info(f"Recherche: {query} à {location}")
        driver.get(url)
        
        # Attente initiale dynamique
        initial_wait = random.uniform(3, 7)
        logger.info(f"Attente initiale de {initial_wait:.2f}s")
        time.sleep(initial_wait)
        
        # Vérification CAPTCHA
        if "captcha" in driver.page_source.lower():
            logger.error("CAPTCHA détecté! Solutions possibles:")
            logger.error("1. Augmenter les délais (paramètre delay)")
            logger.error("2. Utiliser un proxy rotatif")
            logger.error("3. Résoudre manuellement avec headless=False")
            return []
        
        # Attente des résultats
        if not wait_for_results(driver):
            logger.error("Échec de chargement des résultats")
            return []
        
        # Scroll progressif
        scroll_pause = random.uniform(1, 3)
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        
        while scroll_attempts < 5:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause)
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            
            last_height = new_height
            
            # Vérifier si assez de résultats
            items = driver.find_elements(By.CSS_SELECTOR, '[role="article"], div.Q2HXcd, div.m6QErb')
            if len(items) >= max_results:
                break
        
        # Extraction des données
        items = driver.find_elements(By.CSS_SELECTOR, '[role="article"], div.Q2HXcd, div.m6QErb')[:max_results]
        logger.info(f"{len(items)} entreprises trouvées")
        
        results = []
        seen_names = set()  # Pour éviter les doublons
        
        for idx, item in enumerate(items, 1):
            try:
                business_data = extract_business_data(item)
                
                # Vérifier si l'entreprise a un nom et n'est pas déjà dans les résultats
                if business_data['Nom'] and business_data['Nom'] not in seen_names:
                    seen_names.add(business_data['Nom'])
                    
                    # Ne garder que les entrées avec au moins une information utile (autre que le nom)
                    if any(business_data[key] for key in ['Adresse', 'Téléphone', 'Site Web']):
                        results.append(business_data)
                        logger.info(f"{idx}/{len(items)}: {business_data['Nom']}")
                    else:
                        logger.info(f"{idx}/{len(items)}: {business_data['Nom']} - Pas d'informations utiles, ignoré")
                
                # Délai aléatoire entre les extractions
                time.sleep(random.uniform(0.5, 2))
                
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

