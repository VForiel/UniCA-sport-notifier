import logging
import requests
from .base import NotificationBackend

logger = logging.getLogger(__name__)

class DiscordWebhookBackend(NotificationBackend):
    def send(self, user, event, message: str, attempt=None) -> bool:
        pref = user.notification_preferences.filter(channel='discord_webhook', is_active=True).first()
        if not pref or not pref.config.get('webhook_url'):
            logger.warning(f"DiscordWebhookBackend: Pas d'URL webhook pour {user.email}")
            return False

        webhook_url = pref.config.get('webhook_url')

        color = 0x00A86B if attempt and attempt.status == 'réussi' else 0x3498DB
        if attempt and attempt.status == 'échoué':
            color = 0xE74C3C

        fields = [
            {"name": "Date / Heure", "value": event.date_event or "Non précisée", "inline": True},
            {"name": "Lieu", "value": event.location or "Non précisé", "inline": True},
            {"name": "Type", "value": event.event_type or "Événement", "inline": True},
        ]

        if attempt:
            fields.append({
                "name": "Statut réservation auto",
                "value": f"**{attempt.get_status_display()}** (Créneau 30 min)",
                "inline": False
            })
            if attempt.error_message:
                fields.append({
                    "name": "Diagnostic",
                    "value": attempt.error_message[:250],
                    "inline": False
                })

        discord_user_id = str(pref.config.get('discord_user_id', '')).strip()
        ping_mode = pref.config.get('discord_ping_mode', 'none')  # 'none', 'favorite_only', 'all'

        # Détermination si l'événement est un favori
        is_favorite = False
        if attempt is not None or 'FAVORIS' in message.upper():
            is_favorite = True
        else:
            try:
                from apps.events.services import evaluate_event_for_user
                is_favorite = evaluate_event_for_user(user, event).get('is_favorite', False)
            except Exception:
                pass

        # Gestion du ping / de la mention utilisateur Discord
        should_ping = False
        if discord_user_id:
            if ping_mode == 'all':
                should_ping = True
            elif ping_mode == 'favorite_only' and is_favorite:
                should_ping = True

        mention_str = f"<@{discord_user_id}> " if should_ping else ""
        content = f"{mention_str}🔔 **UniCA Sport** : {message}"

        embed = {
            "title": event.title,
            "url": event.url,
            "description": (event.description[:300] + "...") if len(event.description) > 300 else (event.description or "Pas de description"),
            "color": color,
            "fields": fields,
            "footer": {"text": "UniCA Sport Notifier • Alerte personnalisée"}
        }

        # Intégration de l'image de l'événement dans le webhook Discord
        if getattr(event, 'image_url', None):
            embed["image"] = {"url": event.image_url}

        payload = {
            "content": content,
            "embeds": [embed]
        }

        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code in [200, 204]:
                logger.info(f"DiscordWebhookBackend: Envoyé avec succès à {user.email}")
                return True
            else:
                logger.error(f"DiscordWebhookBackend: Code {resp.status_code} reçu de Discord : {resp.text}")
                return False
        except Exception as e:
            logger.error(f"DiscordWebhookBackend: Exception lors de l'envoi : {e}")
            return False
