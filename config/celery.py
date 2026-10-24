import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('unicasport_notifier')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery task routing: dedicated rate-limited queue for notifications
app.conf.task_routes = {
    'apps.notifications.tasks.*': {'queue': 'notifications'},
    'apps.scraping.tasks.*': {'queue': 'celery'},
}

app.conf.beat_schedule = {
    # Une page par demi-heure en journée (heure de Paris, CELERY_TIMEZONE) : de 8h05 à 19h35
    'scan-events': {
        'task': 'apps.scraping.tasks.scan_events_task',
        'schedule': crontab(minute='5,35', hour='8-19'),
    },
    'purge-old-records': {
        'task': 'apps.scraping.tasks.purge_old_records_task',
        'schedule': 24 * 60 * 60,
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
