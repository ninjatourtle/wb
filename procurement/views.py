import csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from pathlib import Path
from functools import wraps
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db import connection
from django.db.models import Count, Min, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    AnswerForm, BidForm, EmployeeInviteForm, OrganizationForm,
    QuestionForm, RegisterForm, SupplierDocumentForm, TenderDocumentForm,
    TenderForm, TenderLotForm, TenderTemplateForm, bid_lot_formset,
)
from .models import (
    AuditEvent, Bid, BidFraudSignal, BidLot, Contract, LoginEvent, Membership, Organization, ProcurementProtocol, Profile,
    Question, SupplierApplication, SupplierDocument, Tender, TenderApproval, TenderDocument,
    TenderImportRun, TenderImportSource, TenderNumberSequence, TenderTemplate, TenderTemplateLot, TenderLot,
    TenderWinnerSelection,
)
from .services import notify_user, refresh_bid_fraud_signals


def audit(user, action, obj=None, organization=None, **details):
    profile = getattr(user, "profile", None) if user and user.is_authenticated else None
    organization = organization or (getattr(obj, "organization", None) if obj else None)
    if not organization and obj:
        organization = getattr(obj, "customer", None)
    if not organization and obj and hasattr(obj, "tender"):
        organization = obj.tender.organization
    AuditEvent.objects.create(
        user=user if user and user.is_authenticated else None,
        organization=organization or getattr(profile, "organization", None),
        action=action,
        object_type=obj.__class__.__name__ if obj else "",
        object_id=str(obj.pk) if obj else "",
        details=details,
    )


def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(request, *args, **kwargs):
            profile = getattr(request.user, "profile", None)
            if not profile or profile.role != role:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def membership_role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(request, *args, **kwargs):
            profile = getattr(request.user, "profile", None)
            if not profile or profile.role != Profile.Role.CUSTOMER:
                raise PermissionDenied
            if not Membership.objects.filter(
                user=request.user,
                is_active=True,
                role__in=roles,
            ).exists():
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def accessible_customer_organizations(user, roles=None):
    memberships = Membership.objects.filter(
        user=user, is_active=True, organization__kind=Organization.Kind.CUSTOMER
    )
    if roles:
        memberships = memberships.filter(role__in=roles)
    return Organization.objects.filter(memberships__in=memberships).distinct()


def selected_organization(request, organizations):
    organization_id = request.GET.get("organization") or request.POST.get("organization")
    if organization_id:
        return organizations.filter(pk=organization_id).first()
    return None


def generate_tender_number():
    year = timezone.now().year
    sequence, _ = TenderNumberSequence.objects.select_for_update().get_or_create(year=year)
    while True:
        sequence.last_value += 1
        number = f"WB-{year}-{sequence.last_value:06d}"
        if not Tender.objects.filter(number=number).exists():
            sequence.save(update_fields=["last_value"])
            return number


def manageable_tender_or_404(user, pk):
    tender = get_object_or_404(Tender, pk=pk)
    if not tender.user_can_manage(user):
        raise PermissionDenied
    return tender


def supplier_application_for_tender(user, tender):
    profile = getattr(user, "profile", None)
    if not profile or not profile.organization_id or not tender.organization_id:
        return None
    return SupplierApplication.objects.filter(
        organization_id=profile.organization_id,
        customer_id=tender.organization_id,
    ).first()


def comparison_rows(tender):
    """Build a live recommendation from submitted offers without persisting scores."""
    bids = list(
        tender.bids.all()
        .select_related("supplier__profile")
        .prefetch_related("lot_offers__lot")
        .order_by("submitted_at", "pk")
    )
    if not bids:
        return []

    best_price = min(bid.price for bid in bids)
    shortest_delivery = min(bid.delivery_days for bid in bids)
    longest_warranty = max(bid.warranty_months for bid in bids)
    rows = []
    for bid in bids:
        price_score = Decimal("60") if bid.price == best_price else (
            (best_price / bid.price * Decimal("60")) if bid.price else Decimal("0")
        )
        delivery_score = Decimal("25") if bid.delivery_days == shortest_delivery else (
            Decimal(shortest_delivery) / Decimal(bid.delivery_days) * Decimal("25")
        )
        warranty_score = (
            Decimal(bid.warranty_months) / Decimal(longest_warranty) * Decimal("15")
            if longest_warranty else Decimal("0")
        )
        score = (price_score + delivery_score + warranty_score).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        rows.append({
            "bid": bid,
            "price_score": price_score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "delivery_score": delivery_score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "warranty_score": warranty_score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "score": score,
            "is_best_price": bid.price == best_price,
            "is_fastest_delivery": bid.delivery_days == shortest_delivery,
            "is_best_warranty": bool(longest_warranty and bid.warranty_months == longest_warranty),
        })
    rows.sort(key=lambda row: row["score"], reverse=True)
    previous_score = None
    rank = 0
    for index, row in enumerate(rows, start=1):
        if row["score"] != previous_score:
            rank = index
            previous_score = row["score"]
        row["rank"] = rank
    return rows


def home(request):
    open_tenders = Tender.objects.filter(
        status=Tender.Status.PUBLISHED, deadline__gt=timezone.now()
    )
    tenders = open_tenders.select_related("owner__profile", "organization").annotate(
        bid_count=Count("bids")
    ).order_by("-created_at", "-pk")[:6]
    completed_tenders = Tender.objects.filter(status=Tender.Status.COMPLETED).annotate(
        winner_price=Min("bids__price", filter=Q(bids__status=Bid.Status.WINNER))
    )
    savings = sum(
        (tender.budget - tender.winner_price)
        for tender in completed_tenders
        if tender.winner_price is not None
    )
    stats = {
        "open": open_tenders.count(),
        "suppliers": SupplierApplication.objects.filter(status=SupplierApplication.Status.APPROVED).count(),
        "completed": completed_tenders.count(),
        "savings": savings,
    }
    category_labels = dict(Tender.Category.choices)
    category_stats = [
        {"value": row["category"], "label": category_labels[row["category"]], "count": row["count"]}
        for row in open_tenders.values("category").annotate(count=Count("pk")).order_by("-count")
    ]
    category_stats.sort(key=lambda item: (item["value"] != Tender.Category.GOODS, -item["count"]))
    return render(request, "procurement/home.html", {
        "tenders": tenders, "stats": stats, "category_stats": category_stats,
    })


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        audit(user, "account.registered")
        messages.success(request, "Компания зарегистрирована.")
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


