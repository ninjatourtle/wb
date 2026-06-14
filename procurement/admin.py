from django.contrib import admin
from .models import (
    AuditEvent, Bid, BidLot, Contract, Membership, Notification, Organization, ProcurementProtocol, Profile, Question,
    ImportedTender, SupplierApplication, SupplierDocument, Tender, TenderApproval, TenderDocument,
    TenderImportSource, TenderLot, TenderNumberSequence, TenderTemplate, TenderTemplateLot,
)

admin.site.site_header = "WB Tender — администрирование"
admin.site.site_title = "WB Tender Admin"
admin.site.index_title = "Управление закупочной площадкой"

ADMIN_MODEL_NAMES = {
    AuditEvent: ("событие аудита", "события аудита"),
    Bid: ("предложение", "предложения"),
    BidLot: ("предложение по лоту", "предложения по лотам"),
    Contract: ("договор", "договоры"),
    ImportedTender: ("импортированная закупка", "импортированные закупки"),
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
    TenderLot: ("лот закупки", "лоты закупок"),
    TenderNumberSequence: ("счетчик номеров", "счетчики номеров"),
    TenderTemplate: ("шаблон закупки", "шаблоны закупок"),
    TenderTemplateLot: ("лот шаблона", "лоты шаблонов"),
}
for model, (singular, plural) in ADMIN_MODEL_NAMES.items():
    model._meta.verbose_name = singular
    model._meta.verbose_name_plural = plural


class BaseAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_max_show_all = 200
    show_full_result_count = False
    save_on_top = True


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
    list_display = ("title", "organization", "kind", "uploaded_by", "uploaded_at")
    list_filter = ("kind", "uploaded_at")
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
