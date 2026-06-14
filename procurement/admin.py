from django.contrib import admin
from .models import (
    AuditEvent, Bid, BidLot, Contract, Membership, Notification, Organization, ProcurementProtocol, Profile, Question,
    ImportedTender, SupplierApplication, SupplierDocument, Tender, TenderApproval, TenderDocument,
    TenderImportSource, TenderLot,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "role", "inn", "user")
    list_filter = ("role",)
    search_fields = ("company_name", "inn", "user__username")


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "owner", "budget", "deadline", "status")
    list_filter = ("status", "category")
    search_fields = ("number", "title", "owner__profile__company_name")
    list_per_page = 50
    list_max_show_all = 200
    show_full_result_count = False
    ordering = ("-created_at",)


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("tender", "supplier", "price", "delivery_days", "status", "submitted_at")
    list_filter = ("status",)


admin.site.register(Organization)
admin.site.register(Membership)
admin.site.register(SupplierApplication)
admin.site.register(TenderLot)
admin.site.register(TenderDocument)
admin.site.register(Question)
admin.site.register(Notification)
admin.site.register(Contract)
admin.site.register(SupplierDocument)
admin.site.register(TenderApproval)
admin.site.register(ProcurementProtocol)
admin.site.register(BidLot)


@admin.register(TenderImportSource)
class TenderImportSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "adapter", "organization", "is_active", "last_synced_at", "last_error")
    list_filter = ("adapter", "is_active", "organization")
    search_fields = ("name", "url")


@admin.register(ImportedTender)
class ImportedTenderAdmin(admin.ModelAdmin):
    list_display = ("external_id", "source", "tender", "last_seen_at", "last_changed_at")
    list_filter = ("source",)
    search_fields = ("external_id", "tender__number", "tender__title")
    readonly_fields = ("payload_hash", "raw_data", "first_seen_at", "last_seen_at", "last_changed_at")
    list_per_page = 50
    list_max_show_all = 200
    show_full_result_count = False


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "organization", "action", "object_type", "object_id")
    list_filter = ("action", "object_type")
    readonly_fields = ("created_at",)
