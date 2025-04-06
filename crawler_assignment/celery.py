# your_project/celery.py

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crawler_assignment.settings')

app = Celery('crawler_assignment')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
