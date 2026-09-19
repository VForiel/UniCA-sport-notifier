import time
import logging
from django.core.management.base import BaseCommand
from apps.scraping.tasks import scan_events_task, calculate_next_scan_delay
from apps.scraping.models import ServerSettings

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Boucle de scan continue en direct pour l'environnement de développement local (respecte la bascule jour/nuit et le jitter sans exiger Redis/Celery)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Démarrage de la boucle de scan continue UniCA Sport..."))
        self.stdout.write("Appuyez sur Ctrl+C pour interrompre la surveillance.")

        while True:
            try:
                settings_obj = ServerSettings.get_solo()
                delay = calculate_next_scan_delay(settings_obj=settings_obj)
                self.stdout.write(f"[{time.strftime('%H:%M:%S')}] Lancement du scan Playwright...")
                result = scan_events_task(auto_reschedule=False)
                self.stdout.write(
                    f"[{time.strftime('%H:%M:%S')}] Scan terminé : {result.get('events_found', 0)} trouvé(s), "
                    f"{result.get('new_events', 0)} nouveau(x) ({result.get('status', 'inconnu')})."
                )
                self.stdout.write(f"Prochain scan prévu dans {delay} secondes (~{round(delay / 60, 1)} min)...")
                time.sleep(delay)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\nArrêt de la boucle de scan."))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur durant le cycle de scan : {e}"))
                time.sleep(15)
