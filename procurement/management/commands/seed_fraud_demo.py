from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from procurement.models import Bid, LoginEvent, Membership, Organization, Profile, SupplierApplication, Tender
from procurement.services import refresh_bid_fraud_signals


class Command(BaseCommand):
    help = "Создает две демонстрационные компании с общими IP и fingerprint для проверки антифрода"

    def handle(self, *args, **options):
        customer = Organization.objects.filter(kind=Organization.Kind.CUSTOMER).order_by("pk").first()
        tender = Tender.objects.filter(organization=customer, status=Tender.Status.PUBLISHED).order_by("deadline", "pk").first() if customer else None
        if not customer or not tender:
            self.stderr.write("Не найдена открытая закупка организации-заказчика.")
            return

        shared_ip = "198.51.100.24"
        fingerprint = "d" * 64
        for index, (username, name, inn) in enumerate((
            ("fraud-demo-alpha", "ООО «Демо Альфа»", "9900000001"),
            ("fraud-demo-beta", "ООО «Демо Бета»", "9900000002"),
        )):
            user, _ = User.objects.get_or_create(username=username, defaults={"email": f"{username}@example.test"})
            user.set_password("demo12345")
            user.save(update_fields=["password"])
            organization, _ = Organization.objects.update_or_create(
                inn=inn,
                defaults={"name": name, "kind": Organization.Kind.SUPPLIER, "contact_email": user.email},
            )
            Profile.objects.update_or_create(
                user=user,
                defaults={"company_name": name, "inn": inn, "role": Profile.Role.SUPPLIER, "organization": organization},
            )
            Membership.objects.update_or_create(user=user, organization=organization, defaults={"role": Membership.Role.OWNER, "is_active": True})
            SupplierApplication.objects.update_or_create(
                organization=organization,
                customer=customer,
                defaults={"status": SupplierApplication.Status.APPROVED, "reviewed_at": timezone.now()},
            )
            LoginEvent.objects.update_or_create(
                user=user,
                device_fingerprint=fingerprint,
                defaults={"username": username, "ip_address": shared_ip, "user_agent": "TenderFlow fraud demo", "success": True},
            )
            Bid.objects.update_or_create(
                tender=tender,
                supplier=user,
                defaults={"price": tender.budget - Decimal("10000") - Decimal(index * 1000), "delivery_days": 10 + index, "warranty_months": 12},
            )

        count = refresh_bid_fraud_signals(tender.pk)
        self.stdout.write(self.style.SUCCESS(f"Созданы демо-поставщики. Сигналов в закупке {tender.number}: {count}"))
