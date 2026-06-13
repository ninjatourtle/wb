try:
    from celery import shared_task
except ModuleNotFoundError:
    def shared_task(func):
        return func
from django.utils import timezone

from .models import Tender
from .services import notify_user


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
