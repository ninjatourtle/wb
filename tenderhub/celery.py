import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tenderhub.settings")
app = Celery("tenderhub")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
