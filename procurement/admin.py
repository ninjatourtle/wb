from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import (
    AuditEvent, Bid, BidFraudSignal, BidLot, Contract, LoginEvent, Membership, Notification, Organization, ProcurementProtocol, Profile, Question,
    ImportedTender, SupplierApplication, SupplierDocument, Tender, TenderApproval, TenderDocument,
    TenderImportRun, TenderImportSource, TenderLot, TenderNumberSequence, TenderTemplate, TenderTemplateLot, TenderWinnerSelection,
)

admin.site.site_header = "WB Tender — администрирование"
admin.site.site_title = "WB Tender Admin"
admin.site.index_title = "Управление закупочной площадкой"

ADMIN_MODEL_NAMES = {
    AuditEvent: ("событие аудита", "события аудита"),
    Bid: ("предложение", "предложения"),
    BidFraudSignal: ("антифрод-сигнал", "антифрод-сигналы"),
    BidLot: ("предложение по лоту", "предложения по лотам"),
    Contract: ("договор", "договоры"),
    ImportedTender: ("импортированная закупка", "импортированные закупки"),
    LoginEvent: ("событие входа", "история входов"),
    Membership: ("сотрудник организации", "сотрудники организаций"),
    Notification: ("уведомление", "уведомления"),
    Organization: ("организация", "организации"),
    ProcurementProtocol: ("протокол", "протоколы"),
    Profile: ("профиль пользователя", "профили пользователей"),
    Question: ("вопрос участника", "вопросы участников"),
    SupplierApplication: ("заявка на аккредитацию", "заявки на аккредитацию"),
    SupplierDocument: ("документ поставщика", "документы поставщиков"),
    Tender: ("закупка", "закупки"),
    TenderApproval: ("согласование закупки", "согласования закупок"),
    TenderDocument: ("документ закупки", "документы закупок"),
    TenderImportSource: ("источник импорта", "источники импорта"),
    TenderImportRun: ("запуск импорта", "запуски импорта"),
    TenderLot: ("лот закупки", "лоты закупок"),
    TenderNumberSequence: ("счетчик номеров", "счетчики номеров"),
    TenderTemplate: ("шаблон закупки", "шаблоны закупок"),
    TenderTemplateLot: ("лот шаблона", "лоты шаблонов"),
    TenderWinnerSelection: ("выбранный победитель", "выбранные победители"),
}
for model, (singular, plural) in ADMIN_MODEL_NAMES.items():
    model._meta.verbose_name = singular
    model._meta.verbose_name_plural = plural


class BaseAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_max_show_all = 200
    show_full_result_count = False
    save_on_top = True


admin.site.unregister(User)


@admin.register(User)
class PlatformUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_active", "is_staff", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")
    actions = ("block_users", "unblock_users")

    @admin.action(description="Заблокировать выбранные учетные записи")
    def block_users(self, request, queryset):
        queryset.exclude(pk=request.user.pk).update(is_active=False)

    @admin.action(description="Разблокировать выбранные учетные записи")
    def unblock_users(self, request, queryset):
        queryset.update(is_active=True)


class TenderLotInline(admin.TabularInline):
    model = TenderLot
    extra = 0


class TenderDocumentInline(admin.TabularInline):
    model = TenderDocument
    extra = 0


class BidLotInline(admin.TabularInline):
    model = BidLot
    extra = 0


class TenderTemplateLotInline(admin.TabularInline):
    model = TenderTemplateLot
    extra = 0


@admin.register(Profile)
class ProfileAdmin(BaseAdmin):
    list_display = ("company_name", "role", "inn", "user")
    list_filter = ("role",)
    search_fields = ("company_name", "inn", "user__username")
    list_select_related = ("user", "organization")


@admin.register(Tender)
class TenderAdmin(BaseAdmin):
    list_display = ("number", "title", "organization", "procedure", "budget", "deadline", "status")
    list_filter = ("status", "category", "procedure", "publish_results", "organization")
    search_fields = ("number", "title", "description", "organization__name", "owner__username")
    list_select_related = ("owner", "organization")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    inlines = (TenderLotInline, TenderDocumentInline)


@admin.register(Bid)
class BidAdmin(BaseAdmin):
    list_display = ("tender", "supplier", "price", "delivery_days", "status", "submitted_at")
    list_filter = ("status", "tender__status", "submitted_at")
    search_fields = ("tender__number", "tender__title", "supplier__username", "supplier__profile__company_name")
    list_select_related = ("tender", "supplier")
    date_hierarchy = "submitted_at"
    inlines = (BidLotInline,)


@admin.register(BidFraudSignal)
class BidFraudSignalAdmin(BaseAdmin):
    list_display = ("tender", "bid", "related_bid", "kind", "created_at")
    list_filter = ("kind", "tender__organization", "created_at")
    search_fields = ("tender__number", "bid__supplier__username", "related_bid__supplier__username", "value")
    list_select_related = ("tender", "bid", "related_bid")


