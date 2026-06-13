from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Min, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    AnswerForm, BidForm, QuestionForm, RegisterForm, SupplierApplicationForm,
    TenderDocumentForm, TenderForm, TenderLotForm,
)
from .models import AuditEvent, Bid, Notification, Profile, Question, SupplierApplication, Tender


def audit(user, action, obj=None, **details):
    profile = getattr(user, "profile", None) if user and user.is_authenticated else None
    AuditEvent.objects.create(
        user=user if user and user.is_authenticated else None,
        organization=getattr(profile, "organization", None),
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


def home(request):
    tenders = Tender.objects.filter(
        status=Tender.Status.PUBLISHED, deadline__gt=timezone.now()
    ).select_related("owner__profile", "organization").annotate(bid_count=Count("bids")).order_by("deadline")[:6]
    stats = {
        "open": Tender.objects.filter(status=Tender.Status.PUBLISHED, deadline__gt=timezone.now()).count(),
        "suppliers": Profile.objects.filter(role=Profile.Role.SUPPLIER).count(),
        "completed": Tender.objects.filter(status=Tender.Status.COMPLETED).count(),
        "savings": Tender.objects.filter(status=Tender.Status.COMPLETED).aggregate(
            value=Sum("budget") - Sum("bids__price", filter=Q(bids__status=Bid.Status.WINNER))
        )["value"] or 0,
    }
    return render(request, "procurement/home.html", {"tenders": tenders, "stats": stats})


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
    tenders = Tender.objects.filter(status=Tender.Status.PUBLISHED).select_related("owner__profile", "organization")
    query, category = request.GET.get("q", "").strip(), request.GET.get("category", "")
    procedure, price_to = request.GET.get("procedure", ""), request.GET.get("price_to", "")
    if query:
        tenders = tenders.filter(Q(title__icontains=query) | Q(number__icontains=query) | Q(description__icontains=query))
    if category:
        tenders = tenders.filter(category=category)
    if procedure:
        tenders = tenders.filter(procedure=procedure)
    if price_to:
        try:
            tenders = tenders.filter(budget__lte=price_to)
        except ValueError:
            pass
    return render(request, "procurement/tender_list.html", {
        "tenders": tenders.annotate(bid_count=Count("bids")), "query": query, "category": category,
        "procedure": procedure, "price_to": price_to, "categories": Tender.Category.choices,
        "procedures": Tender.Procedure.choices,
    })


def tender_detail(request, pk):
    tender = get_object_or_404(Tender.objects.select_related("owner__profile", "organization"), pk=pk)
    profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
    is_owner = request.user.is_authenticated and tender.owner_id == request.user.id
    if tender.status == Tender.Status.DRAFT and not is_owner:
        raise Http404
    own_bid = Bid.objects.filter(tender=tender, supplier=request.user).first() if profile and profile.role == Profile.Role.SUPPLIER else None
    can_see_bids = is_owner and (tender.procedure == Tender.Procedure.AUCTION or not tender.is_open)
    best_price = tender.best_price if tender.procedure == Tender.Procedure.AUCTION else None
    return render(request, "procurement/tender_detail.html", {
        "tender": tender, "own_bid": own_bid,
        "bids": tender.bids.select_related("supplier__profile") if can_see_bids else [],
        "is_owner": is_owner, "can_see_bids": can_see_bids, "best_price": best_price,
        "question_form": QuestionForm(), "document_form": TenderDocumentForm(), "lot_form": TenderLotForm(),
        "is_favorite": request.user.is_authenticated and tender.favorites.filter(pk=request.user.pk).exists(),
    })


@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    if not profile:
        raise PermissionDenied
    notifications = request.user.notifications.all()[:6]
    if profile.role == Profile.Role.CUSTOMER:
        tenders = request.user.tenders.annotate(bid_count=Count("bids"), lowest_price=Min("bids__price"))
        pending = SupplierApplication.objects.filter(status=SupplierApplication.Status.PENDING).select_related("organization")
        return render(request, "procurement/dashboard_customer.html", {
            "tenders": tenders, "pending_applications": pending, "notifications": notifications,
            "total_budget": tenders.aggregate(v=Sum("budget"))["v"] or 0,
        })
    bids = request.user.bids.select_related("tender", "tender__owner__profile")
    application = getattr(profile.organization, "supplier_application", None) if profile.organization else None
    return render(request, "procurement/dashboard_supplier.html", {
        "bids": bids, "application": application, "notifications": notifications,
        "favorites": request.user.favorite_tenders.all()[:4],
    })


@role_required(Profile.Role.CUSTOMER)
def tender_create(request):
    form = TenderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        tender = form.save(commit=False)
        tender.owner = request.user
        tender.organization = request.user.profile.organization
        tender.status = Tender.Status.PUBLISHED if "publish" in request.POST else Tender.Status.DRAFT
        tender.save()
        audit(request.user, "tender.created", tender, status=tender.status)
        messages.success(request, "Тендер опубликован." if tender.status == Tender.Status.PUBLISHED else "Черновик сохранен.")
        return redirect(tender)
    return render(request, "procurement/tender_form.html", {"form": form})


@role_required(Profile.Role.SUPPLIER)
def bid_submit(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    application = getattr(request.user.profile.organization, "supplier_application", None)
    if not application or application.status != SupplierApplication.Status.APPROVED:
        messages.error(request, "Участие доступно после аккредитации компании.")
        return redirect("dashboard")
    if not tender.is_open:
        messages.error(request, "Прием предложений закрыт.")
        return redirect(tender)
    bid = Bid.objects.filter(tender=tender, supplier=request.user).first()
    form = BidForm(request.POST or None, instance=bid)
    if request.method == "POST" and form.is_valid():
        new_bid = form.save(commit=False)
        if tender.procedure == Tender.Procedure.AUCTION and tender.best_price and new_bid.price >= tender.best_price and (not bid or new_bid.price != bid.price):
            form.add_error("price", "Ставка должна быть ниже текущей лучшей цены.")
        else:
            new_bid.tender, new_bid.supplier, new_bid.status = tender, request.user, Bid.Status.SUBMITTED
            new_bid.save()
            audit(request.user, "bid.submitted", new_bid, price=str(new_bid.price))
            Notification.objects.create(user=tender.owner, title=f"Новое предложение: {tender.number}", url=tender.get_absolute_url())
            messages.success(request, "Предложение сохранено.")
            return redirect(tender)
    return render(request, "procurement/bid_form.html", {"form": form, "tender": tender, "bid": bid})


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
    form = QuestionForm(request.POST)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.tender, question.author = tender, request.user
        question.save()
        Notification.objects.create(user=tender.owner, title=f"Новый вопрос: {tender.number}", url=tender.get_absolute_url())
        messages.success(request, "Вопрос отправлен заказчику.")
    return redirect(tender)


@role_required(Profile.Role.CUSTOMER)
def answer_question(request, question_pk):
    question = get_object_or_404(Question, pk=question_pk, tender__owner=request.user)
    form = AnswerForm(request.POST, instance=question)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.answered_by, question.answered_at = request.user, timezone.now()
        question.save()
        Notification.objects.create(user=question.author, title=f"Получен ответ: {question.tender.number}", url=question.tender.get_absolute_url())
    return redirect(question.tender)


@role_required(Profile.Role.CUSTOMER)
def add_lot(request, pk):
    tender = get_object_or_404(Tender, pk=pk, owner=request.user)
    form = TenderLotForm(request.POST)
    if form.is_valid():
        lot = form.save(commit=False)
        lot.tender = tender
        lot.save()
        messages.success(request, "Лот добавлен.")
    return redirect(tender)


@role_required(Profile.Role.CUSTOMER)
def add_document(request, pk):
    tender = get_object_or_404(Tender, pk=pk, owner=request.user)
    form = TenderDocumentForm(request.POST, request.FILES)
    if form.is_valid():
        document = form.save(commit=False)
        document.tender, document.uploaded_by = tender, request.user
        document.save()
        messages.success(request, "Документ загружен.")
    return redirect(tender)


@role_required(Profile.Role.CUSTOMER)
def review_supplier(request, application_pk, decision):
    application = get_object_or_404(SupplierApplication, pk=application_pk)
    if request.method != "POST" or decision not in {"approve", "reject"}:
        raise PermissionDenied
    application.status = SupplierApplication.Status.APPROVED if decision == "approve" else SupplierApplication.Status.REJECTED
    application.reviewed_by, application.reviewed_at = request.user, timezone.now()
    application.save()
    for profile in application.organization.profiles.all():
        Notification.objects.create(user=profile.user, title=f"Аккредитация: {application.get_status_display()}", url="/dashboard/")
    audit(request.user, "supplier.reviewed", application, decision=decision)
    return redirect("dashboard")


@role_required(Profile.Role.CUSTOMER)
@transaction.atomic
def select_winner(request, tender_pk, bid_pk):
    if request.method != "POST":
        raise PermissionDenied
    tender = get_object_or_404(Tender, pk=tender_pk, owner=request.user)
    bid = get_object_or_404(Bid, pk=bid_pk, tender=tender)
    tender.bids.update(status=Bid.Status.REJECTED)
    bid.status = Bid.Status.WINNER
    bid.save(update_fields=["status"])
    tender.status = Tender.Status.COMPLETED
    tender.save(update_fields=["status"])
    for participant in tender.bids.select_related("supplier"):
        Notification.objects.create(user=participant.supplier, title=f"Результаты тендера {tender.number}", url=tender.get_absolute_url())
    audit(request.user, "winner.selected", bid)
    messages.success(request, f"Победитель выбран: {bid.supplier.profile.company_name}.")
    return redirect(tender)


@login_required
def notifications(request):
    request.user.notifications.update(is_read=True)
    return render(request, "procurement/notifications.html", {"notifications": request.user.notifications.all()})


@role_required(Profile.Role.CUSTOMER)
def supplier_registry(request):
    applications = SupplierApplication.objects.select_related("organization", "reviewed_by")
    return render(request, "procurement/supplier_registry.html", {"applications": applications})
