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
        logging.FileHandler('pages_jaunes_scraper.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Désactivation des logs inutiles
logging.getLogger('WDM').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

def configure_driver():
    chrome_options = Options()
    
    # Configuration anti-détection et optimisation
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Désactivation des fonctionnalités problématiques
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-browser-side-navigation")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-infobars")
    
    # Headless moderne
    chrome_options.add_argument("--headless=new")
    
    # User-Agent mobile pour éviter les CAPTCHAs
    mobile_emulation = {
        "userAgent": "Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.62 Mobile Safari/537.36"
    }
    chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)

    service = Service(
        ChromeDriverManager().install(),
        service_args=['--disable-logging', '--silent']
    )

    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Masquage supplémentaire
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr']});
        '''
    })
    return driver

def handle_cookies(driver):
    """Gestion robuste des cookies avec plusieurs méthodes"""
    try:
        # Méthode 1: Attente classique
        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button#didomi-notice-agree-button'))
            )
            driver.execute_script("arguments[0].click();", cookie_btn)
            time.sleep(1)
            return True
        except:
            pass

        # Méthode 2: Sélecteur alternatif
        try:
            cookie_btn = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Accepter tout"]')
            driver.execute_script("arguments[0].click();", cookie_btn)
            time.sleep(1)
            return True
        except:
            pass

        # Méthode 3: Injection JS directe
        try:
            driver.execute_script("""document.cookie = 'didomi_token=xxxx; domain=.pagesjaunes.fr; path=/; max-age=31536000';""")
            time.sleep(1)
            return True
        except:
            pass

        logger.warning("Échec de la gestion des cookies")
        return False
    except Exception as e:
        logger.warning(f"Erreur gestion cookies: {str(e)[:100]}")
        return False

def extract_card_data(card):
    """Extraction précise basée sur la structure réelle du HTML"""
    data = {}
    
    # Nom
    try:
        name = card.find_element(By.CSS_SELECTOR, 'h3').text.strip()
        data['Nom'] = name
    except:
        return None
    
    # Adresse
    try:
        address_elem = card.find_element(By.CSS_SELECTOR, 'div.bi-address a')
        address = ' '.join(address_elem.text.split())  # Nettoie les espaces multiples
        data['Adresse'] = address
    except:
        pass
    
    # Téléphone (nécessite un clic pour afficher)
    try:
        phone_button = card.find_element(By.CSS_SELECTOR, 'button.btn_tel')
        driver.execute_script("arguments[0].click();", phone_button)
        time.sleep(1)  # Attendre l'affichage du numéro
        phone = card.find_element(By.CSS_SELECTOR, 'div.number-contact').text
        data['Téléphone'] = phone.replace('Tél :', '').strip()
    except:
        pass
    
    # Horaires
    try:
        schedule = card.find_element(By.CSS_SELECTOR, 'span.bi-hours').text
        data['Horaires'] = schedule
    except:
        pass
    
    # Site Web
    try:
        website = card.find_element(By.CSS_SELECTOR, 'a.site-internet').get_attribute('href')
        data['Site Web'] = website
    except:
        pass
    
    # Note
    try:
        rating = card.find_element(By.CSS_SELECTOR, 'span.note_moyenne').text
        data['Note'] = rating
    except:
        pass
    
    # Nombre d'avis
    try:
        reviews = card.find_element(By.CSS_SELECTOR, 'span.bi-rating').text
        data['Avis'] = reviews
    except:
        pass
    
    # Tags/Catégories
    try:
        tags = [tag.text for tag in card.find_elements(By.CSS_SELECTOR, 'li.bi-tag')]
        data['Tags'] = ', '.join(tags)
    except:
        pass
    
    # Description
    try:
        description = card.find_element(By.CSS_SELECTOR, 'p.bi-description').text
        data['Description'] = description
    except:
        pass
    
    data['Heure de scraping'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return data

def scrape_pages_jaunes(query, location, max_results=20):
    driver = None
    try:
        driver = configure_driver()
        url = f"https://www.pagesjaunes.fr/recherche/{location}/{query}"
        driver.get(url)
        time.sleep(random.uniform(3, 5))

        # Accepter les cookies si nécessaire
        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button#didomi-notice-agree-button'))
            )
            cookie_btn.click()
            time.sleep(1)
        except:
            pass

        # Attendre les résultats
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'li.bi'))
        )

        # Scrolling progressif
        results = []
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        while len(results) < max_results:
            # Scroller
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 3))
            
            # Extraire les cartes visibles
            cards = driver.find_elements(By.CSS_SELECTOR, 'li.bi')[:max_results]
            for card in cards[len(results):]:
                try:
                    data = extract_card_data(card)
                    if data:
                        results.append(data)
                        logger.info(f"Résultat {len(results)}: {data['Nom']}")
                except Exception as e:
                    logger.warning(f"Erreur sur carte: {str(e)[:100]}")

            # Vérifier si on a atteint la fin de page
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

            if len(results) >= max_results:
                break

        return results[:max_results]

    except Exception as e:
        logger.error(f"Erreur majeure: {str(e)}")
        return []
    finally:
        if driver:
            driver.quit()

def save_pj_results(results, query, location):
    """Sauvegarde identique à la version précédente"""
    if not results:
        logger.warning("Aucune donnée à sauvegarder")
        return None
    
    try:
        df = pd.DataFrame(results)
        # Nettoyage des colonnes vides
        df = df.dropna(axis=1, how='all')
        if df.empty:
            logger.warning("DataFrame vide après nettoyage")
            return None
            
        filename = f"pagesjaunes_{query[:20]}_{location[:10]}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        logger.info(f"Fichier sauvegardé : {filename} ({len(df)} résultats)")
        return filename
    except Exception as e:
        logger.error(f"Erreur sauvegarde : {str(e)}")
        return None