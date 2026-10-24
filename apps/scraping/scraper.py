import asyncio
import logging
import random
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from .parsers import parse_events_html, extract_next_page_url

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

TARGET_URL = "https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement"

async def fetch_unica_events_playwright(url: str = TARGET_URL, max_pages: int = 20):
    """
    Lance une session Playwright asynchrone avec stealth et temporisations humaines
    pour récupérer tous les événements UniCA Sport en parcourant la pagination (ex: /Evenement/2).
    """
    selected_ua = random.choice(USER_AGENTS)
    logger.info(f"Démarrage du scan Playwright multi-pages sur {url} avec User-Agent {selected_ua[:35]}...")

    all_events = []
    seen_ids = set()

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
        try:
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

            current_url = url
            page_idx = 1

            while current_url and page_idx <= max_pages:
                logger.info(f"Navigation Playwright vers page {page_idx} : {current_url}")
                await page.goto(current_url, wait_until='domcontentloaded', timeout=35000)

                # Délai humain aléatoire (0.8 à 1.8 secondes)
                await asyncio.sleep(random.uniform(0.8, 1.8))

                # Attendre le sélecteur des événements
                try:
                    await page.wait_for_selector('.card-event', timeout=6000)
                except Exception:
                    logger.debug(f"Sélecteur '.card-event' non apparu sur {current_url}.")

                content = await page.content()
                page_events = parse_events_html(content)
                if not page_events:
                    logger.info(f"Page {page_idx} sans événements : arrêt du parcours de pagination.")
                    break

                for evt in page_events:
                    if evt['source_id'] not in seen_ids:
                        seen_ids.add(evt['source_id'])
                        all_events.append(evt)

                # Recherche de la page suivante
                next_url = extract_next_page_url(content)
                if next_url and next_url != current_url:
                    current_url = next_url
                    page_idx += 1
                else:
                    break

            logger.info(f"Scan Playwright multi-pages terminé : {len(all_events)} événement(s) trouvé(s) sur {page_idx} page(s).")
            return all_events

        except Exception as e:
            logger.error(f"Erreur lors de la navigation Playwright : {e}")
            if all_events:
                # Retourne ce qui a déjà été extrait sur les premières pages
                return all_events
            raise e
        finally:
            await browser.close()


def scrape_unica_events_sync(url: str = TARGET_URL, max_pages: int = 20):
    """Point d'entrée synchrone utilisable depuis les tâches Celery ou commandes de gestion."""
    return asyncio.run(fetch_unica_events_playwright(url, max_pages=max_pages))
