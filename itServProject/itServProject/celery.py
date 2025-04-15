# itServProject/celery.py
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'itServProject.settings')

app = Celery('itServProject')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.conf.beat_schedule = {
    'detect-pointage-anomalies': {
        'task': 'itServ.tasks.detect_pointage_anomalies',
        'schedule': crontab(minute='*/2'),  # Toutes les 2 minutes
    },
}