def tender_list(request):
    tenders = Tender.objects.filter(
        status=Tender.Status.PUBLISHED, deadline__gt=timezone.now()
    ).select_related("owner__profile", "organization", "import_record")
    query, category = request.GET.get("q", "").strip(), request.GET.get("category", "")
    procedure, price_to = request.GET.get("procedure", ""), request.GET.get("price_to", "")
    source = request.GET.get("source", "")
    if category not in Tender.Category.values:
        category = ""
    if procedure not in Tender.Procedure.values:
        procedure = ""
    if source not in {"", "local", "imported"}:
        source = ""
    if query:
        tenders = tenders.filter(Q(title__icontains=query) | Q(number__icontains=query) | Q(description__icontains=query))
    if category:
        tenders = tenders.filter(category=category)
    if procedure:
        tenders = tenders.filter(procedure=procedure)
    if source == "imported":
        tenders = tenders.filter(import_record__isnull=False)
    elif source == "local":
        tenders = tenders.filter(import_record__isnull=True)
    if price_to:
        try:
            tenders = tenders.filter(budget__lte=price_to)
        except ValueError:
            pass
    tenders = tenders.annotate(bid_count=Count("bids")).order_by("deadline", "-created_at")
    page = Paginator(tenders, 12).get_page(request.GET.get("page"))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    return render(request, "procurement/tender_list.html", {
        "tenders": page, "page_obj": page, "query": query, "category": category,
        "procedure": procedure, "price_to": price_to, "source": source,
        "categories": Tender.Category.choices, "procedures": Tender.Procedure.choices,
        "pagination_query": pagination_params.urlencode(),
    })


def tender_detail(request, pk):
    tender = get_object_or_404(
        Tender.objects.select_related("owner__profile", "organization", "import_record__source"),
        pk=pk,
    )
    profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
    can_manage = tender.user_can_manage(request.user)
    can_review = tender.user_can_review(request.user)
    if tender.status in {Tender.Status.DRAFT, Tender.Status.APPROVAL} and not can_review:
        raise Http404
    own_bid = Bid.objects.filter(tender=tender, supplier=request.user).first() if profile and profile.role == Profile.Role.SUPPLIER else None
    can_see_bids = can_manage and tender.bids.exists()
    ranking = comparison_rows(tender) if can_manage else []
    best_price = tender.best_price if tender.procedure == Tender.Procedure.AUCTION else None
    imported_data = tender.import_record.raw_data if hasattr(tender, "import_record") else {}
    details = imported_data.get("details", {})
    position_groups = details.get("groups", [])
    position_specification = None
    if imported_data and not tender.lots.exists():
        group_params = position_groups[0].get("params", {}) if position_groups else {}
        position_specification = {
            "description": "Участники указывают цену предложения без детализации по позициям.",
            "permit_up_down": group_params.get("permitUpDown"),
            "step": group_params.get("reductionStep"),
            "expected_price": group_params.get("expectedPrice"),
        }
    return render(request, "procurement/tender_detail.html", {
        "tender": tender, "own_bid": own_bid,
        "bids": tender.bids.select_related("supplier__profile") if can_see_bids else [],
        "comparison_summary": ranking[0] if ranking else None,
        "submitted_bid_count": tender.bids.filter(status=Bid.Status.SUBMITTED).count(),
        "is_owner": can_manage, "can_review": can_review, "can_see_bids": can_see_bids, "best_price": best_price,
        "question_form": QuestionForm(), "document_form": TenderDocumentForm(), "lot_form": TenderLotForm(),
        "is_favorite": request.user.is_authenticated and tender.favorites.filter(pk=request.user.pk).exists(),
        "is_imported": bool(imported_data),
        "external_documents": details.get("documents", []),
        "external_criteria": details.get("criteria", []),
        "external_parameters": details.get("parameters", {}),
        "external_rules": details.get("rules", []),
        "position_specification": position_specification,
    })


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def tender_comparison(request, pk):
    tender = manageable_tender_or_404(request.user, pk)
    rows = comparison_rows(tender)
    selected_bid_ids = set(tender.winner_selections.values_list("bid_id", flat=True))
    applications = {
        application.organization_id: application.pk
        for application in SupplierApplication.objects.filter(customer=tender.organization)
    }
    for row in rows:
        row["supplier_application_id"] = applications.get(row["bid"].supplier.profile.organization_id)
    signals_by_bid = {}
    for signal in BidFraudSignal.objects.filter(tender=tender).select_related("related_bid__supplier__profile"):
        signals_by_bid.setdefault(signal.bid_id, []).append(signal)
    for row in rows:
        row["fraud_signals"] = signals_by_bid.get(row["bid"].pk, [])
        row["is_selected"] = row["bid"].pk in selected_bid_ids
    status = request.GET.get("status", "")
    lots = request.GET.get("lots", "")
    score_from = request.GET.get("score_from", "").strip()
    if status not in Bid.Status.values:
        status = ""
    if status:
        rows = [row for row in rows if row["bid"].status == status]
    if lots == "yes":
        rows = [row for row in rows if row["bid"].lot_offers.exists()]
    elif lots == "no":
        rows = [row for row in rows if not row["bid"].lot_offers.exists()]
    if score_from:
        try:
            minimum_score = Decimal(score_from)
            rows = [row for row in rows if row["score"] >= minimum_score]
        except Exception:
            score_from = ""
    audit(request.user, "tender.comparison_opened", tender, bid_count=len(rows))
    return render(request, "procurement/tender_comparison.html", {
        "tender": tender,
        "rows": rows,
        "status": status,
        "lots": lots,
        "score_from": score_from,
        "bid_statuses": Bid.Status.choices,
        "selected_count": len(selected_bid_ids),
    })


