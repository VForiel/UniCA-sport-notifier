import time
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.events.models import Event
from apps.events.services import evaluate_event_for_user
from apps.notifications.backends.email import EmailBackend
from apps.notifications.backends.discord import DiscordWebhookBackend
from apps.notifications.backends.telegram import TelegramBackend
from apps.notifications.backends.whatsapp import WhatsAppBackend
from apps.notifications.backends.webpush import WebPushBackend
from apps.scraping.parsers import calculate_event_hash

BACKENDS_MAP = {
    'email': EmailBackend,
    'discord_webhook': DiscordWebhookBackend,
    'telegram': TelegramBackend,
    'whatsapp': WhatsAppBackend,
    'push': WebPushBackend,
}

class Command(BaseCommand):
    help = "Simule la détection d'un nouvel événement pour tester l'envoi en direct des notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            '--title',
            type=str,
            default='Sortie KAYAK et Calanques [TEST SIMULATION]',
            help="Titre de l'événement simulé",
        )
        parser.add_argument(
            '--type',
            type=str,
            default='Sortie',
            help="Type d'activité (Sortie, Tournoi, Stage, etc.)",
        )
        parser.add_argument(
            '--location',
            type=str,
            default='Base Nautique de Valrose / Mer',
            help="Lieu de l'activité",
        )
        parser.add_argument(
            '--user',
            type=str,
            help="Adresse email de l'utilisateur à cibler (par défaut tous les utilisateurs actifs)",
        )
        parser.add_argument(
            '--favorite',
            action='store_true',
            help="Force la qualification de l'événement en tant que Favori",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        title = options['title']
        event_type = options['type']
        location = options['location']
        target_email = options.get('user')
        force_favorite = options.get('favorite', False)

        import uuid
        source_id = f"sim_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        date_event = "Demain 10:00 - 17:00"
        desc = (
            "Ceci est un événement de TEST simulé pour vérifier le bon fonctionnement "
            "de vos canaux de notification (Push Web, Discord, Telegram, WhatsApp, Email). "
            "Aucune inscription réelle sur UniCA Sport n'a lieu."
        )

        content_hash = calculate_event_hash(source_id, title, event_type, date_event, location, desc)

        self.stdout.write(self.style.NOTICE("=" * 65))
        self.stdout.write(self.style.SUCCESS("SIMULATION D'UN NOUVEL ÉVÉNEMENT UNICA SPORT"))
        self.stdout.write(self.style.NOTICE("=" * 65))

        event = Event.objects.create(
            source_id=source_id,
            title=title,
            event_type=event_type,
            date_event=date_event,
            location=location,
            supervisor="Testeur Automatique",
            description=desc,
            url=f"https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement#event-{source_id}",
            image_url="https://sport.univ-cotedazur.fr/media/cache/thumb_large_big/upload/public/image/6a17e6307f445452066731.png",
            is_simulated=True,
            content_hash=content_hash,
        )

        self.stdout.write(f"Événement créé en base : {event.title} (ID: {event.source_id})")

        if target_email:
            users = User.objects.filter(email=target_email, is_active=True)
            if not users.exists():
                self.stdout.write(self.style.ERROR(f"Aucun utilisateur actif trouvé avec l'email '{target_email}'."))
                return
        else:
            users = User.objects.filter(is_active=True)

        for user in users:
            self.stdout.write(f"\nTraitement pour l'utilisateur : {user.email}")
            eval_res = evaluate_event_for_user(user, event)
            is_fav = force_favorite or eval_res['is_favorite']
            is_black = eval_res['is_blacklisted'] and not force_favorite

            if is_black:
                self.stdout.write(self.style.WARNING("  -> Ignoré car correspond à une règle de Liste Noire."))
                continue

            msg_prefix = "⭐ [SIMULATION FAVORIS]" if is_fav else "🔔 [SIMULATION TEST]"
            message = f"{msg_prefix} Nouvel événement détecté : {event.title}"

            active_prefs = user.notification_preferences.filter(is_active=True)
            if not active_prefs.exists():
                self.stdout.write(self.style.NOTICE("  -> Aucun canal spécifique actif : envoi d'un email de test par défaut."))
                backend = EmailBackend()
                res = backend.send(user, event, message)
                self.stdout.write(f"     * Email ({user.email}) : {'SUCCÈS' if res else 'ÉCHEC'}")
                continue

            for pref in active_prefs:
                backend_cls = BACKENDS_MAP.get(pref.channel)
                if backend_cls:
                    backend = backend_cls()
                    res = backend.send(user, event, message)
                    status_text = self.style.SUCCESS("SUCCÈS") if res else self.style.ERROR("ÉCHEC / NON CONFIGURÉ")
                    self.stdout.write(f"     * Canal {pref.get_channel_display()} : {status_text}")

        self.stdout.write("\n" + self.style.SUCCESS("Simulation terminée."))
