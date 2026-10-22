import logging
from django.core.mail import send_mail
from django.conf import settings
from .base import NotificationBackend

logger = logging.getLogger(__name__)


def get_mail_settings():
    """Expéditeur et connexion SMTP : ServerSettings (admin) s'ils sont renseignés, sinon settings Django."""
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'notifications@sport-notifier.fr')
    connection = None
    try:
        from apps.scraping.models import ServerSettings
        server_settings = ServerSettings.get_solo()
        if server_settings.smtp_from_email:
            from_email = server_settings.smtp_from_email
        if server_settings.smtp_host and server_settings.smtp_user:
            from django.core.mail import get_connection
            connection = get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                host=server_settings.smtp_host,
                port=server_settings.smtp_port,
                username=server_settings.smtp_user,
                password=server_settings.smtp_password,
                use_tls=server_settings.smtp_use_tls,
                fail_silently=False,
            )
    except Exception:
        pass
    return from_email, connection


class EmailBackend(NotificationBackend):
    def send(self, user, event, message: str, attempt=None) -> bool:
        if not user.email:
            logger.warning(f"EmailBackend: Pas d'adresse email pour l'utilisateur {user}")
            return False

        subject = f"[UniCA Sport] {event.title}"
        if attempt:
            subject = f"[UniCA Sport - Réservation] {event.title}"

        body = (
            f"Bonjour,\n\n"
            f"{message}\n\n"
            f"Détails de l'événement :\n"
            f"- Titre : {event.title}\n"
            f"- Type : {event.event_type}\n"
            f"- Date/Heure : {event.date_event}\n"
            f"- Lieu : {event.location}\n"
            f"- Lien direct : {event.url}\n\n"
        )
        if attempt:
            body += (
                f"Statut de l'inscription : {attempt.get_status_display()}\n"
                f"Attention : Vous disposez de 30 minutes pour valider votre place si l'inscription a réussi !\n\n"
            )

        body += "Cordialement,\nVotre notificateur UniCA Sport"

        from_email, connection = get_mail_settings()

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=from_email,
                recipient_list=[user.email],
                connection=connection,
                fail_silently=False,
            )
            logger.info(f"EmailBackend: Notification envoyée avec succès à {user.email}")
            return True
        except Exception as e:
            logger.error(f"EmailBackend: Erreur d'envoi à {user.email} : {e}")
            return False