@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    if not profile:
        raise PermissionDenied
    notifications = request.user.notifications.all()[:6]
    if profile.role == Profile.Role.CUSTOMER:
        organizations = accessible_customer_organizations(request.user)
        organization = selected_organization(request, organizations)
        organization_tenders = Tender.objects.filter(organization__in=organizations)
        query = request.GET.get("q", "").strip()
        status = request.GET.get("status", "")
        category = request.GET.get("category", "")
        procedure = request.GET.get("procedure", "")
        source = request.GET.get("source", "")
        if organization:
            organization_tenders = organization_tenders.filter(organization=organization)
        if status not in Tender.Status.values:
            status = ""
        if category not in Tender.Category.values:
            category = ""
        if procedure not in Tender.Procedure.values:
            procedure = ""
        if source not in {"", "local", "imported"}:
            source = ""
        tenders = organization_tenders
        if query:
            tenders = tenders.filter(Q(title__icontains=query) | Q(number__icontains=query))
        if status:
            tenders = tenders.filter(status=status)
        else:
            tenders = tenders.exclude(status=Tender.Status.COMPLETED)
        if category:
            tenders = tenders.filter(category=category)
        if procedure:
            tenders = tenders.filter(procedure=procedure)
        if source == "imported":
            tenders = tenders.filter(import_record__isnull=False)
        elif source == "local":
            tenders = tenders.filter(import_record__isnull=True)
        tenders = tenders.select_related("pending_winner__supplier__profile").annotate(
            bid_count=Count("bids"), lowest_price=Min("bids__price")
        ).order_by("-created_at", "-pk")
        page = Paginator(tenders, 25).get_page(request.GET.get("page"))
        for tender in page:
            if tender.procedure == Tender.Procedure.CLOSED and tender.is_open:
                tender.lowest_price = None
        pagination_params = request.GET.copy()
        pagination_params.pop("page", None)
        pending = SupplierApplication.objects.filter(
            customer__in=organizations,
            status=SupplierApplication.Status.PENDING,
        ).select_related("organization", "customer")
        approvals = TenderApproval.objects.filter(
            tender__organization__in=organizations,
            decision=TenderApproval.Decision.PENDING,
        ).select_related("tender", "requested_by")
        if organization:
            pending = pending.filter(customer=organization)
            approvals = approvals.filter(tender__organization=organization)
        import_sources = TenderImportSource.objects.filter(
            organization__in=organizations
        ).select_related("organization")
        if organization:
            import_sources = import_sources.filter(organization=organization)
        import_runs = TenderImportRun.objects.filter(
            source__organization__in=organizations
        ).select_related("source", "source__organization", "requested_by")
        if organization:
            import_runs = import_runs.filter(source__organization=organization)
        expiring_documents = SupplierDocument.objects.filter(
            organization__supplier_applications__customer__in=organizations,
            expires_at__isnull=False,
            expires_at__lte=timezone.localdate() + timedelta(days=30),
        ).select_related("organization").order_by("expires_at").distinct()
        if organization:
            expiring_documents = expiring_documents.filter(
                organization__supplier_applications__customer=organization
            )
        return render(request, "procurement/dashboard_customer.html", {
            "tenders": page, "page_obj": page, "pending_applications": pending, "notifications": notifications,
            "total_tenders": organization_tenders.count(),
            "total_budget": organization_tenders.filter(
                status=Tender.Status.PUBLISHED, deadline__gt=timezone.now()
            ).aggregate(v=Sum("budget"))["v"] or 0,
            "active_tenders": organization_tenders.filter(
                status=Tender.Status.PUBLISHED, deadline__gt=timezone.now()
            ).count(),
            "review_tenders": organization_tenders.filter(status=Tender.Status.REVIEW).count(),
            "pending_approvals": approvals, "query": query, "status": status, "category": category,
            "procedure": procedure, "source": source, "statuses": Tender.Status.choices,
            "categories": Tender.Category.choices, "procedures": Tender.Procedure.choices,
            "pagination_query": pagination_params.urlencode(),
            "organizations": organizations, "organization": organization,
            "can_create": accessible_customer_organizations(
                request.user, [Membership.Role.OWNER, Membership.Role.MANAGER]
            ).exists(),
            "can_manage_organizations": accessible_customer_organizations(
                request.user, [Membership.Role.OWNER]
            ).exists(),
            "can_review_any": accessible_customer_organizations(
                request.user, [Membership.Role.OWNER, Membership.Role.REVIEWER]
            ).exists(),
            "import_sources": import_sources, "import_runs": import_runs[:8],
            "expiring_documents": expiring_documents[:5],
            "unanswered_questions": Question.objects.filter(
                tender__organization__in=organizations, answer="", created_at__lte=timezone.now() - timedelta(hours=24)
            ).count(),
            "manageable_import_source_ids": set(TenderImportSource.objects.filter(
                organization__in=accessible_customer_organizations(
                    request.user, [Membership.Role.OWNER, Membership.Role.MANAGER]
                )
            ).values_list("pk", flat=True)),
        })
    bid_query = request.GET.get("q", "").strip()
    bid_status = request.GET.get("status", "")
    tender_status = request.GET.get("tender_status", "")
    if bid_status not in Bid.Status.values:
        bid_status = ""
    if tender_status not in Tender.Status.values:
        tender_status = ""
    all_bids = request.user.bids.select_related("tender", "tender__owner__profile")
    bids = all_bids
    if bid_query:
        bids = bids.filter(Q(tender__title__icontains=bid_query) | Q(tender__number__icontains=bid_query))
    if bid_status:
        bids = bids.filter(status=bid_status)
    if tender_status:
        bids = bids.filter(tender__status=tender_status)
    else:
        bids = bids.exclude(tender__status=Tender.Status.COMPLETED)
    bids = bids.order_by("-updated_at", "-pk")
    page = Paginator(bids, 20).get_page(request.GET.get("page"))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    application = profile.organization.supplier_applications.order_by("submitted_at").first() if profile.organization else None
    return render(request, "procurement/dashboard_supplier.html", {
        "bids": page, "page_obj": page, "application": application, "notifications": notifications,
        "favorites": request.user.favorite_tenders.all()[:4], "total_bids": all_bids.count(),
        "winning_bids": all_bids.filter(status=Bid.Status.WINNER).count(),
        "active_bids": all_bids.filter(tender__status=Tender.Status.PUBLISHED, tender__deadline__gt=timezone.now()).count(),
        "query": bid_query, "status": bid_status, "tender_status": tender_status,
        "bid_statuses": Bid.Status.choices, "tender_statuses": Tender.Status.choices,
        "pagination_query": pagination_params.urlencode(),
    })


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
@transaction.atomic
def tender_create(request):
    form = TenderForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        tender = form.save(commit=False)
        tender.owner = request.user
        tender.number = generate_tender_number()
        tender.auction_step = None
        membership = request.user.memberships.get(organization=tender.organization, is_active=True)
        if "publish" in request.POST and membership.role == Membership.Role.OWNER:
            tender.status = Tender.Status.PUBLISHED
        elif "publish" in request.POST:
            tender.status = Tender.Status.APPROVAL
        else:
            tender.status = Tender.Status.DRAFT
        tender.save()
        if tender.status == Tender.Status.APPROVAL:
            TenderApproval.objects.create(tender=tender, requested_by=request.user)
        audit(request.user, "tender.created", tender, status=tender.status)
        messages.success(request, "Тендер опубликован." if tender.status == Tender.Status.PUBLISHED else "Черновик сохранен.")
        return redirect(tender)
    return render(request, "procurement/tender_form.html", {"form": form})


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def tender_edit(request, pk):
    tender = manageable_tender_or_404(request.user, pk)
    if tender.status != Tender.Status.DRAFT:
        messages.error(request, "Редактировать можно только черновик.")
        return redirect(tender)
    form = TenderForm(request.POST or None, instance=tender, user=request.user)
    if request.method == "POST" and form.is_valid():
        tender = form.save()
        if "publish" in request.POST:
            membership = request.user.memberships.get(organization=tender.organization, is_active=True)
            tender.status = Tender.Status.PUBLISHED if membership.role == Membership.Role.OWNER else Tender.Status.APPROVAL
            tender.save(update_fields=["status"])
            if tender.status == Tender.Status.APPROVAL:
                TenderApproval.objects.create(tender=tender, requested_by=request.user)
        audit(request.user, "tender.updated", tender, status=tender.status)
        messages.success(request, "Закупка обновлена.")
        return redirect(tender)
    return render(request, "procurement/tender_form.html", {"form": form, "tender": tender})


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def tender_cancel(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    tender = manageable_tender_or_404(request.user, pk)
    if tender.status not in {Tender.Status.DRAFT, Tender.Status.APPROVAL, Tender.Status.PUBLISHED, Tender.Status.REVIEW}:
        messages.error(request, "Эту закупку уже нельзя отменить.")
        return redirect(tender)
    tender.status = Tender.Status.CANCELLED
    tender.pending_winner = None
    tender.save(update_fields=["status", "pending_winner"])
    tender.winner_selections.all().delete()
    ProcurementProtocol.objects.create(
        tender=tender,
        kind=ProcurementProtocol.Kind.CANCELLATION,
        number=f"WB-CANCEL-{tender.organization_id}-{tender.pk}",
        data={"reason": request.POST.get("reason", "").strip(), "cancelled_at": timezone.now().isoformat()},
        created_by=request.user,
    )
    for participant in tender.bids.select_related("supplier"):
        notify_user(participant.supplier, f"Закупка отменена: {tender.number}", url=tender.get_absolute_url())
    audit(request.user, "tender.cancelled", tender)
    messages.success(request, "Закупка отменена.")
    return redirect(tender)


@role_required(Profile.Role.SUPPLIER)
@transaction.atomic
def bid_submit(request, pk):
    tender = get_object_or_404(Tender.objects.select_for_update(), pk=pk)
    application = supplier_application_for_tender(request.user, tender)
    if not application or application.status != SupplierApplication.Status.APPROVED:
        messages.error(request, "Участие доступно после аккредитации компании.")
        return redirect("dashboard")
    if not tender.is_open:
        messages.error(request, "Прием предложений закрыт.")
        return redirect(tender)
    bid = Bid.objects.filter(tender=tender, supplier=request.user).first()
    form = BidForm(request.POST or None, instance=bid, tender=tender)
    draft_bid = bid or Bid(tender=tender, supplier=request.user)
    has_lots = tender.lots.exists()
    initial_lots = [{"lot": lot, "price": lot.budget, "delivery_days": 1} for lot in tender.lots.all()] if not bid and has_lots else None
    formset_class = bid_lot_formset(extra=tender.lots.count() if not bid and has_lots else 0)
    lot_formset = formset_class(request.POST or None, instance=draft_bid, initial=initial_lots, prefix="lots")
    for lot_form in lot_formset.forms:
        lot_form.fields["lot"].queryset = tender.lots.all()
    if request.method == "POST" and form.is_valid() and (not has_lots or lot_formset.is_valid()):
        new_bid = form.save(commit=False)
        if has_lots:
            submitted_lot_ids = {lot_form.cleaned_data.get("lot").pk for lot_form in lot_formset if lot_form.cleaned_data.get("lot")}
            expected_lot_ids = set(tender.lots.values_list("pk", flat=True))
            if submitted_lot_ids != expected_lot_ids:
                form.add_error(None, "Необходимо заполнить предложение по каждому лоту.")
            else:
                new_bid.price = sum(lot_form.cleaned_data["price"] for lot_form in lot_formset)
                new_bid.delivery_days = max(lot_form.cleaned_data["delivery_days"] for lot_form in lot_formset)
        current_best_price = tender.best_price
        required_price = current_best_price
        if form.errors:
            pass
        elif tender.budget and new_bid.price > tender.budget:
            form.add_error("price", "Предложение не может превышать начальную цену.")
        elif tender.procedure == Tender.Procedure.AUCTION and required_price is not None and new_bid.price >= required_price:
            form.add_error("price", f"Ставка должна быть ниже текущей лучшей цены {required_price} ₽.")
        else:
            new_bid.tender, new_bid.supplier, new_bid.status = tender, request.user, Bid.Status.SUBMITTED
            new_bid.save()
            if has_lots:
                lot_formset.instance = new_bid
                lot_formset.save()
            audit(request.user, "bid.submitted", new_bid, price=str(new_bid.price))
            signal_count = refresh_bid_fraud_signals(tender.pk)
            if signal_count:
                audit(request.user, "bid.fraud_signals_detected", new_bid, signal_count=signal_count)
            notify_user(tender.owner, f"Новое предложение: {tender.number}", url=tender.get_absolute_url())
            messages.success(request, "Предложение сохранено.")
            return redirect(tender)
    return render(request, "procurement/bid_form.html", {"form": form, "lot_formset": lot_formset, "tender": tender, "bid": bid})


@login_required
def toggle_favorite(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    tender = get_object_or_404(Tender, pk=pk)
    if tender.favorites.filter(pk=request.user.pk).exists():
        tender.favorites.remove(request.user)
    else:
        tender.favorites.add(request.user)
    return redirect(tender)


@role_required(Profile.Role.SUPPLIER)
def ask_question(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    application = supplier_application_for_tender(request.user, tender)
    if not application or application.status != SupplierApplication.Status.APPROVED:
        messages.error(request, "Вопросы доступны после аккредитации компании.")
        return redirect("dashboard")
    if not tender.is_open:
        messages.error(request, "Вопросы можно задавать только во время приема заявок.")
        return redirect(tender)
    form = QuestionForm(request.POST)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.tender, question.author = tender, request.user
        question.save()
        notify_user(tender.owner, f"Новый вопрос: {tender.number}", url=tender.get_absolute_url())
        messages.success(request, "Вопрос отправлен заказчику.")
    return redirect(tender)


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def answer_question(request, question_pk):
    question = get_object_or_404(Question.objects.select_related("tender"), pk=question_pk)
    if not question.tender.user_can_manage(request.user):
        raise PermissionDenied
    form = AnswerForm(request.POST, instance=question)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.answered_by, question.answered_at = request.user, timezone.now()
        question.save()
        notify_user(question.author, f"Получен ответ: {question.tender.number}", url=question.tender.get_absolute_url())
    return redirect(question.tender)


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def add_lot(request, pk):
    tender = manageable_tender_or_404(request.user, pk)
    if tender.status != Tender.Status.DRAFT:
        messages.error(request, "Состав лотов можно менять только в черновике.")
        return redirect(tender)
    form = TenderLotForm(request.POST)
    if form.is_valid():
        lot = form.save(commit=False)
        lot.tender = tender
        lot.save()
        messages.success(request, "Лот добавлен.")
    return redirect(tender)


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def add_document(request, pk):
    tender = manageable_tender_or_404(request.user, pk)
    form = TenderDocumentForm(request.POST, request.FILES)
    if form.is_valid():
        document = form.save(commit=False)
        document.tender, document.uploaded_by = tender, request.user
        document.save()
        messages.success(request, "Документ загружен.")
    return redirect(tender)


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def review_supplier(request, application_pk, decision):
    application = get_object_or_404(
        SupplierApplication,
        pk=application_pk,
        customer__memberships__user=request.user,
        customer__memberships__is_active=True,
        customer__memberships__role__in=[Membership.Role.OWNER, Membership.Role.MANAGER],
    )
    if request.method != "POST" or decision not in {"approve", "reject"}:
        raise PermissionDenied
    application.status = SupplierApplication.Status.APPROVED if decision == "approve" else SupplierApplication.Status.REJECTED
    application.comment = request.POST.get("comment", "").strip()
    application.reviewed_by, application.reviewed_at = request.user, timezone.now()
    application.save()
    for profile in application.organization.profiles.all():
        notify_user(profile.user, f"Аккредитация: {application.get_status_display()}", url="/dashboard/")
    audit(request.user, "supplier.reviewed", application, organization=application.customer, decision=decision)
    return redirect("dashboard")


@membership_role_required(Membership.Role.OWNER, Membership.Role.REVIEWER)
def review_tender(request, approval_pk, decision):
    if request.method != "POST" or decision not in {"approve", "reject"}:
        raise PermissionDenied
    approval = get_object_or_404(
        TenderApproval.objects.select_related("tender"),
        pk=approval_pk,
        tender__organization__memberships__user=request.user,
        tender__organization__memberships__is_active=True,
        tender__organization__memberships__role__in=[Membership.Role.OWNER, Membership.Role.REVIEWER],
        decision=TenderApproval.Decision.PENDING,
    )
    approval.comment = request.POST.get("comment", "").strip()
    approval.reviewer = request.user
    approval.reviewed_at = timezone.now()
    if decision == "approve":
        approval.decision = TenderApproval.Decision.APPROVED
        approval.tender.status = Tender.Status.PUBLISHED
    else:
        approval.decision = TenderApproval.Decision.REJECTED
        approval.tender.status = Tender.Status.DRAFT
    approval.save(update_fields=["comment", "reviewer", "reviewed_at", "decision"])
    approval.tender.save(update_fields=["status"])
    notify_user(
        approval.requested_by,
        f"Результат согласования: {approval.tender.number}",
        approval.get_decision_display(),
        approval.tender.get_absolute_url(),
    )
    audit(request.user, "tender.approval_reviewed", approval, decision=decision)
    return redirect(approval.tender)


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
@transaction.atomic
def select_winner(request, tender_pk, bid_pk):
    if request.method != "POST":
        raise PermissionDenied
    tender = manageable_tender_or_404(request.user, tender_pk)
    if tender.status not in {Tender.Status.PUBLISHED, Tender.Status.REVIEW}:
        messages.error(request, "Для этой закупки победитель уже выбран или процедура отменена.")
        return redirect(tender)
    bid = get_object_or_404(Bid, pk=bid_pk, tender=tender, status=Bid.Status.SUBMITTED)
    ranking = comparison_rows(tender)
    winner_ranking = next((row for row in ranking if row["bid"].pk == bid.pk), None)
    snapshot = {
        "total_score": str(winner_ranking["score"]) if winner_ranking else None,
        "price_score": str(winner_ranking["price_score"]) if winner_ranking else None,
        "delivery_score": str(winner_ranking["delivery_score"]) if winner_ranking else None,
        "warranty_score": str(winner_ranking["warranty_score"]) if winner_ranking else None,
        "weights": {"price": 60, "delivery": 25, "warranty": 15},
    }
    selection, created = TenderWinnerSelection.objects.get_or_create(
        tender=tender, bid=bid,
        defaults={"selected_by": request.user, "ranking_snapshot": snapshot},
    )
    if not created:
        messages.info(request, "Этот поставщик уже выбран предварительно.")
        return redirect(tender)
    first_selection = tender.winner_selections.order_by("selected_at").first()
    tender.pending_winner = first_selection.bid
    tender.winner_selected_by = request.user
    tender.winner_selected_at = timezone.now()
    tender.winner_ranking_snapshot = snapshot
    tender.save(update_fields=["pending_winner", "winner_selected_by", "winner_selected_at", "winner_ranking_snapshot"])
    audit(
        request.user, "winner.preselected", bid,
        ranking_score=str(winner_ranking["score"]) if winner_ranking else None,
        ranking_position=winner_ranking["rank"] if winner_ranking else None,
    )
    messages.success(
        request,
        f"Предварительно выбран поставщик: {bid.supplier.profile.company_name}. "
        "Статусы заявок, протокол и договор будут опубликованы на следующий календарный день после дедлайна.",
    )
    return redirect(tender)


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def unselect_winner(request, tender_pk, bid_pk):
    if request.method != "POST":
        raise PermissionDenied
    tender = manageable_tender_or_404(request.user, tender_pk)
    selection = get_object_or_404(TenderWinnerSelection, tender=tender, bid_id=bid_pk)
    selection.delete()
    first_selection = tender.winner_selections.order_by("selected_at").first()
    tender.pending_winner = first_selection.bid if first_selection else None
    tender.save(update_fields=["pending_winner"])
    audit(request.user, "winner.unselected", tender, bid_id=bid_pk)
    messages.success(request, "Предварительный выбор поставщика отменен.")
    return redirect("tender_comparison", pk=tender.pk)


@login_required
def notifications(request):
    request.user.notifications.update(is_read=True)
    page = Paginator(request.user.notifications.all(), 30).get_page(request.GET.get("page"))
    return render(request, "procurement/notifications.html", {"notifications": page, "page_obj": page})


@role_required(Profile.Role.CUSTOMER)
def supplier_registry(request):
    organizations = accessible_customer_organizations(request.user)
    organization = selected_organization(request, organizations)
    applications = SupplierApplication.objects.filter(
        customer__in=organizations
    ).select_related("organization", "customer", "reviewed_by")
    if organization:
        applications = applications.filter(customer=organization)
    page = Paginator(applications, 30).get_page(request.GET.get("page"))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    return render(request, "procurement/supplier_registry.html", {
        "applications": page, "page_obj": page, "organizations": organizations,
        "organization": organization, "pagination_query": pagination_params.urlencode(),
    })


@membership_role_required(Membership.Role.OWNER)
def employee_registry(request, organization_pk=None):
    organizations = accessible_customer_organizations(request.user, [Membership.Role.OWNER])
    organization = get_object_or_404(organizations, pk=organization_pk) if organization_pk else selected_organization(request, organizations)
    memberships = Membership.objects.filter(organization__in=organizations).select_related("user", "organization")
    if organization:
        memberships = memberships.filter(organization=organization)
    return render(request, "procurement/employee_registry.html", {
        "memberships": memberships,
        "form": EmployeeInviteForm(user=request.user),
        "organizations": organizations, "organization": organization,
    })


@membership_role_required(Membership.Role.OWNER)
def invite_employee(request):
    if request.method != "POST":
        raise PermissionDenied
    form = EmployeeInviteForm(request.POST, user=request.user)
    if not form.is_valid():
        organizations = accessible_customer_organizations(request.user, [Membership.Role.OWNER])
        return render(request, "procurement/employee_registry.html", {
            "memberships": Membership.objects.filter(
                organization__in=organizations
            ).select_related("user", "organization"),
            "form": form, "organizations": organizations, "organization": None,
        })
    organization = form.cleaned_data["organization"]
    user = User.objects.filter(email__iexact=form.cleaned_data["email"]).first()
    if not user:
        user = User.objects.create(
            username=form.cleaned_data["username"],
            email=form.cleaned_data["email"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        Profile.objects.create(
            user=user, role=Profile.Role.CUSTOMER, company_name=organization.name,
            inn=organization.inn or "", phone=organization.phone, organization=organization,
        )
        reset_form = PasswordResetForm({"email": user.email})
        if reset_form.is_valid():
            reset_form.save(request=request, use_https=request.is_secure())
    Membership.objects.update_or_create(
        user=user, organization=organization,
        defaults={"role": form.cleaned_data["role"], "is_active": True},
    )
    audit(
        request.user, "employee.invited", user, organization=organization,
        role=form.cleaned_data["role"],
    )
    messages.success(request, "Сотрудник добавлен. Ссылка для установки пароля отправлена на email.")
    return redirect("employee_registry")


@membership_role_required(Membership.Role.OWNER)
def toggle_employee(request, membership_pk):
    if request.method != "POST":
        raise PermissionDenied
    membership = get_object_or_404(
        Membership,
        pk=membership_pk,
        organization__memberships__user=request.user,
        organization__memberships__role=Membership.Role.OWNER,
        organization__memberships__is_active=True,
    )
    if membership.user_id == request.user.id:
        messages.error(request, "Нельзя отключить собственную учетную запись.")
        return redirect("employee_registry")
    membership.is_active = not membership.is_active
    membership.save(update_fields=["is_active"])
    membership.user.is_active = membership.user.memberships.filter(is_active=True).exists()
    membership.user.save(update_fields=["is_active"])
    audit(
        request.user, "employee.toggled", membership, organization=membership.organization,
        active=membership.is_active,
    )
    return redirect("employee_registry")


@login_required
def company_profile(request):
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.organization:
        raise PermissionDenied
    organization = profile.organization
    can_edit = Membership.objects.filter(
        organization=organization,
        user=request.user,
        role=Membership.Role.OWNER,
        is_active=True,
    ).exists()
    if request.method == "POST" and not can_edit:
        raise PermissionDenied
    form = OrganizationForm(request.POST or None, instance=organization)
    if not can_edit:
        for field in form.fields.values():
            field.disabled = True
    if request.method == "POST" and form.is_valid():
        organization = form.save()
        profile.company_name, profile.inn, profile.phone = organization.name, organization.inn or "", organization.phone
        profile.save(update_fields=["company_name", "inn", "phone"])
        audit(request.user, "organization.updated", organization)
        messages.success(request, "Карточка компании обновлена.")
        return redirect("company_profile")
    application = organization.supplier_applications.order_by("submitted_at").first()
    return render(request, "procurement/company_profile.html", {
        "organization": organization,
        "form": form,
        "application": application,
        "document_form": SupplierDocumentForm(),
        "can_edit": can_edit,
    })


@role_required(Profile.Role.SUPPLIER)
def upload_supplier_document(request):
    form = SupplierDocumentForm(request.POST, request.FILES)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.organization = request.user.profile.organization
        document.uploaded_by = request.user
        document.save()
        audit(request.user, "supplier_document.uploaded", document)
        messages.success(request, "Документ добавлен.")
    return redirect("company_profile")


@role_required(Profile.Role.SUPPLIER)
def resubmit_application(request):
    if request.method != "POST":
        raise PermissionDenied
    application = get_object_or_404(
        SupplierApplication,
        organization=request.user.profile.organization,
        customer__kind=Organization.Kind.CUSTOMER,
    )
    if application.status != SupplierApplication.Status.REJECTED:
        messages.error(request, "Повторная отправка доступна только для отклоненной заявки.")
        return redirect("company_profile")
    application.status = SupplierApplication.Status.PENDING
    application.reviewed_at = None
    application.reviewed_by = None
    application.save(update_fields=["status", "reviewed_at", "reviewed_by"])
    audit(request.user, "supplier_application.resubmitted", application)
    messages.success(request, "Заявка повторно отправлена на проверку.")
    return redirect("company_profile")


@role_required(Profile.Role.CUSTOMER)
def supplier_detail(request, application_pk):
    application = get_object_or_404(
        SupplierApplication.objects.select_related("organization"),
        pk=application_pk,
        customer__memberships__user=request.user,
        customer__memberships__is_active=True,
    )
    bids = Bid.objects.filter(
        supplier__profile__organization=application.organization,
        tender__organization=application.customer,
    ).select_related("tender", "supplier__profile").order_by("-updated_at", "-pk")
    return render(request, "procurement/supplier_detail.html", {
        "application": application,
        "bids": bids,
    })


@login_required
def supplier_document_download(request, document_pk):
    document = get_object_or_404(SupplierDocument.objects.select_related("organization"), pk=document_pk)
    profile = getattr(request.user, "profile", None)
    if not profile:
        raise PermissionDenied
    owns_document = profile.organization_id == document.organization_id
    customer_is_accreditor = (
        profile.role == Profile.Role.CUSTOMER
        and SupplierApplication.objects.filter(
            organization=document.organization,
            customer__memberships__user=request.user,
            customer__memberships__is_active=True,
        ).exists()
    )
    if not owns_document and not customer_is_accreditor:
        raise PermissionDenied
    audit(request.user, "supplier_document.downloaded", document)
    return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.file.name.rsplit("/", 1)[-1])


@login_required
def document_download(request, document_pk):
    document = get_object_or_404(TenderDocument.objects.select_related("tender"), pk=document_pk)
    if document.tender.status in {Tender.Status.DRAFT, Tender.Status.APPROVAL} and not document.tender.user_can_review(request.user):
        raise PermissionDenied
    if document.visibility == TenderDocument.Visibility.CUSTOMER and not document.tender.user_can_review(request.user):
        raise PermissionDenied
    audit(request.user, "document.downloaded", document)
    return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.file.name.rsplit("/", 1)[-1])


def external_document_redirect(request, tender_pk, document_index):
    tender = get_object_or_404(
        Tender.objects.select_related("import_record"), pk=tender_pk
    )
    if tender.status in {Tender.Status.DRAFT, Tender.Status.APPROVAL} and not tender.user_can_review(request.user):
        raise PermissionDenied
    imported_data = tender.import_record.raw_data if hasattr(tender, "import_record") else {}
    documents = imported_data.get("details", {}).get("documents", [])
    try:
        document = documents[document_index]
        url = document["url"]
    except (IndexError, KeyError, TypeError):
        raise Http404
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise Http404
    audit(
        request.user, "external_document.redirected", tender,
        document_title=document.get("title", ""),
    )
    response = HttpResponseRedirect(url)
    response["Referrer-Policy"] = "no-referrer"
    return response


@login_required
def contract_registry(request):
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.organization:
        raise PermissionDenied
    if profile.role == Profile.Role.CUSTOMER:
        organizations = accessible_customer_organizations(request.user)
        organization = selected_organization(request, organizations)
        contracts = Contract.objects.filter(customer__in=organizations)
        if organization:
            contracts = contracts.filter(customer=organization)
    else:
        organizations, organization = None, None
        contracts = Contract.objects.filter(supplier=profile.organization)
    page = Paginator(contracts.select_related("tender", "customer", "supplier"), 30).get_page(request.GET.get("page"))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    return render(request, "procurement/contract_registry.html", {
        "contracts": page, "page_obj": page, "organizations": organizations, "organization": organization,
        "pagination_query": pagination_params.urlencode(),
    })


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def update_contract_status(request, contract_pk, status):
    if request.method != "POST" or status not in Contract.Status.values:
        raise PermissionDenied
    contract = get_object_or_404(
        Contract, pk=contract_pk,
        customer__memberships__user=request.user,
        customer__memberships__is_active=True,
        customer__memberships__role__in=[Membership.Role.OWNER, Membership.Role.MANAGER],
    )
    transitions = {
        Contract.Status.PREPARATION: {Contract.Status.SIGNED, Contract.Status.TERMINATED},
        Contract.Status.SIGNED: {Contract.Status.COMPLETED, Contract.Status.TERMINATED},
        Contract.Status.COMPLETED: set(),
        Contract.Status.TERMINATED: set(),
    }
    if status not in transitions[contract.status]:
        messages.error(request, "Недопустимый переход статуса договора.")
        return redirect("contract_registry")
    contract.status = status
    contract.signed_at = timezone.now() if status == Contract.Status.SIGNED else contract.signed_at
    contract.save(update_fields=["status", "signed_at"])
    audit(request.user, "contract.status_updated", contract, status=status)
    notify_user(contract.winning_bid.supplier, f"Статус договора {contract.number}: {contract.get_status_display()}", url=reverse("contract_registry"))
    return redirect("contract_registry")


@login_required
def protocol_detail(request, protocol_pk):
    protocol = get_object_or_404(ProcurementProtocol.objects.select_related("tender", "created_by"), pk=protocol_pk)
    if not protocol.tender.publish_results and not protocol.tender.user_can_review(request.user):
        raise PermissionDenied
    return render(request, "procurement/protocol_detail.html", {"protocol": protocol})


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER, Membership.Role.REVIEWER)
def tender_export(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="wildberries-tenders.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Юридическое лицо", "Номер", "Название", "Статус", "Формат", "Бюджет", "Дедлайн", "Заявок"])
    organizations = accessible_customer_organizations(request.user)
    organization = selected_organization(request, organizations)
    tenders = Tender.objects.filter(organization__in=organizations).annotate(bid_count=Count("bids"))
    if organization:
        tenders = tenders.filter(organization=organization)
    for tender in tenders:
        writer.writerow([tender.organization.name, tender.number, tender.title, tender.get_status_display(), tender.get_procedure_display(), tender.budget, tender.deadline, tender.bid_count])
    return response


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER, Membership.Role.REVIEWER)
def audit_export(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="tenderflow-audit.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Время", "Юридическое лицо", "Пользователь", "Действие", "Объект", "Детали"])
    organizations = accessible_customer_organizations(request.user)
    organization = selected_organization(request, organizations)
    events = AuditEvent.objects.filter(organization__in=organizations).select_related("user", "organization")
    if organization:
        events = events.filter(organization=organization)
    action = request.GET.get("action", "").strip()
    if action:
        events = events.filter(action__icontains=action)
    for event in events.iterator():
        writer.writerow([
            event.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            event.organization.name if event.organization else "",
            event.user.get_username() if event.user else "Система",
            event.action,
            f"{event.object_type} #{event.object_id}",
            event.details,
        ])
    audit(request.user, "audit.exported", organization=organization)
    return response


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER, Membership.Role.REVIEWER)
def audit_registry(request):
    organizations = accessible_customer_organizations(request.user)
    organization = selected_organization(request, organizations)
    events = AuditEvent.objects.filter(organization__in=organizations).select_related("user", "organization")
    if organization:
        events = events.filter(organization=organization)
    action = request.GET.get("action", "").strip()
    if action:
        events = events.filter(action__icontains=action)
    page = Paginator(events, 50).get_page(request.GET.get("page"))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    return render(request, "procurement/audit_registry.html", {
        "events": page, "page_obj": page, "action": action,
        "organizations": organizations, "organization": organization,
        "pagination_query": pagination_params.urlencode(),
    })


