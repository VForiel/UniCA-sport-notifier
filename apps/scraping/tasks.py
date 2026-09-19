import time
import random
import logging
from zoneinfo import ZoneInfo
from datetime import datetime
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.events.models import Event, RegistrationAttempt
from apps.events.services import evaluate_event_for_user
from apps.notifications.tasks import dispatch_notification_task
from .models import ServerSettings, ScanLog
from .scraper import scrape_unica_events_sync
from .auto_register import perform_auto_registration_playwright

logger = logging.getLogger(__name__)

def calculate_next_scan_delay(current_dt: datetime = None, settings_obj: ServerSettings = None) -> int:
    """
    Calcule le délai (en secondes) avant le prochain scan selon :
    - Le fuseau horaire Europe/Paris (non UTC).
    - La bascule jour / nuit définie dans ServerSettings.
    - L'application du jitter aléatoire ± correspondant.
    """
    if current_dt is None:
        current_dt = datetime.now(ZoneInfo("Europe/Paris"))
    elif current_dt.tzinfo is None:
        current_dt = current_dt.replace(tzinfo=ZoneInfo("Europe/Paris"))
    else:
        current_dt = current_dt.astimezone(ZoneInfo("Europe/Paris"))

    if settings_obj is None:
        try:
            settings_obj = ServerSettings.get_solo()
        except Exception:
            settings_obj = ServerSettings()

    current_time = current_dt.time()
    day_start = settings_obj.day_start_time
    night_start = settings_obj.night_start_time

    # Détermination du mode diurne vs nocturne
    # Cas standard : jour de 06:00 à 00:00 (minuit)
    if day_start < night_start:
        is_day = day_start <= current_time < night_start
    else:
        # Cas où night_start est 00:00 ou passage par minuit
        is_day = current_time >= day_start or current_time < night_start

    if is_day:
        base_interval = settings_obj.day_interval_seconds
        jitter = random.uniform(-settings_obj.day_jitter_seconds, settings_obj.day_jitter_seconds)
    else:
        base_interval = settings_obj.night_interval_seconds
        jitter = random.uniform(-settings_obj.night_jitter_seconds, settings_obj.night_jitter_seconds)

    delay = int(round(base_interval + jitter))
    return max(5, delay)  # Minimum 5 secondes de sécurité


def safe_dispatch_task(task_func, *args, **kwargs):
    """
    Délègue la tâche à Celery de manière asynchrone (broker Redis).
    Si le broker est indisponible (ex: environnement dev local sans Redis démarré),
    exécute directement la tâche de façon synchrone pour éviter tout blocage réseau.
    """
    try:
        from django.conf import settings
        import redis
        broker_url = getattr(settings, 'CELERY_BROKER_URL', '')
        if broker_url.startswith('redis://'):
            r = redis.from_url(broker_url, socket_connect_timeout=0.5, socket_timeout=0.5)
            r.ping()
        return task_func.apply_async(args=args, kwargs=kwargs, retry=False)
    except Exception as e:
        logger.warning(f"Broker Celery indisponible ({e}), exécution synchrone locale de {task_func.__name__}...")
        return task_func(*args, **kwargs)


@shared_task(bind=True, queue='celery', max_retries=2)
def auto_register_task(self, user_id: int, event_id: int, attempt_id: int):
    """
    Tâche Celery dédiée à l'exécution de la tentative d'inscription / blocage de place.
    Gère jusqu'à 2 réessais en cas d'échec transitoire.
    """
    import asyncio
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        event = Event.objects.get(id=event_id)
        attempt = RegistrationAttempt.objects.get(id=attempt_id)
    except Exception as e:
        logger.error(f"auto_register_task: Objets introuvables : {e}")
        return False

    success, message = perform_auto_registration_playwright(user, event, attempt_id)

    # Notification immédiate du résultat de la réservation
    notif_msg = (
        f"Résultat réservation '{event.title}' : {message}"
    )
    safe_dispatch_task(
        dispatch_notification_task,
        user_id=user.id,
        event_id=event.id,
        message=notif_msg,
        attempt_id=attempt.id
    )

    if not success and self.request.retries < self.max_retries:
        # Erreur transitoire potentielle : nouvel essai avec backoff
        countdown = 15 * (self.request.retries + 1)
        logger.warning(f"Nouvelle tentative auto_register dans {countdown}s...")
        raise self.retry(countdown=countdown)

    return success


