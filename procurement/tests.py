from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Bid, Contract, Membership, Organization, ProcurementProtocol, Profile, SupplierApplication,
    ImportedTender, SupplierDocument, Tender, TenderApproval, TenderDocument, TenderImportSource,
    TenderLot,
)
from .forms import TenderDocumentForm
from .imports import fetch_bidzaar_items, sync_source


class ProcurementFlowTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user("customer", password="testpass123")
        customer_org = Organization.objects.create(name="Заказчик", kind=Organization.Kind.CUSTOMER)
        Profile.objects.create(user=self.customer, company_name="Заказчик", role=Profile.Role.CUSTOMER, organization=customer_org)
        Membership.objects.create(user=self.customer, organization=customer_org, role=Membership.Role.OWNER)
        self.supplier = User.objects.create_user("supplier", password="testpass123")
        supplier_org = Organization.objects.create(name="Поставщик", kind=Organization.Kind.SUPPLIER)
        Profile.objects.create(user=self.supplier, company_name="Поставщик", role=Profile.Role.SUPPLIER, organization=supplier_org)
        SupplierApplication.objects.create(
            organization=supplier_org,
            customer=customer_org,
            status=SupplierApplication.Status.APPROVED,
        )
        self.tender = Tender.objects.create(
            owner=self.customer,
            organization=customer_org,
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

    def test_supplier_can_submit_bid_for_imported_tender_without_budget(self):
        self.tender.budget = 0
        self.tender.save(update_fields=["budget"])
        source = TenderImportSource.objects.create(
            name="Imported",
            url="https://example.com/tenders",
            organization=self.customer.profile.organization,
            owner=self.customer,
        )
        ImportedTender.objects.create(source=source, external_id="external-1", tender=self.tender)
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
        self.tender.deadline = timezone.now() - timedelta(minutes=1)
        self.tender.status = Tender.Status.REVIEW
        self.tender.save()
        self.client.login(username="customer", password="testpass123")
        response = self.client.post(reverse("select_winner", args=[self.tender.pk, bid.pk]))
        self.assertRedirects(response, self.tender.get_absolute_url())
        bid.refresh_from_db()
        self.tender.refresh_from_db()
        self.assertEqual(bid.status, Bid.Status.WINNER)
        self.assertEqual(self.tender.status, Tender.Status.COMPLETED)
        self.assertTrue(Contract.objects.filter(tender=self.tender, winning_bid=bid).exists())
        self.assertTrue(ProcurementProtocol.objects.filter(tender=self.tender, kind=ProcurementProtocol.Kind.RESULTS).exists())

    def test_customer_cannot_select_winner_before_deadline(self):
        bid = Bid.objects.create(tender=self.tender, supplier=self.supplier, price=90000, delivery_days=10)
        self.client.login(username="customer", password="testpass123")
        response = self.client.post(reverse("select_winner", args=[self.tender.pk, bid.pk]))
        self.assertRedirects(response, self.tender.get_absolute_url())
        self.tender.refresh_from_db()
        self.assertEqual(self.tender.status, Tender.Status.PUBLISHED)
        self.assertFalse(Contract.objects.filter(tender=self.tender).exists())

    def test_closed_bids_hidden_from_customer_while_open(self):
        Bid.objects.create(tender=self.tender, supplier=self.supplier, price=90000, delivery_days=10)
        self.client.login(username="customer", password="testpass123")
        response = self.client.get(self.tender.get_absolute_url())
        self.assertContains(response, "будут доступны после завершения")
        self.assertNotContains(response, "90000")

    def test_auction_hides_supplier_identity_while_showing_best_price(self):
        self.tender.procedure = Tender.Procedure.AUCTION
        self.tender.auction_step = 5000
        self.tender.save(update_fields=["procedure", "auction_step"])
        self.supplier.profile.company_name = "Секретный участник аукциона"
        self.supplier.profile.save(update_fields=["company_name"])
        Bid.objects.create(tender=self.tender, supplier=self.supplier, price=90000, delivery_days=10)
        self.client.login(username="customer", password="testpass123")

        response = self.client.get(self.tender.get_absolute_url())

        self.assertContains(response, "90000")
        self.assertContains(response, "без раскрытия поставщика")
        self.assertNotContains(response, self.supplier.profile.company_name)

    def test_auction_bid_must_beat_best_price(self):
        self.tender.procedure = Tender.Procedure.AUCTION
        self.tender.auction_step = 5000
        self.tender.save()
        other = User.objects.create_user("other", password="testpass123")
        other_org = Organization.objects.create(name="Другой", kind=Organization.Kind.SUPPLIER)
        Profile.objects.create(user=other, company_name="Другой", role=Profile.Role.SUPPLIER, organization=other_org)
        Bid.objects.create(tender=self.tender, supplier=other, price=90000, delivery_days=10)
        self.client.login(username="supplier", password="testpass123")
        response = self.client.post(reverse("bid_submit", args=[self.tender.pk]), {"price": 95000, "delivery_days": 8, "warranty_months": 12})
        self.assertContains(response, "с учетом шага аукциона")
        self.assertFalse(Bid.objects.filter(tender=self.tender, supplier=self.supplier).exists())

    def test_unapproved_supplier_cannot_bid(self):
        application = self.supplier.profile.organization.supplier_applications.get(
            customer=self.customer.profile.organization
        )
        application.status = SupplierApplication.Status.PENDING
        application.save()
        self.client.login(username="supplier", password="testpass123")
        response = self.client.get(reverse("bid_submit", args=[self.tender.pk]))
        self.assertRedirects(response, reverse("dashboard"))

    def test_public_registration_creates_supplier_only(self):
        response = self.client.post(reverse("register"), {
            "username": "new-company",
            "email": "new@example.ru",
            "company_name": "Новый поставщик",
            "inn": "1234567890",
            "phone": "+70000000000",
            "password1": "Complex-pass-123",
            "password2": "Complex-pass-123",
        })
        self.assertRedirects(response, reverse("dashboard"))
        profile = User.objects.get(username="new-company").profile
        self.assertEqual(profile.role, Profile.Role.SUPPLIER)
        self.assertEqual(profile.organization.kind, Organization.Kind.SUPPLIER)

    def test_supplier_cannot_download_customer_document(self):
        document = TenderDocument.objects.create(
            tender=self.tender,
            title="Внутренний документ",
            file=SimpleUploadedFile("private.txt", b"secret"),
            visibility=TenderDocument.Visibility.CUSTOMER,
            uploaded_by=self.customer,
        )
        self.client.login(username="supplier", password="testpass123")
        response = self.client.get(reverse("document_download", args=[document.pk]))
        self.assertEqual(response.status_code, 403)

    def test_customer_organization_manager_can_manage_tender(self):
        manager = User.objects.create_user("manager", password="testpass123")
        Profile.objects.create(
            user=manager,
            company_name="Заказчик",
            role=Profile.Role.CUSTOMER,
            organization=self.customer.profile.organization,
        )
        Membership.objects.create(
            user=manager,
            organization=self.customer.profile.organization,
            role=Membership.Role.MANAGER,
        )
        self.client.login(username="manager", password="testpass123")
        response = self.client.get(self.tender.get_absolute_url())
        self.assertContains(response, "Предложения поставщиков")

    def test_cancelled_tender_rejects_new_bid(self):
        self.tender.status = Tender.Status.CANCELLED
        self.tender.save()
        self.client.login(username="supplier", password="testpass123")
        response = self.client.post(reverse("bid_submit", args=[self.tender.pk]), {
            "price": 80000, "delivery_days": 10, "warranty_months": 12,
        })
        self.assertRedirects(response, self.tender.get_absolute_url())
        self.assertFalse(Bid.objects.filter(tender=self.tender, supplier=self.supplier).exists())

    def test_winner_cannot_be_selected_twice(self):
        first = Bid.objects.create(tender=self.tender, supplier=self.supplier, price=90000, delivery_days=10)
        other = User.objects.create_user("second-supplier", password="testpass123")
        other_org = Organization.objects.create(name="Второй", kind=Organization.Kind.SUPPLIER)
        Profile.objects.create(user=other, company_name="Второй", role=Profile.Role.SUPPLIER, organization=other_org)
        second = Bid.objects.create(tender=self.tender, supplier=other, price=85000, delivery_days=9)
        self.tender.deadline = timezone.now() - timedelta(minutes=1)
        self.tender.status = Tender.Status.REVIEW
        self.tender.save()
        self.client.login(username="customer", password="testpass123")
        self.client.post(reverse("select_winner", args=[self.tender.pk, first.pk]))
        response = self.client.post(reverse("select_winner", args=[self.tender.pk, second.pk]))
        self.assertRedirects(response, self.tender.get_absolute_url())
        self.assertEqual(Contract.objects.filter(tender=self.tender).count(), 1)
        first.refresh_from_db()
        self.assertEqual(first.status, Bid.Status.WINNER)

    def test_rejected_supplier_can_resubmit_application(self):
        application = self.supplier.profile.organization.supplier_applications.get(
            customer=self.customer.profile.organization
        )
        application.status = SupplierApplication.Status.REJECTED
        application.save()
        self.client.login(username="supplier", password="testpass123")
        response = self.client.post(reverse("resubmit_application"))
        self.assertRedirects(response, reverse("company_profile"))
        application.refresh_from_db()
        self.assertEqual(application.status, SupplierApplication.Status.PENDING)

    def test_executable_document_is_rejected(self):
        form = TenderDocumentForm(
            data={"title": "Опасный файл", "visibility": TenderDocument.Visibility.PUBLIC},
            files={"file": SimpleUploadedFile("payload.exe", b"binary")},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Недопустимый формат", form.errors["file"][0])

    def test_health_endpoint_checks_database(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


    def test_reviewer_cannot_create_tender(self):
        reviewer = User.objects.create_user("reviewer", password="testpass123")
        Profile.objects.create(
            user=reviewer,
            company_name="Заказчик",
            role=Profile.Role.CUSTOMER,
            organization=self.customer.profile.organization,
        )
        Membership.objects.create(
            user=reviewer,
            organization=self.customer.profile.organization,
            role=Membership.Role.REVIEWER,
        )
        self.client.login(username="reviewer", password="testpass123")
        response = self.client.get(reverse("tender_create"))
        self.assertEqual(response.status_code, 403)

    def test_owner_can_invite_employee(self):
        self.client.login(username="customer", password="testpass123")
        response = self.client.post(reverse("invite_employee"), {
            "username": "wb-manager",
            "email": "manager@wildberries.ru",
            "first_name": "Иван",
            "last_name": "Менеджер",
            "role": Membership.Role.MANAGER,
        })
        self.assertRedirects(response, reverse("employee_registry"))
        user = User.objects.get(username="wb-manager")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(Membership.objects.filter(user=user, role=Membership.Role.MANAGER).exists())

    def test_manager_submits_tender_for_approval(self):
        manager = User.objects.create_user("approval-manager", password="testpass123")
        Profile.objects.create(
            user=manager,
            company_name="Заказчик",
            role=Profile.Role.CUSTOMER,
            organization=self.customer.profile.organization,
        )
        Membership.objects.create(
            user=manager,
            organization=self.customer.profile.organization,
            role=Membership.Role.MANAGER,
        )
        self.client.login(username="approval-manager", password="testpass123")
        response = self.client.post(reverse("tender_create"), {
            "title": "Новая закупка",
            "number": "T-APPROVAL",
            "category": Tender.Category.IT,
            "description": "Описание",
            "requirements": "",
            "delivery_address": "Москва",
            "budget": 100000,
            "deadline": (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
            "procedure": Tender.Procedure.CLOSED,
            "publish_results": "on",
            "publish": "1",
        })
        tender = Tender.objects.get(number="T-APPROVAL")
        self.assertRedirects(response, tender.get_absolute_url())
        self.assertEqual(tender.status, Tender.Status.APPROVAL)
        self.assertTrue(TenderApproval.objects.filter(tender=tender, requested_by=manager).exists())

    def test_reviewer_can_approve_tender(self):
        reviewer = User.objects.create_user("approval-reviewer", password="testpass123")
        Profile.objects.create(
            user=reviewer,
            company_name="Заказчик",
            role=Profile.Role.CUSTOMER,
            organization=self.customer.profile.organization,
        )
        Membership.objects.create(
            user=reviewer,
            organization=self.customer.profile.organization,
            role=Membership.Role.REVIEWER,
        )
        self.tender.status = Tender.Status.APPROVAL
        self.tender.save()
        approval = TenderApproval.objects.create(tender=self.tender, requested_by=self.customer)
        self.client.login(username="approval-reviewer", password="testpass123")
        response = self.client.post(reverse("review_tender", args=[approval.pk, "approve"]), {"comment": "Согласовано"})
        self.assertRedirects(response, self.tender.get_absolute_url())
        self.tender.refresh_from_db()
        approval.refresh_from_db()
        self.assertEqual(self.tender.status, Tender.Status.PUBLISHED)
        self.assertEqual(approval.decision, TenderApproval.Decision.APPROVED)

    def test_supplier_cannot_view_tender_on_approval(self):
        self.tender.status = Tender.Status.APPROVAL
        self.tender.save()
        self.client.login(username="supplier", password="testpass123")
        response = self.client.get(self.tender.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_customer_can_export_tender_registry(self):
        self.client.login(username="customer", password="testpass123")
        response = self.client.get(reverse("tender_export"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(self.tender.number.encode(), response.content)

    def test_customer_can_update_contract_status(self):
        bid = Bid.objects.create(tender=self.tender, supplier=self.supplier, price=90000, delivery_days=10)
        contract = Contract.objects.create(
            number="WB-CONTRACT-1",
            tender=self.tender,
            winning_bid=bid,
            customer=self.customer.profile.organization,
            supplier=self.supplier.profile.organization,
            amount=bid.price,
        )
        self.client.login(username="customer", password="testpass123")
        response = self.client.post(reverse("update_contract_status", args=[contract.pk, Contract.Status.SIGNED]))
        self.assertRedirects(response, reverse("contract_registry"))
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.SIGNED)
        self.assertIsNotNone(contract.signed_at)

    def test_supplier_submits_prices_for_all_lots(self):
        lot_one = TenderLot.objects.create(tender=self.tender, title="Лот 1", budget=60000)
        lot_two = TenderLot.objects.create(tender=self.tender, title="Лот 2", budget=40000)
        self.client.login(username="supplier", password="testpass123")
        response = self.client.post(reverse("bid_submit", args=[self.tender.pk]), {
            "price": "",
            "delivery_days": "",
            "warranty_months": 12,
            "comment": "Полная заявка",
            "lots-TOTAL_FORMS": "2",
            "lots-INITIAL_FORMS": "0",
            "lots-MIN_NUM_FORMS": "0",
            "lots-MAX_NUM_FORMS": "1000",
            "lots-0-lot": str(lot_one.pk),
            "lots-0-price": "55000",
            "lots-0-delivery_days": "10",
            "lots-0-comment": "",
            "lots-1-lot": str(lot_two.pk),
            "lots-1-price": "35000",
            "lots-1-delivery_days": "15",
            "lots-1-comment": "",
        })
        self.assertRedirects(response, self.tender.get_absolute_url())
        bid = Bid.objects.get(tender=self.tender, supplier=self.supplier)
        self.assertEqual(bid.price, 90000)
        self.assertEqual(bid.delivery_days, 15)
        self.assertEqual(bid.lot_offers.count(), 2)

    def test_contract_status_cannot_skip_from_preparation_to_completed(self):
        bid = Bid.objects.create(tender=self.tender, supplier=self.supplier, price=90000, delivery_days=10)
        contract = Contract.objects.create(
            number="WB-CONTRACT-INVALID",
            tender=self.tender,
            winning_bid=bid,
            customer=self.customer.profile.organization,
            supplier=self.supplier.profile.organization,
            amount=bid.price,
        )
        self.client.login(username="customer", password="testpass123")
        response = self.client.post(reverse("update_contract_status", args=[contract.pk, Contract.Status.COMPLETED]))
        self.assertRedirects(response, reverse("contract_registry"))
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.PREPARATION)

    def test_login_is_rate_limited_after_failed_attempts(self):
        for _ in range(5):
            self.client.post(reverse("login"), {"username": "supplier", "password": "wrong"})
        response = self.client.post(reverse("login"), {"username": "supplier", "password": "wrong"})
        self.assertEqual(response.status_code, 429)

    def test_closed_bid_price_is_hidden_on_customer_dashboard(self):
        Bid.objects.create(tender=self.tender, supplier=self.supplier, price=70000, delivery_days=10)
        self.client.login(username="customer", password="testpass123")
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "70000")

    def test_customer_dashboard_filters_tenders(self):
        Tender.objects.create(
            owner=self.customer, organization=self.customer.profile.organization,
            title="ИТ услуги", number="IT-001", category=Tender.Category.IT,
            description="Описание", delivery_address="Москва", budget=50000,
            deadline=timezone.now() + timedelta(days=5), status=Tender.Status.DRAFT,
        )
        self.client.login(username="customer", password="testpass123")
        response = self.client.get(reverse("dashboard"), {"q": "ИТ", "status": Tender.Status.DRAFT})
        self.assertContains(response, "ИТ услуги")
        self.assertNotContains(response, "Поставка оборудования")
        self.assertEqual(response.context["page_obj"].paginator.count, 1)

    def test_customer_dashboard_paginates_tenders(self):
        for index in range(25):
            Tender.objects.create(
                owner=self.customer, organization=self.customer.profile.organization,
                title=f"Закупка {index}", number=f"P-{index}", category=Tender.Category.GOODS,
                description="Описание", delivery_address="Москва", budget=1000,
                deadline=timezone.now() + timedelta(days=5), status=Tender.Status.PUBLISHED,
            )
        self.client.login(username="customer", password="testpass123")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        self.assertEqual(len(response.context["tenders"]), 25)
        self.assertContains(response, "Далее")

    def test_supplier_dashboard_filters_and_paginates_bids(self):
        Bid.objects.create(
            tender=self.tender, supplier=self.supplier, price=90000, delivery_days=10
        )
        for index in range(20):
            tender = Tender.objects.create(
                owner=self.customer, organization=self.customer.profile.organization,
                title=f"Услуги {index}", number=f"S-{index}", category=Tender.Category.SERVICES,
                description="Описание", delivery_address="Москва", budget=50000,
                deadline=timezone.now() + timedelta(days=5), status=Tender.Status.PUBLISHED,
            )
            Bid.objects.create(tender=tender, supplier=self.supplier, price=40000, delivery_days=5)
        self.client.login(username="supplier", password="testpass123")
        response = self.client.get(reverse("dashboard"), {"q": "Услуги"})
        self.assertEqual(response.context["page_obj"].paginator.count, 20)
        self.assertEqual(len(response.context["bids"]), 20)
        self.assertNotContains(response, "Поставка оборудования")

    def test_tender_list_ignores_invalid_choice_filters(self):
        response = self.client.get(
            reverse("tender_list"),
            {"category": "invalid", "procedure": "invalid", "source": "invalid"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["category"], "")
        self.assertEqual(response.context["procedure"], "")
        self.assertEqual(response.context["source"], "")

    def test_unapproved_supplier_cannot_ask_question(self):
        application = self.supplier.profile.organization.supplier_applications.get(
            customer=self.customer.profile.organization
        )
        application.status = SupplierApplication.Status.PENDING
        application.save()
        self.client.login(username="supplier", password="testpass123")
        response = self.client.post(reverse("ask_question", args=[self.tender.pk]), {"text": "Вопрос"})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.tender.questions.count(), 0)

    def test_customer_operational_pages_smoke(self):
        self.client.login(username="customer", password="testpass123")
        for url_name in ("dashboard", "supplier_registry", "contract_registry", "employee_registry", "audit_registry", "tender_export"):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, url_name)

    def test_supplier_operational_pages_smoke(self):
        self.client.login(username="supplier", password="testpass123")
        for url_name in ("dashboard", "company_profile", "contract_registry", "notifications"):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, url_name)

    def test_customer_cannot_access_another_customers_supplier_accreditation(self):
        other_customer = User.objects.create_user("other-customer", password="testpass123")
        other_customer_org = Organization.objects.create(name="Другой заказчик", kind=Organization.Kind.CUSTOMER)
        Profile.objects.create(
            user=other_customer,
            company_name=other_customer_org.name,
            role=Profile.Role.CUSTOMER,
            organization=other_customer_org,
        )
        Membership.objects.create(
            user=other_customer,
            organization=other_customer_org,
            role=Membership.Role.OWNER,
        )
        application = self.supplier.profile.organization.supplier_applications.get(
            customer=self.customer.profile.organization
        )
        document = SupplierDocument.objects.create(
            organization=self.supplier.profile.organization,
            title="Устав",
            file=SimpleUploadedFile("charter.pdf", b"document"),
            uploaded_by=self.supplier,
        )

        self.client.login(username="other-customer", password="testpass123")
        registry_response = self.client.get(reverse("supplier_registry"))
        self.assertEqual(registry_response.context["applications"].paginator.count, 0)
        self.assertEqual(self.client.get(reverse("supplier_detail", args=[application.pk])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("supplier_document_download", args=[document.pk])).status_code,
            403,
        )

    def test_supplier_rejection_stores_customer_comment(self):
        application = self.supplier.profile.organization.supplier_applications.get(
            customer=self.customer.profile.organization
        )
        application.status = SupplierApplication.Status.PENDING
        application.save(update_fields=["status"])
        self.client.login(username="customer", password="testpass123")

        response = self.client.post(
            reverse("review_supplier", args=[application.pk, "reject"]),
            {"comment": "Не хватает лицензии"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        application.refresh_from_db()
        self.assertEqual(application.status, SupplierApplication.Status.REJECTED)
        self.assertEqual(application.comment, "Не хватает лицензии")

    def test_supplier_cannot_download_public_document_from_draft_tender(self):
        self.tender.status = Tender.Status.DRAFT
        self.tender.save(update_fields=["status"])
        document = TenderDocument.objects.create(
            tender=self.tender,
            title="Будущее техническое задание",
            file=SimpleUploadedFile("draft.pdf", b"secret"),
            visibility=TenderDocument.Visibility.PUBLIC,
            uploaded_by=self.customer,
        )
        self.client.login(username="supplier", password="testpass123")

        response = self.client.get(reverse("document_download", args=[document.pk]))

        self.assertEqual(response.status_code, 403)

    def test_duplicate_tender_number_in_same_organization_is_rejected(self):
        self.client.login(username="customer", password="testpass123")
        response = self.client.post(reverse("tender_create"), {
            "title": "Другая закупка",
            "number": self.tender.number,
            "category": Tender.Category.IT,
            "description": "Описание",
            "requirements": "",
            "delivery_address": "Москва",
            "budget": 100000,
            "deadline": (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
            "procedure": Tender.Procedure.CLOSED,
            "publish_results": "on",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Закупка с таким номером уже существует")
        self.assertEqual(Tender.objects.filter(number=self.tender.number).count(), 1)

    def test_non_owner_cannot_edit_organization_details(self):
        manager = User.objects.create_user("profile-manager", password="testpass123")
        Profile.objects.create(
            user=manager,
            company_name="Заказчик",
            role=Profile.Role.CUSTOMER,
            organization=self.customer.profile.organization,
        )
        Membership.objects.create(
            user=manager,
            organization=self.customer.profile.organization,
            role=Membership.Role.MANAGER,
        )
        self.client.login(username="profile-manager", password="testpass123")

        response = self.client.post(reverse("company_profile"), {"name": "Подмененное имя"})

        self.assertEqual(response.status_code, 403)
        self.customer.profile.organization.refresh_from_db()
        self.assertEqual(self.customer.profile.organization.name, "Заказчик")


class TenderImportTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("import-owner", password="testpass123")
        self.organization = Organization.objects.create(
            name="Импортируемый заказчик", kind=Organization.Kind.CUSTOMER
        )
        self.source = TenderImportSource.objects.create(
            name="Тестовый API",
            url="https://example.test/tenders",
            organization=self.organization,
            owner=self.owner,
        )
        self.item = {
            "id": "external-42",
            "number": "EXT-42",
            "title": "Поставка из внешнего API",
            "category": "goods",
            "description": "Начальное описание",
            "delivery_address": "Москва",
            "budget": "150000.50",
            "deadline": (timezone.now() + timedelta(days=3)).isoformat(),
            "procedure": "auction",
            "auction_step": "5000",
            "status": "active",
            "url": "https://example.test/tenders/42",
        }

    @patch("procurement.imports.fetch_source_items")
    def test_sync_creates_then_updates_without_duplicate(self, fetch_source_items):
        fetch_source_items.return_value = [self.item]
        first = sync_source(self.source)
        self.assertEqual(first["created"], 1)
        self.assertEqual(Tender.objects.filter(number="EXT-42").count(), 1)

        changed = {**self.item, "title": "Обновленное название", "status": "closed"}
        fetch_source_items.return_value = [changed]
        second = sync_source(self.source)

        self.assertEqual(second["updated"], 1)
        self.assertEqual(Tender.objects.filter(number="EXT-42").count(), 1)
        tender = Tender.objects.get(number="EXT-42")
        self.assertEqual(tender.title, "Обновленное название")
        self.assertEqual(tender.status, Tender.Status.COMPLETED)
        self.assertEqual(tender.import_record.external_id, "external-42")

    @patch("procurement.imports.fetch_source_items")
    def test_unchanged_payload_is_idempotent(self, fetch_source_items):
        fetch_source_items.return_value = [self.item]
        sync_source(self.source)
        result = sync_source(self.source)

        self.assertEqual(result["unchanged"], 1)
        self.assertEqual(ImportedTender.objects.count(), 1)

    @patch("procurement.imports.fetch_source_items")
    def test_missing_tender_is_cancelled_only_when_enabled(self, fetch_source_items):
        fetch_source_items.return_value = [self.item]
        sync_source(self.source)
        fetch_source_items.return_value = []

        result = sync_source(self.source)
        self.assertEqual(result["cancelled"], 0)
        self.assertEqual(Tender.objects.get(number="EXT-42").status, Tender.Status.PUBLISHED)

        self.source.cancel_missing = True
        self.source.save(update_fields=["cancel_missing"])
        fetch_source_items.return_value = [{
            "id": "other",
            "number": "OTHER",
            "title": "Другой",
            "budget": "1",
            "deadline": self.item["deadline"],
        }]
        result = sync_source(self.source)
        self.assertEqual(result["cancelled"], 1)
        self.assertEqual(Tender.objects.get(number="EXT-42").status, Tender.Status.CANCELLED)

    @patch("procurement.imports.fetch_source_items")
    def test_custom_field_mapping(self, fetch_source_items):
        self.source.field_mapping = {
            "external_id": "uid",
            "number": "code",
            "title": "name",
            "deadline": "dates.finish",
        }
        self.source.save(update_fields=["field_mapping"])
        fetch_source_items.return_value = [{
            "uid": "mapped-1",
            "code": "MAP-1",
            "name": "Тендер с нестандартными полями",
            "dates": {"finish": self.item["deadline"]},
            "budget": 500,
        }]

        result = sync_source(self.source)

        self.assertEqual(result["created"], 1)
        self.assertTrue(Tender.objects.filter(number="MAP-1").exists())

    @patch("procurement.imports.fetch_json")
    def test_bidzaar_adapter_paginates_and_maps_items(self, fetch_json):
        self.source.adapter = TenderImportSource.Adapter.BIDZAAR
        self.source.url = (
            "https://bidzaar.com/app/requests/public/buy"
            "?sorting.key=publishDate&sorting.direction=desc&logic=and"
            "&filters%5B0%5D.operator=in&filters%5B0%5D.field=companyId"
            "&filters%5B0%5D.value=%5Bcompany-id%5D&id=selected-id"
        )
        self.source.save(update_fields=["adapter", "url"])
        base_item = {
            "id": "bidzaar-1",
            "number": "341-001",
            "name": "Монтаж оборудования",
            "companyName": "ВАЙЛДБЕРРИЗ",
            "status": 1,
            "acceptanceEndDate": self.item["deadline"],
            "publishDate": self.item["deadline"],
            "deliveryAddresses": [{"comment": "Коледино"}],
        }
        fetch_json.side_effect = [
            {"items": [base_item], "totalCount": 2},
            {
                "items": [{**base_item, "id": "bidzaar-2", "number": "341-002", "status": 3}],
                "totalCount": 2,
            },
        ]

        items = fetch_bidzaar_items(self.source)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["delivery_address"], "Коледино")
        self.assertEqual(items[0]["status"], Tender.Status.PUBLISHED)
        self.assertEqual(items[1]["status"], Tender.Status.COMPLETED)
        self.assertEqual(items[0]["url"], "https://bidzaar.com/app/process/light/bidzaar-1")
        first_url = fetch_json.call_args_list[0].args[0]
        self.assertIn("procedureType", first_url)
        self.assertNotIn("selected-id", first_url)
        self.assertIn("paging.page=1", first_url)
        self.assertIn("paging.size=100", first_url)
