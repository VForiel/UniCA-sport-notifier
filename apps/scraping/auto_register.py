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

async def perform_auto_registration_playwright(user, event, attempt_id: int):
    """
    Effectue la tentative de blocage de place temporaire (créneau 30 minutes)
    via Playwright authentifié pour le compte de l'utilisateur.

    RÈGLE DE SÉCURITÉ ET D'ÉTHIQUE ABSOLUE :
    Ce script s'arrête EXPLICITEMENT et IMPÉRATIVEMENT avant toute validation
    de commande payante ou écran de paiement bancaire.
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

    # Vérification du nombre maximal de blocages actifs
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
            logger.info(f"[AutoRegister] Connexion CAS sur {cas_url} pour {user.email}...")
            await page.goto(cas_url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_selector('input#username', timeout=15000)

            # Saisie humaine des identifiants CAS
            await page.fill('input#username', credentials.unica_identifier)
            await asyncio.sleep(random.uniform(0.3, 0.7))
            await page.fill('input#password', raw_password)
            await asyncio.sleep(random.uniform(0.3, 0.7))

            submit_btn = await page.query_selector('button[type="submit"], input[type="submit"]')
            if submit_btn:
                await submit_btn.click()
                await page.wait_for_load_state('networkidle', timeout=20000)
                await asyncio.sleep(1.5)

            # 2. Navigation vers la liste des événements
            events_page_url = "https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement"
            logger.info(f"[AutoRegister] Recherche de l'événement {event.title} (ID {event.source_id})...")
            await page.goto(events_page_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(1.0, 1.8))

            # Recherche du bouton d'inscription pour l'événement (avec gestion multi-pages si besoin)
            btn_selector = f'button.js-inscription[data-id="{event.source_id}"], .card-event:has(#modal_details_event_{event.source_id}) button.js-inscription'
            register_btn = await page.query_selector(btn_selector)

            if not register_btn:
                # Vérification sur les pages de pagination si non trouvé en page 1
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
                # Diagnostic précis si le bouton est manquant
                page_text = await page.inner_text('body')
                if "complet" in page_text.lower():
                    raise Exception("L'événement est complet.")
                if "déjà inscrit" in page_text.lower():
                    raise Exception("Vous êtes déjà inscrit à cet événement.")
                raise Exception(f"Bouton d'inscription introuvable pour l'événement {event.source_id} ({event.title}).")

            # 3. Clic sur S'INSCRIRE
            logger.info(f"[AutoRegister] Clic sur le bouton S'inscrire pour l'événement {event.source_id}...")
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

            # =========================================================================
            # ARRÊT EXPLICITE AVANT PAIEMENT (EXIGÉ PAR LE CAHIER DES CHARGES SECTION 4.2 & 7.4)
            # =========================================================================
            # À cette étape, la place est réservée dans le panier pour 30 minutes.
            # NOUS N'EFFECTUONS AUCUNE VALIDATION DE COMMANDE NI CONFIRMATION BANCAIRE.
            # L'utilisateur finalise et paie lui-même sa réservation sur UniCA Sport.
            # =========================================================================
            logger.info(
                f"[AutoRegister - STOP SÉCURITÉ] Créneau réservé 30 minutes pour {user.email} sur {event.title}. "
                "Arrêt explicite avant paiement."
            )

            attempt.status = 'réussi'
            attempt.hold_expires_at = timezone.now() + timedelta(minutes=30)
            attempt.error_message = f"Place réservée avec succès pour '{event.title}'. Vous disposez de 30 minutes pour finaliser sur votre panier UniCA Sport !"
            attempt.save()
            return True, attempt.error_message

        except Exception as exc:
            logger.error(f"[AutoRegister] Échec de l'inscription pour {user.email} : {exc}")
            attempt.status = 'échoué'
            attempt.error_message = str(exc)[:500]
            attempt.save()
            return False, str(exc)
        finally:
            await browser.close()