@login_required
def operations_dashboard(request):
    if not request.user.is_staff:
        raise PermissionDenied
    checks = []
    try:
        connection.ensure_connection()
        checks.append(("База данных", True, "Подключение PostgreSQL установлено."))
    except Exception:
        checks.append(("База данных", False, "Не удалось подключиться к базе данных."))
    try:
        cache.set("operations-health-check", "ok", 10)
        checks.append(("Redis cache", cache.get("operations-health-check") == "ok", "Кэш и блокировки доступны."))
    except Exception:
        checks.append(("Redis cache", False, "Кэш недоступен."))
    smtp_ready = bool(settings.EMAIL_HOST and settings.EMAIL_NOTIFICATIONS_ENABLED)
    checks.append(("Email", smtp_ready, "Уведомления включены." if smtp_ready else "Email-уведомления выключены или SMTP не настроен."))
    try:
        backup_file = Path(settings.BACKUP_STATUS_FILE)
        backup_time = backup_file.read_text(encoding="utf-8").strip() if backup_file.exists() else ""
        checks.append(("Резервная копия", bool(backup_time), backup_time or "Файл последней успешной копии не найден."))
    except OSError:
        checks.append(("Резервная копия", False, "Статус резервного копирования недоступен."))
    since = timezone.now() - timedelta(hours=24)
    failed_imports = TenderImportRun.objects.filter(
        created_at__gte=since, status__in=[TenderImportRun.Status.FAILED, TenderImportRun.Status.PARTIAL]
    ).count()
    recent_logins = LoginEvent.objects.select_related("user").all()[:20]
    return render(request, "procurement/operations_dashboard.html", {
        "checks": checks,
        "failed_imports": failed_imports,
        "unread_notifications": request.user.notifications.filter(is_read=False).count(),
        "recent_logins": recent_logins,
    })


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def run_tender_import(request, source_pk):
    if request.method != "POST":
        raise PermissionDenied
    source = get_object_or_404(
        TenderImportSource,
        pk=source_pk,
        organization__memberships__user=request.user,
        organization__memberships__is_active=True,
        organization__memberships__role__in=[Membership.Role.OWNER, Membership.Role.MANAGER],
    )
    if source.runs.filter(status__in=[
        TenderImportRun.Status.QUEUED, TenderImportRun.Status.RUNNING,
    ], created_at__gte=timezone.now() - timedelta(hours=2)).exists():
        messages.warning(request, "Парсер этого источника уже запущен.")
        return redirect("dashboard")
    run = TenderImportRun.objects.create(
        source=source, trigger=TenderImportRun.Trigger.MANUAL, requested_by=request.user
    )
    from .tasks import sync_external_tender_source

    sync_external_tender_source.delay(source.pk, run.pk)
    audit(request.user, "tender_import.requested", run, organization=source.organization)
    messages.success(request, "Парсер поставлен в очередь. Результат появится в кабинете.")
    return redirect("dashboard")


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER, Membership.Role.REVIEWER)
def organization_registry(request):
    organizations = accessible_customer_organizations(request.user).annotate(
        employee_count=Count("memberships", distinct=True),
        tender_count=Count("tenders", distinct=True),
    )
    return render(request, "procurement/organization_registry.html", {
        "organizations": organizations,
        "can_create": accessible_customer_organizations(
            request.user, [Membership.Role.OWNER]
        ).exists(),
    })


