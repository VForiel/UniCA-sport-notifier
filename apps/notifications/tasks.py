import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from apps.events.models import Event, RegistrationAttempt
from .backends.email import EmailBackend
from .backends.discord import DiscordWebhookBackend
from .backends.telegram import TelegramBackend
from .backends.whatsapp import WhatsAppBackend
from .backends.webpush import WebPushBackend

logger = logging.getLogger(__name__)

BACKENDS_MAP = {
    'email': EmailBackend,
    'discord_webhook': DiscordWebhookBackend,
    'telegram': TelegramBackend,
    'whatsapp': WhatsAppBackend,
    'push': WebPushBackend,
}

@shared_task(
    bind=True,
    queue='notifications',
    rate_limit='30/m',
    max_retries=3,
    default_retry_delay=10
)
def dispatch_notification_task(self, user_id: int, event_id: int, message: str, attempt_id: int = None):
    """
    Tâche Celery pour l'envoi asynchrone et rate-limité des notifications.
    Protège les quotas des APIs externes (Discord, Meta WhatsApp).
    """
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        event = Event.objects.get(id=event_id)
        attempt = RegistrationAttempt.objects.get(id=attempt_id) if attempt_id else None
    except Exception as e:
        logger.error(f"dispatch_notification_task: Données introuvables : {e}")
        return False

    active_prefs = user.notification_preferences.filter(is_active=True)
    if not active_prefs.exists():
        # Si aucune préférence n'a été spécifiée mais que l'email existe, fallback email par défaut
        backend = EmailBackend()
        backend.send(user, event, message, attempt=attempt)
        return True

    success_all = True
    for pref in active_prefs:
        backend_cls = BACKENDS_MAP.get(pref.channel)
        if backend_cls:
            try:
                backend = backend_cls()
                res = backend.send(user, event, message, attempt=attempt)
                if not res:
                    success_all = False
            except Exception as exc:
                logger.error(f"Erreur backend {pref.channel} pour {user.email}: {exc}")
                success_all = False

    return success_all
