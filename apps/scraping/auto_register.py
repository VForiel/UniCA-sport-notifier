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
            # 1. Navigation vers la page de connexion
            await page.goto(AUTH_LOGIN_URL, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Choix du mode d'authentification : CAS ou Basic
            # UniCA propose soit CAS UCA (/fr/Connexion/Cas/cas-uca), soit Compte externe (/fr/Connexion/Basic/default)
            cas_link = await page.query_selector('a[href*="/Cas/cas-uca"]')
            if cas_link:
                await cas_link.click()
                await page.wait_for_load_state('domcontentloaded')
                await asyncio.sleep(1.0)

                # Remplissage formulaire CAS (username / password)
                username_input = await page.query_selector('input#username, input[name="username"]')
                password_input = await page.query_selector('input#password, input[name="password"]')

                if username_input and password_input:
                    await username_input.fill(credentials.unica_identifier)
                    await asyncio.sleep(random.uniform(0.3, 0.7))
                    await password_input.fill(raw_password)
                    await asyncio.sleep(random.uniform(0.3, 0.7))
                    
                    submit_btn = await page.query_selector('input[type="submit"], button[type="submit"]')
                    if submit_btn:
                        await submit_btn.click()
                        await page.wait_for_load_state('networkidle', timeout=15000)

            # 2. Navigation vers la page de l'événement cible
            logger.info(f"[AutoRegister] Navigation vers l'événement {event.url}")
            await page.goto(event.url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(1.2, 2.0))

            # 3. Recherche du bouton d'inscription pour l'événement
            # Selon le code source UniCA : bouton dans .card-event ou modal d'inscription
            register_btn = await page.query_selector(
                f'.card-event:has(#modal_details_event_{event.source_id}) button.btn-primary:not([data-dismiss]), '
                f'button[data-target="#modal_details_event_{event.source_id}"] ~ button, '
                'a.btn-primary:has-text("S\'inscrire"), button.btn-primary:has-text("S\'inscrire"), '
                '.card-event a[href*="Inscription"], .card-event button[data-action*="inscription"]'
            )

            if not register_btn:
                # Vérifier si l'utilisateur est déjà inscrit ou complet
                page_text = await page.inner_text('body')
                if "complet" in page_text.lower():
                    raise Exception("L'événement est complet.")
                if "déjà inscrit" in page_text.lower():
                    raise Exception("Vous êtes déjà inscrit à cet événement.")
                raise Exception("Bouton d'inscription introuvable sur la page de l'événement.")

            # Clic sur Inscription
            await register_btn.click()
            await page.wait_for_load_state('domcontentloaded', timeout=10000)
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # 4. Étape de validation du panier / réservation temporaire
            # Sur UniCA Sport, l'ajout au panier réserve le créneau pendant 30 minutes
            cart_confirm_btn = await page.query_selector(
                'button#confirm_cart, input[value*="Ajouter au panier"], button:has-text("Ajouter au panier"), '
                '.modal button.btn-primary:has-text("Confirmer")'
            )
            if cart_confirm_btn:
                await cart_confirm_btn.click()
                await page.wait_for_load_state('networkidle', timeout=15000)
                await asyncio.sleep(1.0)

            # =========================================================================
            # ARRÊT EXPLICITE AVANT PAIEMENT (EXIGÉ PAR LE CAHIER DES CHARGES SECTION 4.2 & 7.4)
            # =========================================================================
            # À cette étape, la place est verrouillée dans le panier pour 30 minutes.
            # NOUS N'EFFECTUONS AUCUNE VALIDATION DE PAIEMENT NI CONFIRMATION BANCAIRE.
            # L'utilisateur doit se connecter lui-même pour finaliser et payer.
            # =========================================================================
            logger.info(
                "[AutoRegister - STOP SÉCURITÉ] La place est réservée dans le panier pour 30 minutes. "
                "Arrêt explicite avant paiement."
            )

            attempt.status = 'réussi'
            attempt.hold_expires_at = timezone.now() + timedelta(minutes=30)
            attempt.error_message = "Place réservée avec succès pour 30 minutes. Finalisez votre commande sur UniCA Sport !"
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