@shared_task(bind=True, queue='celery')
def scan_events_task(self, auto_reschedule: bool = True):
    """
    Tâche Celery principale de scan :
    1. Exécute le scraping Playwright.
    2. Détecte les nouveaux événements et modifications.
    3. Évalue les FilterRule de chaque utilisateur.
    4. Déclenche notifications et réservations automatiques.
    5. Enregistre un ScanLog.
    6. Calcule le prochain délai et s'auto-replanifie via apply_async(countdown=...).
    """
    start_time = time.time()
    events_found_count = 0
    new_events_count = 0
    status = 'succès'
    error_msg = ""
    settings_obj = ServerSettings.get_solo()

    try:
        scraped_events = scrape_unica_events_sync()
        events_found_count = len(scraped_events)
        User = get_user_model()
        all_users = User.objects.filter(is_active=True)

        for data in scraped_events:
            existing_event = Event.objects.filter(source_id=data['source_id']).first()
            is_new = False

            if not existing_event:
                # Nouvel événement découvert
                event = Event.objects.create(
                    source_id=data['source_id'],
                    title=data['title'],
                    event_type=data['event_type'],
                    description=data['description'],
                    date_event=data['date_event'],
                    location=data['location'],
                    supervisor=data['supervisor'],
                    url=data['url'],
                    image_url=data.get('image_url', ''),
                    is_simulated=False,
                    content_hash=data['content_hash'],
                )
                is_new = True
                new_events_count += 1
            elif existing_event.content_hash != data['content_hash']:
                # Événement existant modifié
                existing_event.title = data['title']
                existing_event.event_type = data['event_type']
                existing_event.description = data['description']
                existing_event.date_event = data['date_event']
                existing_event.location = data['location']
                existing_event.supervisor = data['supervisor']
                existing_event.url = data['url']
                existing_event.image_url = data.get('image_url', '')
                existing_event.content_hash = data['content_hash']
                existing_event.save()
                event = existing_event
                is_new = True  # Traiter comme nouveau pour réévaluer les alertes
            else:
                event = existing_event

            if is_new:
                # Évaluation des règles pour chaque utilisateur actif
                for user in all_users:
                    eval_res = evaluate_event_for_user(user, event)

                    if eval_res['is_blacklisted']:
                        # Règle liste noire correspondante -> aucun envoi
                        continue

                    if eval_res['is_favorite']:
                        # Règle favori correspondante
                        # 1. Vérifier si l'utilisateur a configuré ses identifiants avec consentement
                        credentials = getattr(user, 'unica_credentials', None)
                        attempt = None
                        if credentials and credentials.unica_identifier and credentials.auto_registration_consent:
                            attempt = RegistrationAttempt.objects.create(
                                event=event,
                                user=user,
                                status='en_attente'
                            )
                            # Déclencher la tâche Celery dédiée d'inscription
                            safe_dispatch_task(auto_register_task, user.id, event.id, attempt.id)

                        # 2. Envoyer la notification favori prioritaire
                        message = f"⭐ Événement FAVORIS détecté : {event.title} !"
                        safe_dispatch_task(
                            dispatch_notification_task,
                            user_id=user.id,
                            event_id=event.id,
                            message=message,
                            attempt_id=attempt.id if attempt else None
                        )
                    else:
                        # Notification standard
                        message = f"Nouvel événement disponible : {event.title}"
                        safe_dispatch_task(
                            dispatch_notification_task,
                            user_id=user.id,
                            event_id=event.id,
                            message=message
                        )

    except Exception as exc:
        logger.error(f"Erreur lors de l'exécution du scan : {exc}", exc_info=True)
        status = 'échec'
        error_msg = str(exc)

    duration = time.time() - start_time

    # Journalisation du passage dans ScanLog
    ScanLog.objects.create(
        execution_duration_seconds=round(duration, 2),
        events_found_count=events_found_count,
        new_events_count=new_events_count,
        status=status,
        error_message=error_msg
    )

    # Replanification automatique dynamique avec jitter et fuseau Europe/Paris
    if auto_reschedule:
        next_delay = calculate_next_scan_delay(settings_obj=settings_obj)
        logger.info(f"Scan terminé ({status}). Prochaine exécution programmée dans {next_delay} secondes.")
        try:
            scan_events_task.apply_async(countdown=next_delay, retry=False)
        except Exception as e:
            logger.info(f"Broker Celery non connecté pour la replanification ({e}).")

    return {
        'status': status,
        'events_found': events_found_count,
        'new_events': new_events_count,
        'duration': duration,
    }
