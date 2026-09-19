import asyncio
import logging
import random
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from .parsers import parse_events_html

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

TARGET_URL = "https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement"

async def fetch_unica_events_playwright(url: str = TARGET_URL):
    """
    Lance une session Playwright asynchrone avec stealth et temporisations humaines
    pour récupérer la page d'événements UniCA Sport en limitant le risque de détection.
    """
    selected_ua = random.choice(USER_AGENTS)
    logger.info(f"Démarrage du scan Playwright sur {url} avec User-Agent {selected_ua[:35]}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        context = await browser.new_context(
            user_agent=selected_ua,
            viewport={'width': 1920, 'height': 1080},
            locale='fr-FR',
            timezone_id='Europe/Paris'
        )
        page = await context.new_page()

        # Application du module stealth
        stealth = Stealth()
        await stealth.apply_stealth_async(page)

        try:
            # Navigation avec temporisation
            await page.goto(url, wait_until='domcontentloaded', timeout=35000)
            
            # Délai humain aléatoire (1 à 2.5 secondes)
            await asyncio.sleep(random.uniform(1.2, 2.5))

            # Attendre que les cartes d'événements soient chargées
            try:
                await page.wait_for_selector('.card-event', timeout=8000)
            except Exception:
                logger.warning("Sélecteur '.card-event' non apparu dans le délai imparti.")

            content = await page.content()
            events = parse_events_html(content)
            logger.info(f"Scan Playwright terminé avec succès : {len(events)} événement(s) extrait(s).")
            return events

        except Exception as e:
            logger.error(f"Erreur lors de la navigation Playwright : {e}")
            raise e
        finally:
            await browser.close()


def scrape_unica_events_sync(url: str = TARGET_URL):
    """Point d'entrée synchrone utilisable depuis les tâches Celery ou commandes de gestion."""
    return asyncio.run(fetch_unica_events_playwright(url))
