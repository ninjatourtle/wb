import logging
from urllib.parse import urljoin

from django.conf import settings
from django.db import transaction

from django.utils import timezone

from .models import AuditEvent, Bid, Contract, Notification, ProcurementProtocol, Tender


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


@transaction.atomic
def finalize_pending_winner(tender_id):
    """Publish a preselected winner on the calendar day after the bid deadline."""
    tender = Tender.objects.select_for_update().select_related(
        "pending_winner__supplier__profile", "organization", "winner_selected_by"
    ).get(pk=tender_id)
    bid = tender.pending_winner
    if not bid or tender.status in {Tender.Status.COMPLETED, Tender.Status.CANCELLED}:
        return False
    if timezone.localdate() <= timezone.localdate(tender.deadline):
        return False
    if bid.tender_id != tender.pk or bid.status != Bid.Status.SUBMITTED:
        tender.pending_winner = None
        tender.save(update_fields=["pending_winner"])
        return False

    tender.bids.update(status=Bid.Status.REJECTED)
    bid.status = Bid.Status.WINNER
    bid.save(update_fields=["status"])
    tender.status = Tender.Status.COMPLETED
    tender.pending_winner = None
    tender.save(update_fields=["status", "pending_winner"])
    supplier_org = bid.supplier.profile.organization
    Contract.objects.get_or_create(
        tender=tender,
        defaults={
            "number": f"WB-{tender.organization_id}-{tender.pk}",
            "winning_bid": bid,
            "customer": tender.organization,
            "supplier": supplier_org,
            "amount": bid.price,
        },
    )
    ProcurementProtocol.objects.get_or_create(
        tender=tender,
        kind=ProcurementProtocol.Kind.RESULTS,
        defaults={
            "number": f"WB-RESULT-{tender.organization_id}-{tender.pk}",
            "data": {
                "winner": bid.supplier.profile.company_name,
                "winning_price": str(bid.price),
                "participants": tender.bids.count(),
                "completed_at": timezone.now().isoformat(),
                "preselected_at": tender.winner_selected_at.isoformat() if tender.winner_selected_at else None,
                "ranking": tender.winner_ranking_snapshot,
            },
            "created_by": tender.winner_selected_by or tender.owner,
        },
    )
    for participant in tender.bids.select_related("supplier"):
        notify_user(participant.supplier, f"Результаты тендера {tender.number}", url=tender.get_absolute_url())
    AuditEvent.objects.create(
        user=tender.winner_selected_by,
        organization=tender.organization,
        action="winner.finalized",
        object_type="Bid",
        object_id=str(bid.pk),
        details={"tender_id": tender.pk, "price": str(bid.price)},
    )
    return True