@membership_role_required(Membership.Role.OWNER)
@transaction.atomic
def organization_create(request):
    form = OrganizationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        organization = form.save(commit=False)
        organization.kind = Organization.Kind.CUSTOMER
        organization.save()
        Membership.objects.create(
            organization=organization, user=request.user, role=Membership.Role.OWNER
        )
        audit(request.user, "organization.created", organization)
        messages.success(request, "Юридическое лицо добавлено.")
        return redirect("organization_registry")
    return render(request, "procurement/organization_form.html", {"form": form})


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
def tender_template_registry(request):
    organizations = accessible_customer_organizations(
        request.user, [Membership.Role.OWNER, Membership.Role.MANAGER]
    )
    organization = selected_organization(request, organizations)
    templates = TenderTemplate.objects.filter(organization__in=organizations).select_related("organization")
    query = request.GET.get("q", "").strip()
    if organization:
        templates = templates.filter(organization=organization)
    if query:
        templates = templates.filter(Q(name__icontains=query) | Q(title__icontains=query))
    return render(request, "procurement/tender_template_registry.html", {
        "templates": templates, "organizations": organizations,
        "organization": organization, "query": query,
    })


def clone_tender_data(source, owner, organization):
    return Tender.objects.create(
        owner=owner, organization=organization, number=generate_tender_number(),
        title=source.title, category=source.category, description=source.description,
        requirements=source.requirements, delivery_address=source.delivery_address,
        budget=source.budget, deadline=timezone.now() + timedelta(days=30),
        procedure=source.procedure, publish_results=source.publish_results,
        status=Tender.Status.DRAFT, auction_step=None,
    )


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
@transaction.atomic
def tender_copy(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    source = manageable_tender_or_404(request.user, pk)
    tender = clone_tender_data(source, request.user, source.organization)
    TenderLot.objects.bulk_create([
        TenderLot(
            tender=tender, title=lot.title, description=lot.description,
            quantity=lot.quantity, unit=lot.unit, budget=lot.budget,
        ) for lot in source.lots.all()
    ])
    audit(request.user, "tender.copied", tender, source_id=source.pk)
    return redirect("tender_edit", pk=tender.pk)


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
@transaction.atomic
def tender_save_template(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    source = manageable_tender_or_404(request.user, pk)
    form = TenderTemplateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Укажите название шаблона.")
        return redirect(source)
    template = form.save(commit=False)
    template.organization, template.owner = source.organization, request.user
    for field in ("title", "category", "description", "requirements", "delivery_address", "budget", "procedure", "publish_results"):
        setattr(template, field, getattr(source, field))
    template.save()
    TenderTemplateLot.objects.bulk_create([
        TenderTemplateLot(
            template=template, title=lot.title, description=lot.description,
            quantity=lot.quantity, unit=lot.unit, budget=lot.budget,
        ) for lot in source.lots.all()
    ])
    audit(request.user, "tender_template.created", template, source_id=source.pk)
    messages.success(request, "Шаблон сохранен.")
    return redirect("tender_template_registry")


@membership_role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
@transaction.atomic
def tender_create_from_template(request, template_pk):
    if request.method != "POST":
        raise PermissionDenied
    template = get_object_or_404(
        TenderTemplate, pk=template_pk,
        organization__memberships__user=request.user,
        organization__memberships__is_active=True,
        organization__memberships__role__in=[Membership.Role.OWNER, Membership.Role.MANAGER],
    )
    tender = clone_tender_data(template, request.user, template.organization)
    TenderLot.objects.bulk_create([
        TenderLot(
            tender=tender, title=lot.title, description=lot.description,
            quantity=lot.quantity, unit=lot.unit, budget=lot.budget,
        ) for lot in template.lots.all()
    ])
    audit(request.user, "tender.created_from_template", tender, template_id=template.pk)
    return redirect("tender_edit", pk=tender.pk)


def health(request):
    try:
        Organization.objects.only("pk").first()
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)


def error_403(request, exception):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
