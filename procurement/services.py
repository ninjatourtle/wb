import logging
import re
from itertools import combinations
from urllib.parse import urljoin

from django.conf import settings
from django.db import transaction

from django.utils import timezone

from .models import (
    AuditEvent, Bid, BidFraudSignal, Contract, LoginEvent, Notification,
    ProcurementProtocol, Tender, TenderWinnerSelection,
)


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


def _normalized(value):
    return re.sub(r"[^a-z0-9а-яё]", "", (value or "").lower())


@transaction.atomic
def refresh_bid_fraud_signals(tender_id):
    """Rebuild affiliation signals for offers within one tender; signals warn but never block."""
    tender = Tender.objects.get(pk=tender_id)
    bids = list(Bid.objects.filter(tender=tender).select_related("supplier__profile__organization"))
    BidFraudSignal.objects.filter(tender=tender).delete()
    created = []
    for first, second in combinations(bids, 2):
        first_org, second_org = first.supplier.profile.organization, second.supplier.profile.organization
        checks = (
            (BidFraudSignal.Kind.EMAIL, _normalized(first_org.contact_email or first.supplier.email), _normalized(second_org.contact_email or second.supplier.email)),
            (BidFraudSignal.Kind.PHONE, _normalized(first_org.phone or first.supplier.profile.phone), _normalized(second_org.phone or second.supplier.profile.phone)),
            (BidFraudSignal.Kind.ADDRESS, _normalized(first_org.legal_address), _normalized(second_org.legal_address)),
        )
        first_ips = set(LoginEvent.objects.filter(user=first.supplier).exclude(ip_address__isnull=True).values_list("ip_address", flat=True))
        second_ips = set(LoginEvent.objects.filter(user=second.supplier).exclude(ip_address__isnull=True).values_list("ip_address", flat=True))
        first_fingerprints = set(LoginEvent.objects.filter(user=first.supplier, success=True).exclude(device_fingerprint="").values_list("device_fingerprint", flat=True))
        second_fingerprints = set(LoginEvent.objects.filter(user=second.supplier, success=True).exclude(device_fingerprint="").values_list("device_fingerprint", flat=True))
        shared_ips = first_ips & second_ips
        for kind, first_value, second_value in checks:
            if first_value and first_value == second_value:
                created.extend([
                    BidFraudSignal(tender=tender, bid=first, related_bid=second, kind=kind, value=first_value),
                    BidFraudSignal(tender=tender, bid=second, related_bid=first, kind=kind, value=first_value),
                ])
        for ip in shared_ips:
            created.extend([
                BidFraudSignal(tender=tender, bid=first, related_bid=second, kind=BidFraudSignal.Kind.LOGIN_IP, value=str(ip)),
                BidFraudSignal(tender=tender, bid=second, related_bid=first, kind=BidFraudSignal.Kind.LOGIN_IP, value=str(ip)),
            ])
        for fingerprint in first_fingerprints & second_fingerprints:
            created.extend([
                BidFraudSignal(tender=tender, bid=first, related_bid=second, kind=BidFraudSignal.Kind.DEVICE_FINGERPRINT, value=fingerprint),
                BidFraudSignal(tender=tender, bid=second, related_bid=first, kind=BidFraudSignal.Kind.DEVICE_FINGERPRINT, value=fingerprint),
            ])
    BidFraudSignal.objects.bulk_create(created, ignore_conflicts=True)
    return len(created)


@transaction.atomic
def finalize_pending_winner(tender_id):
    """Publish every preselected winner on the calendar day after the bid deadline."""
    # Lock only the tender row. `pending_winner` and the user links are nullable,
    # and PostgreSQL cannot lock the nullable side of an outer join.
    tender = Tender.objects.select_for_update(of=("self",)).select_related(
        "pending_winner__supplier__profile", "organization", "winner_selected_by", "owner"
    ).get(pk=tender_id)
    selections = list(tender.winner_selections.select_related("bid__supplier__profile").all())
    if not selections and tender.pending_winner_id:
        selection, _ = TenderWinnerSelection.objects.get_or_create(
            tender=tender,
            bid=tender.pending_winner,
            defaults={
                "selected_by": tender.winner_selected_by,
                "ranking_snapshot": tender.winner_ranking_snapshot,
            },
        )
        selections = [selection]
    if not selections or tender.status in {Tender.Status.COMPLETED, Tender.Status.CANCELLED}:
        return False
    if timezone.localdate() <= timezone.localdate(tender.deadline):
        return False
    winning_bids = [selection.bid for selection in selections if selection.bid.tender_id == tender.pk and selection.bid.status == Bid.Status.SUBMITTED]
    if not winning_bids:
        tender.pending_winner = None
        tender.save(update_fields=["pending_winner"])
        return False

    tender.bids.exclude(pk__in=[bid.pk for bid in winning_bids]).update(status=Bid.Status.REJECTED)
    Bid.objects.filter(pk__in=[bid.pk for bid in winning_bids]).update(status=Bid.Status.WINNER)
    tender.status = Tender.Status.COMPLETED
    tender.pending_winner = None
    tender.save(update_fields=["status", "pending_winner"])
    for bid in winning_bids:
        supplier_org = bid.supplier.profile.organization
        Contract.objects.get_or_create(
            winning_bid=bid,
            defaults={
                "number": f"WB-{tender.organization_id}-{tender.pk}-{bid.pk}",
                "tender": tender,
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
                "winners": [{"supplier": bid.supplier.profile.company_name, "price": str(bid.price)} for bid in winning_bids],
                "participants": tender.bids.count(),
                "completed_at": timezone.now().isoformat(),
                "preselected_at": [selection.selected_at.isoformat() for selection in selections],
                "ranking": {str(selection.bid_id): selection.ranking_snapshot for selection in selections},
            },
            "created_by": tender.winner_selected_by or tender.owner,
        },
    )
    for participant in tender.bids.select_related("supplier"):
        notify_user(participant.supplier, f"Результаты тендера {tender.number}", url=tender.get_absolute_url())
    AuditEvent.objects.create(
        user=tender.winner_selected_by or tender.owner,
        organization=tender.organization,
        action="winner.finalized",
        object_type="Tender",
        object_id=str(tender.pk),
        details={"winner_bid_ids": [bid.pk for bid in winning_bids]},
    )
    return True
