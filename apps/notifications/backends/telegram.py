import logging
from html import escape
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

        # HTML plutôt que Markdown : un « * » ou « _ » dans un titre ne casse plus le message
        text = (
            f"🔔 <b>UniCA Sport</b> : {escape(message)}\n\n"
            f"🏅 <b>{escape(event.title)}</b>\n"
            f"📅 Date : {escape(event.date_event or 'Non précisée')}\n"
            f"📍 Lieu : {escape(event.location or 'Non précisé')}\n"
            f"🔗 <a href=\"{escape(event.url)}\">Voir l'événement</a>\n"
        )
        if attempt:
            text += f"\n⚡ <b>Réservation automatique :</b> {escape(attempt.get_status_display())} (30 min)"

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
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
