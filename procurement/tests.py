from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Bid, Organization, Profile, SupplierApplication, Tender


class ProcurementFlowTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user("customer", password="testpass123")
        customer_org = Organization.objects.create(name="Заказчик", kind=Organization.Kind.CUSTOMER)
        Profile.objects.create(user=self.customer, company_name="Заказчик", role=Profile.Role.CUSTOMER, organization=customer_org)
        self.supplier = User.objects.create_user("supplier", password="testpass123")
        supplier_org = Organization.objects.create(name="Поставщик", kind=Organization.Kind.SUPPLIER)
        Profile.objects.create(user=self.supplier, company_name="Поставщик", role=Profile.Role.SUPPLIER, organization=supplier_org)
        SupplierApplication.objects.create(organization=supplier_org, status=SupplierApplication.Status.APPROVED)
        self.tender = Tender.objects.create(
            owner=self.customer,
            title="Поставка оборудования",
            number="T-001",
            category=Tender.Category.GOODS,
            description="Описание",
            delivery_address="Москва",
            budget=100000,
            deadline=timezone.now() + timedelta(days=5),
            status=Tender.Status.PUBLISHED,
        )

    def test_supplier_can_submit_bid(self):
        self.client.login(username="supplier", password="testpass123")
        response = self.client.post(
            reverse("bid_submit", args=[self.tender.pk]),
            {"price": 90000, "delivery_days": 10, "warranty_months": 12, "comment": "Готовы"},
        )
        self.assertRedirects(response, self.tender.get_absolute_url())
        self.assertTrue(Bid.objects.filter(tender=self.tender, supplier=self.supplier).exists())

    def test_supplier_cannot_create_tender(self):
        self.client.login(username="supplier", password="testpass123")
        response = self.client.get(reverse("tender_create"))
        self.assertEqual(response.status_code, 403)

    def test_customer_selects_winner(self):
        bid = Bid.objects.create(tender=self.tender, supplier=self.supplier, price=90000, delivery_days=10)
        self.client.login(username="customer", password="testpass123")
        response = self.client.post(reverse("select_winner", args=[self.tender.pk, bid.pk]))
        self.assertRedirects(response, self.tender.get_absolute_url())
        bid.refresh_from_db()
        self.tender.refresh_from_db()
        self.assertEqual(bid.status, Bid.Status.WINNER)
        self.assertEqual(self.tender.status, Tender.Status.COMPLETED)

    def test_closed_bids_hidden_from_customer_while_open(self):
        Bid.objects.create(tender=self.tender, supplier=self.supplier, price=90000, delivery_days=10)
        self.client.login(username="customer", password="testpass123")
        response = self.client.get(self.tender.get_absolute_url())
        self.assertContains(response, "будут доступны после завершения")
        self.assertNotContains(response, "90000")

    def test_auction_bid_must_beat_best_price(self):
        self.tender.procedure = Tender.Procedure.AUCTION
        self.tender.save()
        other = User.objects.create_user("other", password="testpass123")
        other_org = Organization.objects.create(name="Другой", kind=Organization.Kind.SUPPLIER)
        Profile.objects.create(user=other, company_name="Другой", role=Profile.Role.SUPPLIER, organization=other_org)
        Bid.objects.create(tender=self.tender, supplier=other, price=90000, delivery_days=10)
        self.client.login(username="supplier", password="testpass123")
        response = self.client.post(reverse("bid_submit", args=[self.tender.pk]), {"price": 95000, "delivery_days": 8, "warranty_months": 12})
        self.assertContains(response, "Ставка должна быть ниже")
        self.assertFalse(Bid.objects.filter(tender=self.tender, supplier=self.supplier).exists())

    def test_unapproved_supplier_cannot_bid(self):
        self.supplier.profile.organization.supplier_application.status = SupplierApplication.Status.PENDING
        self.supplier.profile.organization.supplier_application.save()
        self.client.login(username="supplier", password="testpass123")
        response = self.client.get(reverse("bid_submit", args=[self.tender.pk]))
        self.assertRedirects(response, reverse("dashboard"))
