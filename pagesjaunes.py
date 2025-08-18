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
from selenium.webdriver.common.action_chains import ActionChains
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
    
    # Anti-bot
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Paramètres
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    service = Service(
        ChromeDriverManager().install(),
        service_args=['--disable-logging', '--silent']
    )

    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Masquage avancé
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        '''
    })
    return driver

def handle_cookies(driver):
    try:
        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button#didomi-notice-agree-button'))
            )
            driver.execute_script("arguments[0].click();", cookie_btn)
            time.sleep(1)
            return True
        except:
            pass
        try:
            cookie_btn = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Accepter tout"]')
            driver.execute_script("arguments[0].click();", cookie_btn)
            time.sleep(1)
            return True
        except:
            pass
        try:
            driver.execute_script(
                "document.cookie = 'didomi_token=xxxx; domain=.pagesjaunes.fr; path=/; max-age=31536000';"
            )
            time.sleep(1)
            return True
        except:
            pass
        logger.warning("Échec de la gestion des cookies")
        return False
    except Exception as e:
        logger.warning(f"Erreur gestion cookies: {str(e)[:100]}")
        return False

def extract_phone_numbers(driver, card):
    """Extraction téléphone robuste pour toutes les pages"""
    try:
        # Vérifier d'abord si le numéro est déjà visible dans la carte
        visible_numbers = []
        try:
            visible_phone_elements = card.find_elements(By.CSS_SELECTOR, 'div.number-contact, span.number-contact, a[href^="tel:"]')
            for element in visible_phone_elements:
                phone_text = element.text.replace('Tél :', '').strip()
                phone_text = ''.join(c for c in phone_text if c.isdigit() or c == ' ')
                if phone_text:
                    visible_numbers.append(phone_text)
            
            if visible_numbers:
                return ', '.join(visible_numbers)
        except:
            pass  # Continuer avec la méthode normale si la vérification échoue

        # Méthode normale avec clic sur le bouton
        phone_button = card.find_element(By.CSS_SELECTOR, 'button.btn_tel')

        # Récupérer l'ID du container de manière fiable
        container_id = None
        try:
            focus_data = phone_button.get_attribute("data-pjsetfocus")
            if focus_data and "bi-fantomas-" in focus_data:
                container_id = focus_data.split("bi-fantomas-")[-1].split('"')[0]
        except:
            pass

        if not container_id:
            logger.warning("Impossible de récupérer l'ID fantomas")
            return None

        container_id = f"bi-fantomas-{container_id}"

        # Scroll dans le viewport
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", phone_button)
        time.sleep(random.uniform(0.5, 1.0))

        # Clic JS (plus fiable)
        try:
            driver.execute_script("arguments[0].click();", phone_button)
        except:
            logger.warning("Impossible de cliquer sur le bouton téléphone")
            return None

        # Attendre 3-5 secondes max pour que le container apparaisse
        phone_container = None
        try:
            phone_container = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.ID, container_id)))
        except:
            # Retry 1 fois après 2s
            time.sleep(2)
            try:
                phone_container = WebDriverWait(driver, 3).until(
                    EC.visibility_of_element_located((By.ID, container_id)))
            except:
                logger.warning("Conteneur téléphone introuvable après retry")
                return None

        # Extraire numéros
        number_divs = phone_container.find_elements(By.CSS_SELECTOR, 'div.number-contact')
        phone_numbers = []
        for div in number_divs:
            phone_text = div.text.replace('Tél :', '').strip()
            phone_text = ''.join(c for c in phone_text if c.isdigit() or c == ' ')
            if phone_text:
                phone_numbers.append(phone_text)

        return ', '.join(phone_numbers) if phone_numbers else None

    except Exception as e:
        logger.error(f"Échec extraction téléphone: {str(e)}")
        return None




def extract_card_data(driver, card):
    data = {}
    try:
        data['Nom'] = card.find_element(By.CSS_SELECTOR, 'h3').text.strip()
    except:
        return None
    data['Téléphone'] = extract_phone_numbers(driver, card)
    try:
        address = card.find_element(By.CSS_SELECTOR, 'div.bi-address').text.strip()
        data['Adresse'] = ' '.join(address.split())
    except:
        pass
    try:
        website = card.find_element(By.CSS_SELECTOR, 'a[data-omniture*="site-internet"]').get_attribute('href')
        if website and 'pagesjaunes.fr' not in website:
            data['Site Web'] = website
    except:
        pass
    try:
        schedule = card.find_element(By.CSS_SELECTOR, 'span.bi-hours').text.strip()
        data['Horaires'] = schedule
    except:
        pass
    data['Heure de scraping'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return data

def scrape_pages_jaunes(query, location, max_results=20):
    driver = None
    try:
        driver = configure_driver()
        encoded_query = urllib.parse.quote_plus(query.lower())
        encoded_location = urllib.parse.quote_plus(location.lower())
        url = f"https://www.pagesjaunes.fr/recherche/{encoded_location}/{encoded_query}"
        logger.info(f"Lancement du scraping pour {query} à {location}")
        driver.get(url)
        time.sleep(random.uniform(4, 6))

        handle_cookies(driver)
        WebDriverWait(driver, 25).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li.bi'))
        )

        results = []
        page_num = 1

        while len(results) < max_results:
            logger.info(f"Scraping page {page_num} ...")

            # Récupérer les cartes visibles
            cards = driver.find_elements(By.CSS_SELECTOR, 'li.bi')
            for card in cards:
                if len(results) >= max_results:
                    break
                data = extract_card_data(driver, card)
                if data:
                    results.append(data)
                    logger.info(f"Extrait: {data['Nom']} | Tel: {data.get('Téléphone','N/A')}")

            # Vérifier si bouton "Suivant" existe
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, 'a#pagination-next')
                if "disabled" in next_btn.get_attribute("class"):
                    logger.info("Dernière page atteinte.")
                    break
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                time.sleep(random.uniform(1.5, 2.5))
                driver.execute_script("arguments[0].click();", next_btn)
                page_num += 1
                WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li.bi'))
                )
                time.sleep(random.uniform(3, 5))
            except Exception:
                logger.info("Pas de bouton 'Suivant', fin du scraping.")
                break

        return results[:max_results]

    except Exception as e:
        logger.error(f"ERREUR GLOBALE: {str(e)}")
        if driver:
            driver.save_screenshot('error_scraping.png')
        return []
    finally:
        if driver:
            driver.quit()


def save_pj_results(results, query, location):
    
    return None