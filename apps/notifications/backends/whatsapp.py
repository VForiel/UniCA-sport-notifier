import logging
import requests
from django.conf import settings
from .base import NotificationBackend

logger = logging.getLogger(__name__)

class WhatsAppBackend(NotificationBackend):
    """
    Backend pour l'API Cloud officielle de Meta (WhatsApp Business Platform).
    Respecte les quotas et conditions d'utilisation sans dépendance tierce instable.
    """
    def send(self, user, event, message: str, attempt=None) -> bool:
        pref = user.notification_preferences.filter(channel='whatsapp', is_active=True).first()
        if not pref or not pref.config.get('phone_number'):
            logger.warning(f"WhatsAppBackend: Numéro de téléphone manquant pour {user.email}")
            return False

        recipient_phone = pref.config.get('phone_number').replace(" ", "").replace("-", "")

        api_token = getattr(settings, 'WHATSAPP_API_TOKEN', '')
        phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')

        try:
            from apps.scraping.models import ServerSettings
            server_settings = ServerSettings.get_solo()
            if server_settings.whatsapp_api_token:
                api_token = server_settings.whatsapp_api_token
            if server_settings.whatsapp_phone_number_id:
                phone_number_id = server_settings.whatsapp_phone_number_id
        except Exception:
            pass

        if not api_token or not phone_number_id:
            logger.error("WhatsAppBackend: Identifiants Meta Cloud API non configurés.")
            return False

        text_body = (
            f"🔔 *UniCA Sport* : {message}\n\n"
            f"🏅 *{event.title}*\n"
            f"📅 Date : {event.date_event}\n"
            f"📍 Lieu : {event.location}\n"
            f"🔗 {event.url}"
        )
        if attempt:
            text_body += f"\n⚡ Réservation : {attempt.get_status_display()}"

        url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "text",
            "text": {"body": text_body}
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code in [200, 201]:
                logger.info(f"WhatsAppBackend: Message envoyé avec succès à {recipient_phone}")
                return True
            else:
                logger.error(f"WhatsAppBackend: Erreur {resp.status_code} Meta : {resp.text}")
                return False
        except Exception as e:
            logger.error(f"WhatsAppBackend: Exception lors de l'envoi : {e}")
            return False
