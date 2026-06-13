from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from pathlib import Path

from .models import (
    Bid, BidLot, Membership, Organization, Profile, Question, SupplierApplication, SupplierDocument,
    Tender, TenderApproval, TenderDocument, TenderLot,
)


ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".zip"}
MAX_DOCUMENT_SIZE = 25 * 1024 * 1024


def validate_document(file):
    if file.size > MAX_DOCUMENT_SIZE:
        raise forms.ValidationError("Размер файла не должен превышать 25 МБ.")
    if Path(file.name).suffix.lower() not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise forms.ValidationError("Недопустимый формат файла.")
    return file


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label="Email")
    company_name = forms.CharField(label="Название компании", max_length=200)
    inn = forms.CharField(label="ИНН", max_length=12, required=False)
    phone = forms.CharField(label="Телефон", max_length=32, required=False)
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "company_name", "inn", "phone")

    def clean_inn(self):
        inn = self.cleaned_data["inn"].strip()
        if inn and Organization.objects.filter(inn=inn).exists():
            raise forms.ValidationError("Компания с таким ИНН уже зарегистрирована.")
        return inn

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            organization = Organization.objects.create(
                name=self.cleaned_data["company_name"],
                inn=self.cleaned_data["inn"],
                phone=self.cleaned_data["phone"],
                contact_email=self.cleaned_data["email"],
                kind=Organization.Kind.SUPPLIER,
            )
            Profile.objects.create(
                user=user,
                company_name=self.cleaned_data["company_name"],
                inn=self.cleaned_data["inn"],
                phone=self.cleaned_data["phone"],
                role=Profile.Role.SUPPLIER,
                organization=organization,
            )
            from .models import Membership

            Membership.objects.create(organization=organization, user=user)
            customer = Organization.objects.filter(kind=Organization.Kind.CUSTOMER).order_by("pk").first()
            if customer:
                SupplierApplication.objects.create(organization=organization, customer=customer)
        return user


class TenderForm(forms.ModelForm):
    deadline = forms.DateTimeField(
        label="Окончание приема заявок",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization or getattr(self.instance, "organization", None)

    class Meta:
        model = Tender
        fields = (
            "title",
            "number",
            "category",
            "description",
            "requirements",
            "delivery_address",
            "budget",
            "deadline",
            "procedure",
            "auction_step",
            "publish_results",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "requirements": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_deadline(self):
        deadline = self.cleaned_data["deadline"]
        if deadline <= timezone.now():
            raise forms.ValidationError("Срок должен быть в будущем.")
        return deadline

    def clean_number(self):
        number = self.cleaned_data["number"].strip()
        if self.organization:
            existing = Tender.objects.filter(organization=self.organization, number=number)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("Закупка с таким номером уже существует.")
        return number

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("procedure") == Tender.Procedure.AUCTION and not cleaned.get("auction_step"):
            self.add_error("auction_step", "Укажите шаг для открытого аукциона.")
        return cleaned


class BidForm(forms.ModelForm):
    def __init__(self, *args, tender=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tender and tender.lots.exists():
            self.fields["price"].required = False
            self.fields["delivery_days"].required = False
            self.fields["price"].widget = forms.HiddenInput()
            self.fields["delivery_days"].widget = forms.HiddenInput()

    class Meta:
        model = Bid
        fields = ("price", "delivery_days", "warranty_months", "comment")
        widgets = {"comment": forms.Textarea(attrs={"rows": 4})}


def bid_lot_formset(extra=0):
    return inlineformset_factory(
        Bid,
        BidLot,
        fields=("lot", "price", "delivery_days", "comment"),
        extra=extra,
        can_delete=False,
    )


class TenderLotForm(forms.ModelForm):
    class Meta:
        model = TenderLot
        fields = ("title", "description", "quantity", "unit", "budget")


class TenderDocumentForm(forms.ModelForm):
    class Meta:
        model = TenderDocument
        fields = ("title", "file", "visibility")

    def clean_file(self):
        return validate_document(self.cleaned_data["file"])


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ("text",)
        widgets = {"text": forms.Textarea(attrs={"rows": 3})}


class AnswerForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ("answer",)
        widgets = {"answer": forms.Textarea(attrs={"rows": 3})}


class SupplierApplicationForm(forms.ModelForm):
    class Meta:
        model = SupplierApplication
        fields = ("comment",)
        widgets = {"comment": forms.Textarea(attrs={"rows": 4})}


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ("name", "inn", "kpp", "legal_address", "contact_email", "phone")


class SupplierDocumentForm(forms.ModelForm):
    class Meta:
        model = SupplierDocument
        fields = ("kind", "title", "file")

    def clean_file(self):
        return validate_document(self.cleaned_data["file"])


class EmployeeInviteForm(forms.Form):
    username = forms.CharField(label="Логин", max_length=150)
    email = forms.EmailField(label="Email")
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    role = forms.ChoiceField(label="Роль", choices=Membership.Role.choices)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Этот логин уже занят.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email


class TenderApprovalForm(forms.ModelForm):
    class Meta:
        model = TenderApproval
        fields = ("comment",)
        widgets = {"comment": forms.Textarea(attrs={"rows": 3})}
