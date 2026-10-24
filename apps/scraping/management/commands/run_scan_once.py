from django.core.management.base import BaseCommand
from apps.scraping.tasks import scan_events_task

class Command(BaseCommand):
    help = "Exécute un cycle de scan UniCA Sport immédiatement et de façon synchrone."

    def handle(self, *args, **options):
        self.stdout.write("Lancement du scan UniCA Sport...")
        result = scan_events_task()
        self.stdout.write(self.style.SUCCESS(f"Résultat du scan : {result}"))
