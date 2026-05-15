import logging

try:
	from .celery import app as celery_app
except Exception as e:
	# Avoid crashing the whole Django import process if Celery isn't
	# available in the environment (helps surface clearer logs in prod).
	celery_app = None
	logging.getLogger(__name__).exception("Failed to import Celery app; celery_app set to None: %s", e)

__all__ = ('celery_app',)
