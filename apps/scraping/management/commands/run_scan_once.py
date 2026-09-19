from django.core.management.base import BaseCommand
from apps.scraping.tasks import scan_events_task

class Command(BaseCommand):
    help = "Exécute un cycle de scan UniCA Sport immédiatement et de façon synchrone."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reschedule',
            action='store_true',
            help="Si spécifié, déclenche également la replanification automatique après ce scan.",
        )

    def handle(self, *args, **options):
        reschedule = options.get('reschedule', False)
        self.stdout.write("Lancement du scan UniCA Sport...")
        result = scan_events_task(auto_reschedule=reschedule)
        self.stdout.write(self.style.SUCCESS(f"Résultat du scan : {result}"))
