from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from pathlib import Path

from .models import (
    Bid, BidLot, Membership, Organization, Profile, Question, SupplierApplication, SupplierDocument,
    Tender, TenderApproval, TenderDocument, TenderLot, TenderTemplate,
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
    organization = forms.ModelChoiceField(
        label="Юридическое лицо-заказчик",
        queryset=Organization.objects.none(),
    )
    deadline = forms.DateTimeField(
        label="Окончание приема заявок",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        organization_ids = []
        if user:
            organization_ids = user.memberships.filter(
                is_active=True,
                role__in=[Membership.Role.OWNER, Membership.Role.MANAGER],
                organization__kind=Organization.Kind.CUSTOMER,
            ).values_list("organization_id", flat=True)
        self.fields["organization"].queryset = Organization.objects.filter(pk__in=organization_ids)
        if self.instance.pk:
            self.fields["organization"].initial = self.instance.organization
        elif user and getattr(getattr(user, "profile", None), "organization_id", None):
            primary = self.fields["organization"].queryset.filter(
                pk=user.profile.organization_id
            ).first()
            if primary:
                self.fields["organization"].initial = primary
        if not self.instance.pk and self.fields["organization"].queryset.count() == 1:
            only_organization = self.fields["organization"].queryset.first()
            if not self.fields["organization"].initial:
                self.fields["organization"].initial = only_organization
            if self.is_bound and not self.data.get("organization"):
                self.data = self.data.copy()
                self.data["organization"] = str(only_organization.pk)

    class Meta:
        model = Tender
        fields = (
            "organization",
            "title",
            "category",
            "description",
            "requirements",
            "delivery_address",
            "budget",
            "deadline",
            "procedure",
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

class TenderTemplateForm(forms.ModelForm):
    class Meta:
        model = TenderTemplate
        fields = ("name",)


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
    organization = forms.ModelChoiceField(
        label="Юридическое лицо", queryset=Organization.objects.none()
    )
    username = forms.CharField(label="Логин нового сотрудника", max_length=150, required=False)
    email = forms.EmailField(label="Email")
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    role = forms.ChoiceField(label="Роль", choices=Membership.Role.choices)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["organization"].queryset = Organization.objects.filter(
                memberships__user=user,
                memberships__is_active=True,
                memberships__role=Membership.Role.OWNER,
                kind=Organization.Kind.CUSTOMER,
            ).distinct()
            if self.fields["organization"].queryset.count() == 1:
                only_organization = self.fields["organization"].queryset.first()
                self.fields["organization"].initial = only_organization
                if self.is_bound and not self.data.get("organization"):
                    self.data = self.data.copy()
                    self.data["organization"] = str(only_organization.pk)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError("Этот логин уже занят.")
        return username

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        username = cleaned.get("username")
        if email and not User.objects.filter(email__iexact=email).exists() and not username:
            self.add_error("username", "Укажите логин для нового сотрудника.")
        return cleaned


class TenderApprovalForm(forms.ModelForm):
    class Meta:
        model = TenderApproval
        fields = ("comment",)
        widgets = {"comment": forms.Textarea(attrs={"rows": 3})}
