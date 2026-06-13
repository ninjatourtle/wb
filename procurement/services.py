import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .models import Notification


logger = logging.getLogger(__name__)


def notify_user(user, title, message="", url=""):
    notification = Notification.objects.create(user=user, title=title, message=message, url=url)
    if user.email:
        transaction.on_commit(
            lambda: _send_email_safely(user.email, title, message or title, url)
        )
    return notification


def _send_email_safely(email, title, message, url):
    body = message
    if url:
        body = f"{body}\n\nСсылка: {url}"
    try:
        send_mail(title, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception:
        logger.exception("Failed to send notification email to %s", email)
