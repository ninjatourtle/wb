from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from procurement.models import (
    Bid, Membership, Organization, Profile, Question, SupplierApplication, Tender, TenderLot,
)


class Command(BaseCommand):
    help = "Создает демонстрационных пользователей и тендеры"

    def handle(self, *args, **options):
        customer, _ = User.objects.get_or_create(username="customer", defaults={"email": "customer@example.ru"})
        customer.set_password("demo12345")
        customer.save()
        customer_org, _ = Organization.objects.update_or_create(
            inn="7701234567",
            defaults={"name": "ООО «Северная компания»", "kind": Organization.Kind.CUSTOMER, "contact_email": "customer@example.ru"},
        )
        Profile.objects.update_or_create(
            user=customer,
            defaults={"company_name": customer_org.name, "inn": customer_org.inn, "role": Profile.Role.CUSTOMER, "organization": customer_org},
        )
        Membership.objects.update_or_create(user=customer, organization=customer_org)
        suppliers = []
        for idx, (username, company) in enumerate([("supplier", "ООО «ТехПоставка»"), ("partner", "АО «ПромРесурс»")]):
            user, _ = User.objects.get_or_create(username=username)
            user.set_password("demo12345")
            user.save()
            org, _ = Organization.objects.update_or_create(
                inn=f"770000000{idx + 1}", defaults={"name": company, "kind": Organization.Kind.SUPPLIER, "contact_email": f"{username}@example.ru"}
            )
            Profile.objects.update_or_create(user=user, defaults={"company_name": company, "inn": org.inn, "role": Profile.Role.SUPPLIER, "organization": org})
            Membership.objects.update_or_create(user=user, organization=org)
            SupplierApplication.objects.update_or_create(organization=org, defaults={"status": SupplierApplication.Status.APPROVED, "reviewed_by": customer, "reviewed_at": timezone.now()})
            suppliers.append(user)

        examples = [
            ("TF-2026-014", "Поставка серверного оборудования", Tender.Category.IT, "4850000", "Поставка серверов и систем хранения данных для нового центра обработки.", "Москва, ул. Деловая, 12"),
            ("TF-2026-015", "Техническое обслуживание офисов", Tender.Category.SERVICES, "1800000", "Комплексное обслуживание инженерных систем трех офисных площадок.", "Москва"),
            ("TF-2026-016", "Поставка спецодежды для персонала", Tender.Category.GOODS, "950000", "Летние и зимние комплекты спецодежды по техническому заданию.", "Тула"),
            ("TF-2026-017", "Ремонт складского комплекса", Tender.Category.CONSTRUCTION, "7200000", "Ремонт кровли и внутренних помещений складского комплекса.", "Московская область"),
        ]
        for index, (number, title, category, budget, description, address) in enumerate(examples):
            tender, _ = Tender.objects.update_or_create(
                number=number,
                defaults={
                    "owner": customer,
                    "organization": customer_org,
                    "title": title,
                    "category": category,
                    "budget": Decimal(budget),
                    "description": description,
                    "requirements": "Опыт аналогичных поставок от 2 лет. Предоставление реквизитов и референсов.",
                    "delivery_address": address,
                    "deadline": timezone.now() + timedelta(days=5 + index * 2),
                    "status": Tender.Status.PUBLISHED,
                    "procedure": Tender.Procedure.AUCTION if index in (0, 3) else Tender.Procedure.CLOSED,
                    "auction_step": Decimal("50000") if index in (0, 3) else None,
                },
            )
            TenderLot.objects.update_or_create(tender=tender, title=title, defaults={"description": description, "budget": Decimal(budget), "quantity": 1})
            if index == 0:
                Bid.objects.update_or_create(tender=tender, supplier=suppliers[0], defaults={"price": 4620000, "delivery_days": 21, "warranty_months": 24})
                Bid.objects.update_or_create(tender=tender, supplier=suppliers[1], defaults={"price": 4750000, "delivery_days": 14, "warranty_months": 36})
                Question.objects.update_or_create(tender=tender, author=suppliers[0], defaults={"text": "Допускается ли поставка эквивалентного оборудования?", "answer": "Да, при полном соответствии техническим требованиям.", "answered_by": customer, "answered_at": timezone.now()})
        self.stdout.write(self.style.SUCCESS("Демоданные созданы. Пароль всех пользователей: demo12345"))
