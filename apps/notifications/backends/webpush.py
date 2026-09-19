import json
import logging
from django.conf import settings
from pywebpush import webpush, WebPushException
from .base import NotificationBackend

logger = logging.getLogger(__name__)

class WebPushBackend(NotificationBackend):
    """
    Backend pour les notifications Push Web standards via pywebpush et VAPID.
    Pas de dépendance à Firebase.
    """
    def send(self, user, event, message: str, attempt=None) -> bool:
        subscriptions = user.push_subscriptions.all()
        if not subscriptions.exists():
            logger.info(f"WebPushBackend: Aucun abonnement push actif pour {user.email}")
            return False

        vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', '')
        vapid_admin_email = getattr(settings, 'VAPID_ADMIN_EMAIL', 'mailto:admin@example.com')

        if not vapid_private_key:
            logger.warning("WebPushBackend: VAPID_PRIVATE_KEY non configurée.")
            return False

        payload_data = {
            "title": f"UniCA Sport : {event.title}",
            "body": f"{message}\nLieu : {event.location or 'UniCA'} | {event.date_event or ''}",
            "url": event.url,
            "tag": f"unica-event-{event.source_id}",
            "icon": "/static/icons/icon-192.png",
        }
        if attempt:
            payload_data["body"] += f"\nRéservation : {attempt.get_status_display()}"

        payload_str = json.dumps(payload_data)
        success_count = 0

        for sub in subscriptions:
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth,
                }
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=payload_str,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={"sub": vapid_admin_email},
                    ttl=86400
                )
                success_count += 1
            except WebPushException as ex:
                logger.error(f"WebPushBackend: Erreur lors de l'envoi au device : {ex}")
                # Si le device a révoqué la souscription (410 Gone ou 404)
                if ex.response and ex.response.status_code in [404, 410]:
                    logger.info(f"WebPushBackend: Suppression de l'abonnement expiré {sub.endpoint[:30]}...")
                    sub.delete()
            except Exception as e:
                logger.error(f"WebPushBackend: Exception inattendue : {e}")

        return success_count > 0
