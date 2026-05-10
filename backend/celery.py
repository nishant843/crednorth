import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("backend")

# Load settings from Django settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")

# Explicitly ensure broker/backend loaded
app.conf.broker_url = os.getenv("REDIS_URL")
app.conf.result_backend = os.getenv("REDIS_URL")

app.autodiscover_tasks()

print("CELERY BROKER:", app.conf.broker_url)