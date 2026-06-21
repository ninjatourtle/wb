import logging
from urllib.parse import urljoin

from django.conf import settings
from django.db import transaction

from .models import Notification


logger = logging.getLogger(__name__)


def notify_user(user, title, message="", url=""):
    notification = Notification.objects.create(user=user, title=title, message=message, url=url)
    if user.email and settings.EMAIL_NOTIFICATIONS_ENABLED:
        transaction.on_commit(
            lambda: _queue_notification_email(user.email, title, message or title, url)
        )
    return notification


def notification_email_body(message, url):
    body = message
    if url:
        body = f"{body}\n\nСсылка: {urljoin(f'{settings.SITE_URL}/', url)}"
    return body


def _queue_notification_email(email, title, message, url):
    try:
        from .tasks import send_notification_email

        send_notification_email.delay(email, title, message, url)
    except Exception:
        logger.exception("Failed to queue notification email to %s", email)
