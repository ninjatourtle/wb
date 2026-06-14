from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Organization(models.Model):
    class Kind(models.TextChoices):
        CUSTOMER = "customer", "Заказчик"
        SUPPLIER = "supplier", "Поставщик"

    name = models.CharField("Название", max_length=200)
    kind = models.CharField("Тип", max_length=16, choices=Kind.choices)
    inn = models.CharField("ИНН", max_length=12, blank=True, null=True)
    kpp = models.CharField("КПП", max_length=9, blank=True)
    legal_address = models.CharField("Юридический адрес", max_length=300, blank=True)
    contact_email = models.EmailField("Контактный email", blank=True)
    phone = models.CharField("Телефон", max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["inn"],
                condition=models.Q(inn__isnull=False) & ~models.Q(inn=""),
                name="unique_nonempty_organization_inn",
            )
        ]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Владелец"
        MANAGER = "manager", "Менеджер"
        REVIEWER = "reviewer", "Эксперт"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.OWNER)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="one_membership_per_org")
        ]


class Profile(models.Model):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Заказчик"
        SUPPLIER = "supplier", "Поставщик"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=16, choices=Role.choices)
    company_name = models.CharField("Компания", max_length=200)
    inn = models.CharField("ИНН", max_length=12, blank=True)
    phone = models.CharField("Телефон", max_length=32, blank=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name="profiles"
    )

    def __str__(self):
        return self.company_name


class Tender(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        APPROVAL = "approval", "На согласовании"
        PUBLISHED = "published", "Прием заявок"
        REVIEW = "review", "Рассмотрение"
        COMPLETED = "completed", "Завершен"
        CANCELLED = "cancelled", "Отменен"

    class Category(models.TextChoices):
        GOODS = "goods", "Товары"
        SERVICES = "services", "Услуги"
        CONSTRUCTION = "construction", "Строительство"
        IT = "it", "ИТ и телеком"
        OTHER = "other", "Другое"

    class Procedure(models.TextChoices):
        CLOSED = "closed", "Закрытый конкурс"
        AUCTION = "auction", "Открытый аукцион"

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tenders")
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, null=True, blank=True, related_name="tenders"
    )
    title = models.CharField("Название", max_length=250)
    number = models.CharField("Номер", max_length=40)
    category = models.CharField("Категория", max_length=20, choices=Category.choices)
    description = models.TextField("Описание")
    requirements = models.TextField("Требования к поставщику", blank=True)
    delivery_address = models.CharField("Место поставки", max_length=300)
    budget = models.DecimalField(
        "Начальная цена", max_digits=14, decimal_places=2, validators=[MinValueValidator(0)]
    )
    deadline = models.DateTimeField("Окончание приема заявок")
    procedure = models.CharField(
        "Формат процедуры", max_length=16, choices=Procedure.choices, default=Procedure.CLOSED
    )
    auction_step = models.DecimalField(
        "Шаг аукциона", max_digits=14, decimal_places=2, null=True, blank=True
    )
    publish_results = models.BooleanField("Публиковать результаты", default=True)
    favorites = models.ManyToManyField(User, blank=True, related_name="favorite_tenders")
    status = models.CharField("Статус", max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="unique_tender_number_per_org")
        ]

    def __str__(self):
        return f"{self.number}: {self.title}"

    def get_absolute_url(self):
        return reverse("tender_detail", kwargs={"pk": self.pk})

    @property
    def is_open(self):
        return self.status == self.Status.PUBLISHED and self.deadline > timezone.now()

    @property
    def best_price(self):
        return self.bids.aggregate(models.Min("price"))["price__min"]

    def user_can_manage(self, user):
        if not user.is_authenticated or not self.organization_id:
            return self.owner_id == user.id
        return Membership.objects.filter(
            organization_id=self.organization_id,
            user=user,
            is_active=True,
            role__in=[Membership.Role.OWNER, Membership.Role.MANAGER],
        ).exists()

    def user_can_review(self, user):
        if not user.is_authenticated or not self.organization_id:
            return self.owner_id == user.id
        return Membership.objects.filter(
            organization_id=self.organization_id,
            user=user,
            is_active=True,
            role__in=[Membership.Role.OWNER, Membership.Role.MANAGER, Membership.Role.REVIEWER],
        ).exists()


class TenderImportSource(models.Model):
    class Adapter(models.TextChoices):
        JSON = "json", "Универсальный JSON API"
        BIDZAAR = "bidzaar", "Bidzaar"

    name = models.CharField("Название источника", max_length=120, unique=True)
    url = models.URLField("URL JSON API", max_length=500)
    adapter = models.CharField(
        "Адаптер", max_length=20, choices=Adapter.choices, default=Adapter.JSON
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="tender_import_sources"
    )
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="tender_import_sources")
    is_active = models.BooleanField("Активен", default=True)
    items_path = models.CharField(
        "Путь к списку", max_length=120, blank=True, help_text="Например: result.items"
    )
    auth_header = models.CharField(
        "Заголовок авторизации", max_length=80, blank=True, help_text="Например: Authorization"
    )
    auth_env_var = models.CharField(
        "Переменная окружения с токеном", max_length=120, blank=True
    )
    field_mapping = models.JSONField(
        "Соответствие полей",
        default=dict,
        blank=True,
        help_text='Например: {"external_id": "id", "title": "name", "deadline": "end_at"}',
    )
    status_mapping = models.JSONField(
        "Соответствие статусов", default=dict, blank=True
    )
    cancel_missing = models.BooleanField(
        "Отменять пропавшие тендеры",
        default=False,
        help_text="Включайте только если API всегда возвращает полный список актуальных тендеров.",
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ImportedTender(models.Model):
    source = models.ForeignKey(
        TenderImportSource, on_delete=models.CASCADE, related_name="imported_tenders"
    )
    external_id = models.CharField("ID во внешней системе", max_length=200)
    tender = models.OneToOneField(
        Tender, on_delete=models.CASCADE, related_name="import_record"
    )
    external_url = models.URLField("Ссылка на источник", max_length=500, blank=True)
    payload_hash = models.CharField(max_length=64, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    last_changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"], name="unique_external_tender_per_source"
            )
        ]

    def __str__(self):
        return f"{self.source}: {self.external_id}"


