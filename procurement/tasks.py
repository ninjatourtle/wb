try:
    from celery import shared_task
except ModuleNotFoundError:
    def shared_task(func):
        func.delay = func
        return func
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail

from .models import SupplierDocument, Tender, TenderImportRun, TenderImportSource
from .imports import run_source_sync, sync_active_sources
from .services import notify_user
from .services import notification_email_body


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_notification_email(email, title, message, url=""):
    return send_mail(
        title,
        notification_email_body(message, url),
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )


@shared_task
def close_expired_tenders():
    tenders = Tender.objects.filter(status=Tender.Status.PUBLISHED, deadline__lte=timezone.now())
    count = 0
    for tender in tenders:
        tender.status = Tender.Status.REVIEW
        tender.save(update_fields=["status"])
        notify_user(tender.owner, f"Прием заявок завершен: {tender.number}", url=tender.get_absolute_url())
        count += 1
    return count


@shared_task
def sync_external_tenders():
    return sync_active_sources()


@shared_task
def sync_external_tender_source(source_id, run_id):
    source = TenderImportSource.objects.get(pk=source_id)
    run = TenderImportRun.objects.get(pk=run_id, source=source)
    run_source_sync(source, run=run)
    return run.result or {"error": run.error}


@shared_task
def check_expiring_supplier_documents():
    """Notify suppliers before a licensing or registration document becomes invalid."""
    from datetime import timedelta

    deadline = timezone.localdate() + timedelta(days=30)
    documents = SupplierDocument.objects.filter(
        expires_at__isnull=False,
        expires_at__lte=deadline,
        expiry_notice_sent_at__isnull=True,
    ).select_related("organization")
    notified = 0
    for document in documents:
        users = document.organization.profiles.select_related("user")
        state = "истек" if document.expires_at < timezone.localdate() else "истекает"
        for profile in users:
            notify_user(
                profile.user,
                f"Срок документа {state}: {document.title}",
                f"Документ компании «{document.organization.name}» действует до {document.expires_at:%d.%m.%Y}.",
                "/company/",
            )
            notified += 1
        document.expiry_notice_sent_at = timezone.now()
        document.save(update_fields=["expiry_notice_sent_at"])
    return notified
