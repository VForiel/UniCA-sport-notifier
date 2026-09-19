import logging
import requests
from django.conf import settings
from .base import NotificationBackend

logger = logging.getLogger(__name__)

class TelegramBackend(NotificationBackend):
    def send(self, user, event, message: str, attempt=None) -> bool:
        pref = user.notification_preferences.filter(channel='telegram', is_active=True).first()
        if not pref or not pref.config.get('chat_id'):
            logger.warning(f"TelegramBackend: Pas de chat_id Telegram pour {user.email}")
            return False

        chat_id = pref.config.get('chat_id')

        # Retrieve bot token from ServerSettings if present, else django settings
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        try:
            from apps.scraping.models import ServerSettings
            server_settings = ServerSettings.get_solo()
            if server_settings.telegram_bot_token:
                bot_token = server_settings.telegram_bot_token
        except Exception:
            pass

        if not bot_token:
            logger.error("TelegramBackend: Aucun token de bot Telegram configuré.")
            return False

        text = (
            f"🔔 *UniCA Sport* : {message}\n\n"
            f"🏅 *{event.title}*\n"
            f"📅 Date : {event.date_event or 'Non précisée'}\n"
            f"📍 Lieu : {event.location or 'Non précisé'}\n"
            f"🔗 [Voir l'événement]({event.url})\n"
        )
        if attempt:
            text += f"\n⚡ *Réservation automatique :* {attempt.get_status_display()} (30 min)"

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"TelegramBackend: Message envoyé avec succès à {user.email}")
                return True
            else:
                logger.error(f"TelegramBackend: Erreur {resp.status_code} : {resp.text}")
                return False
        except Exception as e:
            logger.error(f"TelegramBackend: Exception lors de l'envoi : {e}")
            return False
