import asyncio
import logging
import random
from datetime import timedelta
from django.utils import timezone
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from apps.events.models import RegistrationAttempt
from apps.events.services import decrypt_password

logger = logging.getLogger(__name__)

MAX_SIMULTANEOUS_HOLDS = 2
AUTH_LOGIN_URL = "https://sport.univ-cotedazur.fr/fr/Connexion"

async def _run_playwright_cart_flow(unica_id: str, raw_pwd: str, source_id: str, title: str) -> tuple[bool, str]:
    """
    Exécute le navigateur Playwright pour se connecter au CAS et ajouter l'événement au panier.
    S'arrête strictement avant toute étape de paiement.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='fr-FR',
            timezone_id='Europe/Paris'
        )
        page = await context.new_page()
        stealth = Stealth()
        await stealth.apply_stealth_async(page)

        try:
            # 1. Navigation directe vers le CAS UniCA
            cas_url = "https://sport.univ-cotedazur.fr/fr/Connexion/Cas/cas-uca"
            logger.info(f"[AutoRegister] Connexion CAS sur {cas_url} pour {unica_id}...")
            await page.goto(cas_url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_selector('input#username', timeout=15000)

            # Saisie humaine des identifiants CAS
            await page.fill('input#username', unica_id)
            await asyncio.sleep(random.uniform(0.3, 0.7))
            await page.fill('input#password', raw_pwd)
            await asyncio.sleep(random.uniform(0.3, 0.7))

            submit_btn = await page.query_selector('button[type="submit"], input[type="submit"]')
            if submit_btn:
                await submit_btn.click()
                await page.wait_for_load_state('networkidle', timeout=20000)
                await asyncio.sleep(1.5)

            # 2. Navigation vers la liste des événements
            events_page_url = "https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement"
            logger.info(f"[AutoRegister] Recherche de l'événement {title} (ID {source_id})...")
            await page.goto(events_page_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(1.0, 1.8))

            # Recherche du bouton d'inscription pour l'événement (avec gestion multi-pages)
            btn_selector = f'button.js-inscription[data-id="{source_id}"], .card-event:has(#modal_details_event_{source_id}) button.js-inscription'
            register_btn = await page.query_selector(btn_selector)

            if not register_btn:
                from .parsers import extract_next_page_url
                curr_content = await page.content()
                next_url = extract_next_page_url(curr_content)
                while next_url and not register_btn:
                    logger.info(f"[AutoRegister] Événement non trouvé sur cette page, consultation de {next_url}...")
                    await page.goto(next_url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(1.2)
                    register_btn = await page.query_selector(btn_selector)
                    curr_content = await page.content()
                    next_url = extract_next_page_url(curr_content)

            if not register_btn:
                page_text = await page.inner_text('body')
                if "complet" in page_text.lower():
                    raise Exception("L'événement est complet.")
                if "déjà inscrit" in page_text.lower():
                    raise Exception("Vous êtes déjà inscrit à cet événement.")
                raise Exception(f"Bouton d'inscription introuvable pour l'événement {source_id} ({title}).")

            # 3. Clic sur S'INSCRIRE
            logger.info(f"[AutoRegister] Clic sur le bouton S'inscrire pour l'événement {source_id}...")
            await register_btn.click()
            await asyncio.sleep(1.0)

            # 4. Attente du modal de confirmation et clic sur AJOUTER AU PANIER
            confirm_btn_selector = '#modalInscription button#btn-confirmation, button#btn-confirmation'
            await page.wait_for_selector(confirm_btn_selector, timeout=10000)
            await asyncio.sleep(random.uniform(0.6, 1.2))

            logger.info("[AutoRegister] Validation du créneau dans le panier (#btn-confirmation)...")
            await page.click(confirm_btn_selector)
            await page.wait_for_load_state('networkidle', timeout=15000)
            await asyncio.sleep(1.5)

            # 5. Vérification du Panier
            cart_url = "https://sport.univ-cotedazur.fr/fr/UcaWeb/Panier"
            await page.goto(cart_url, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(1.5)

            # ARRÊT EXPLICITE AVANT PAIEMENT
            logger.info(
                f"[AutoRegister - STOP SÉCURITÉ] Créneau réservé 30 minutes sur {title}. "
                "Arrêt explicite avant paiement."
            )
            msg = f"Place réservée avec succès pour '{title}'. Vous disposez de 30 minutes pour finaliser sur votre panier UniCA Sport !"
            return True, msg

        except Exception as exc:
            logger.error(f"[AutoRegister] Erreur lors du flux Playwright : {exc}")
            return False, str(exc)
        finally:
            await browser.close()


def perform_auto_registration_sync(user, event, attempt_id: int) -> tuple[bool, str]:
    """
    Exécute les validations préalables côté base de données Django ORM,
    puis lance le blocage du panier via Playwright de façon isolée et sécurisée.
    """
    attempt = RegistrationAttempt.objects.get(id=attempt_id)
    credentials = getattr(user, 'unica_credentials', None)

    if not credentials or not credentials.unica_identifier or not credentials.encrypted_password:
        attempt.status = 'échoué'
        attempt.error_message = "Identifiants UniCA non configurés ou incomplets."
        attempt.save()
        return False, attempt.error_message

    if not credentials.auto_registration_consent:
        attempt.status = 'échoué'
        attempt.error_message = "Consentement de l'utilisateur manquant pour la réservation automatique."
        attempt.save()
        return False, attempt.error_message

    # Vérification du nombre maximal de blocages actifs (réservé aux usagers non-administrateurs)
    is_admin = bool(getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False))
    if not is_admin:
        active_holds = RegistrationAttempt.objects.filter(
            user=user,
            status='réussi',
            hold_expires_at__gt=timezone.now()
        ).count()

        if active_holds >= MAX_SIMULTANEOUS_HOLDS:
            attempt.status = 'échoué'
            attempt.error_message = (
                f"Limite éthique atteinte : vous avez déjà {active_holds} place(s) réservée(s) "
                "non validée(s). Confirmez vos inscriptions en cours avant d'en bloquer de nouvelles."
            )
            attempt.save()
            return False, attempt.error_message

    try:
        raw_password = decrypt_password(credentials.encrypted_password)
    except Exception as e:
        attempt.status = 'échoué'
        attempt.error_message = f"Erreur de déchiffrement des identifiants : {str(e)}"
        attempt.save()
        return False, attempt.error_message

    logger.info(f"[AutoRegister] Démarrage de la réservation pour {user.email} sur {event.title}...")
    success, message = asyncio.run(_run_playwright_cart_flow(
        credentials.unica_identifier,
        raw_password,
        event.source_id,
        event.title
    ))

    if success:
        attempt.status = 'réussi'
        attempt.hold_expires_at = timezone.now() + timedelta(minutes=30)
        attempt.error_message = message
    else:
        attempt.status = 'échoué'
        attempt.error_message = message[:500]
    attempt.save()
    return success, message


# Alias pour rétrocompatibilité
perform_auto_registration = perform_auto_registration_sync
perform_auto_registration_playwright = perform_auto_registration_sync