class TenderLot(models.Model):
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="lots")
    external_id = models.CharField("ID во внешней системе", max_length=200, blank=True)
    title = models.CharField("Название лота", max_length=250)
    description = models.TextField("Описание", blank=True)
    quantity = models.DecimalField("Количество", max_digits=12, decimal_places=2, default=1)
    unit = models.CharField("Единица измерения", max_length=30, default="шт.")
    budget = models.DecimalField("Начальная цена", max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tender", "external_id"],
                condition=~models.Q(external_id=""),
                name="unique_external_lot_per_tender",
            )
        ]

    def __str__(self):
        return self.title


class TenderApproval(models.Model):
    class Decision(models.TextChoices):
        PENDING = "pending", "Ожидает решения"
        APPROVED = "approved", "Согласовано"
        REJECTED = "rejected", "Отклонено"

    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="approvals")
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="requested_tender_approvals")
    reviewer = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_tender_approvals"
    )
    decision = models.CharField(max_length=16, choices=Decision.choices, default=Decision.PENDING)
    comment = models.TextField("Комментарий", blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)


class TenderDocument(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = "public", "Всем участникам"
        CUSTOMER = "customer", "Только заказчику"

    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField("Название", max_length=200)
    file = models.FileField("Файл", upload_to="tenders/%Y/%m/")
    visibility = models.CharField(
        "Доступ", max_length=16, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class SupplierApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        APPROVED = "approved", "Аккредитован"
        REJECTED = "rejected", "Отклонен"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="supplier_applications"
    )
    customer = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="supplier_accreditations"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    comment = models.TextField("Комментарий", blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "customer"], name="one_supplier_application_per_customer"
            )
        ]


class SupplierDocument(models.Model):
    class Kind(models.TextChoices):
        CHARTER = "charter", "Учредительный документ"
        LICENSE = "license", "Лицензия или разрешение"
        TAX = "tax", "Налоговый документ"
        OTHER = "other", "Другой документ"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="supplier_documents")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.OTHER)
    title = models.CharField("Название", max_length=200)
    file = models.FileField("Файл", upload_to="suppliers/%Y/%m/")
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class Question(models.Model):
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="questions")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField("Вопрос")
    answer = models.TextField("Ответ", blank=True)
    answered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="answered_questions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AuditEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Contract(models.Model):
    class Status(models.TextChoices):
        PREPARATION = "preparation", "Подготовка"
        SIGNED = "signed", "Подписан"
        COMPLETED = "completed", "Исполнен"
        TERMINATED = "terminated", "Расторгнут"

    number = models.CharField("Номер договора", max_length=50, unique=True)
    tender = models.OneToOneField(Tender, on_delete=models.PROTECT, related_name="contract")
    winning_bid = models.OneToOneField("Bid", on_delete=models.PROTECT, related_name="contract")
    customer = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="customer_contracts")
    supplier = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="supplier_contracts")
    amount = models.DecimalField("Сумма", max_digits=14, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PREPARATION)
    created_at = models.DateTimeField(auto_now_add=True)
    signed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.number

    class Meta:
        ordering = ["-created_at"]


class ProcurementProtocol(models.Model):
    class Kind(models.TextChoices):
        RESULTS = "results", "Протокол подведения итогов"
        CANCELLATION = "cancellation", "Протокол отмены"

    tender = models.ForeignKey(Tender, on_delete=models.PROTECT, related_name="protocols")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    number = models.CharField(max_length=60, unique=True)
    data = models.JSONField(default=dict)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Bid(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Подана"
        WINNER = "winner", "Победитель"
        REJECTED = "rejected", "Не выбрана"

    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="bids")
    supplier = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bids")
    price = models.DecimalField(
        "Цена предложения", max_digits=14, decimal_places=2, validators=[MinValueValidator(0)]
    )
    delivery_days = models.PositiveIntegerField("Срок поставки, дней")
    warranty_months = models.PositiveIntegerField("Гарантия, месяцев", default=0)
    comment = models.TextField("Комментарий", blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUBMITTED)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price", "delivery_days"]
        constraints = [
            models.UniqueConstraint(fields=["tender", "supplier"], name="one_bid_per_supplier")
        ]

    def __str__(self):
        return f"{self.supplier} → {self.tender.number}"


class BidLot(models.Model):
    bid = models.ForeignKey(Bid, on_delete=models.CASCADE, related_name="lot_offers")
    lot = models.ForeignKey(
        TenderLot, verbose_name="Лот", on_delete=models.PROTECT, related_name="bid_offers"
    )
    price = models.DecimalField(
        "Цена по лоту", max_digits=14, decimal_places=2, validators=[MinValueValidator(0)]
    )
    delivery_days = models.PositiveIntegerField("Срок поставки, дней")
    comment = models.TextField("Комментарий", blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["bid", "lot"], name="one_offer_per_bid_lot")
        ]