@admin.register(Organization)
class OrganizationAdmin(BaseAdmin):
    list_display = ("name", "kind", "inn", "contact_email", "phone", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("name", "inn", "kpp", "contact_email", "phone")
    date_hierarchy = "created_at"


@admin.register(Membership)
class MembershipAdmin(BaseAdmin):
    list_display = ("user", "organization", "role", "is_active")
    list_filter = ("role", "is_active", "organization")
    search_fields = ("user__username", "user__email", "organization__name")
    list_select_related = ("user", "organization")


@admin.register(SupplierApplication)
class SupplierApplicationAdmin(BaseAdmin):
    list_display = ("organization", "customer", "status", "submitted_at", "reviewed_at")
    list_filter = ("status", "customer", "submitted_at")
    search_fields = ("organization__name", "organization__inn", "customer__name")
    list_select_related = ("organization", "customer", "reviewed_by")
    date_hierarchy = "submitted_at"


@admin.register(Question)
class QuestionAdmin(BaseAdmin):
    list_display = ("tender", "author", "answered_by", "created_at", "answered_at")
    list_filter = ("created_at", "answered_at")
    search_fields = ("tender__number", "tender__title", "text", "answer", "author__username")
    list_select_related = ("tender", "author", "answered_by")


@admin.register(Notification)
class NotificationAdmin(BaseAdmin):
    list_display = ("title", "user", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("title", "message", "user__username")
    list_select_related = ("user",)


@admin.register(Contract)
class ContractAdmin(BaseAdmin):
    list_display = ("number", "tender", "customer", "supplier", "amount", "status", "created_at")
    list_filter = ("status", "customer", "supplier")
    search_fields = ("number", "tender__number", "tender__title", "customer__name", "supplier__name")
    list_select_related = ("tender", "customer", "supplier", "winning_bid")


@admin.register(TenderApproval)
class TenderApprovalAdmin(BaseAdmin):
    list_display = ("tender", "requested_by", "reviewer", "decision", "requested_at", "reviewed_at")
    list_filter = ("decision", "requested_at")
    search_fields = ("tender__number", "tender__title", "requested_by__username", "reviewer__username")
    list_select_related = ("tender", "requested_by", "reviewer")


@admin.register(TenderWinnerSelection)
class TenderWinnerSelectionAdmin(BaseAdmin):
    list_display = ("tender", "bid", "selected_by", "selected_at")
    list_filter = ("tender__organization", "selected_at")
    search_fields = ("tender__number", "bid__supplier__username", "bid__supplier__profile__company_name")
    list_select_related = ("tender", "bid", "selected_by")


@admin.register(ProcurementProtocol)
class ProcurementProtocolAdmin(BaseAdmin):
    list_display = ("number", "tender", "kind", "created_by", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("number", "tender__number", "tender__title")
    readonly_fields = ("created_at",)


@admin.register(TenderLot)
class TenderLotAdmin(BaseAdmin):
    list_display = ("title", "tender", "quantity", "unit", "budget")
    search_fields = ("title", "tender__number", "tender__title", "external_id")
    list_select_related = ("tender",)


@admin.register(TenderDocument)
class TenderDocumentAdmin(BaseAdmin):
    list_display = ("title", "tender", "visibility", "uploaded_by", "uploaded_at")
    list_filter = ("visibility", "uploaded_at")
    search_fields = ("title", "tender__number", "tender__title")
    list_select_related = ("tender", "uploaded_by")


@admin.register(SupplierDocument)
class SupplierDocumentAdmin(BaseAdmin):
    list_display = ("title", "organization", "kind", "expires_at", "uploaded_by", "uploaded_at")
    list_filter = ("kind", "expires_at", "uploaded_at")
    search_fields = ("title", "organization__name", "organization__inn")
    list_select_related = ("organization", "uploaded_by")


@admin.register(BidLot)
class BidLotAdmin(BaseAdmin):
    list_display = ("bid", "lot", "price", "delivery_days")
    search_fields = ("bid__tender__number", "bid__supplier__username", "lot__title")
    list_select_related = ("bid", "lot")


@admin.register(TenderTemplate)
class TenderTemplateAdmin(BaseAdmin):
    list_display = ("name", "organization", "title", "category", "procedure", "created_at")
    list_filter = ("organization", "category", "procedure")
    search_fields = ("name", "title", "organization__name")
    inlines = (TenderTemplateLotInline,)


admin.site.register(TenderNumberSequence, BaseAdmin)
admin.site.register(TenderTemplateLot, BaseAdmin)


@admin.register(TenderImportSource)
class TenderImportSourceAdmin(BaseAdmin):
    list_display = ("name", "adapter", "organization", "is_active", "last_synced_at", "last_error")
    list_filter = ("adapter", "is_active", "organization")
    search_fields = ("name", "url")


@admin.register(TenderImportRun)
class TenderImportRunAdmin(BaseAdmin):
    list_display = ("created_at", "source", "trigger", "status", "requested_by", "finished_at")
    list_filter = ("status", "trigger", "source")
    search_fields = ("source__name", "error", "requested_by__username")
    readonly_fields = ("source", "trigger", "status", "requested_by", "result", "error", "started_at", "finished_at", "created_at")
    list_select_related = ("source", "requested_by")


@admin.register(ImportedTender)
class ImportedTenderAdmin(BaseAdmin):
    list_display = ("external_id", "source", "tender", "last_seen_at", "last_changed_at")
    list_filter = ("source",)
    search_fields = ("external_id", "tender__number", "tender__title")
    readonly_fields = ("payload_hash", "raw_data", "first_seen_at", "last_seen_at", "last_changed_at")


@admin.register(AuditEvent)
class AuditEventAdmin(BaseAdmin):
    list_display = ("created_at", "user", "organization", "action", "object_type", "object_id")
    list_filter = ("action", "object_type", "organization", "created_at")
    search_fields = ("action", "object_type", "object_id", "user__username", "organization__name")
    readonly_fields = ("user", "organization", "action", "object_type", "object_id", "details", "created_at")
    date_hierarchy = "created_at"


@admin.register(LoginEvent)
class LoginEventAdmin(BaseAdmin):
    list_display = ("created_at", "username", "user", "ip_address", "device_fingerprint", "success")
    list_filter = ("success", "created_at")
    search_fields = ("username", "user__username", "ip_address")
    readonly_fields = ("user", "username", "ip_address", "user_agent", "device_fingerprint", "success", "created_at")
    date_hierarchy = "created_at"
