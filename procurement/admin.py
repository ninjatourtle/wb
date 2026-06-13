from django.contrib import admin
from .models import (
    AuditEvent, Bid, Membership, Notification, Organization, Profile, Question,
    SupplierApplication, Tender, TenderDocument, TenderLot,
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


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "organization", "action", "object_type", "object_id")
    list_filter = ("action", "object_type")
    readonly_fields = ("created_at",)
