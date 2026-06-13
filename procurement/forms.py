from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Bid, Organization, Profile, Question, SupplierApplication, Tender, TenderDocument, TenderLot


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label="Email")
    company_name = forms.CharField(label="Название компании", max_length=200)
    inn = forms.CharField(label="ИНН", max_length=12, required=False)
    phone = forms.CharField(label="Телефон", max_length=32, required=False)
    role = forms.ChoiceField(label="Роль", choices=Profile.Role.choices)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "company_name", "inn", "phone", "role")

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
                kind=self.cleaned_data["role"],
            )
            Profile.objects.create(
                user=user,
                company_name=self.cleaned_data["company_name"],
                inn=self.cleaned_data["inn"],
                phone=self.cleaned_data["phone"],
                role=self.cleaned_data["role"],
                organization=organization,
            )
            from .models import Membership

            Membership.objects.create(organization=organization, user=user)
            if self.cleaned_data["role"] == Profile.Role.SUPPLIER:
                SupplierApplication.objects.create(organization=organization)
        return user


class TenderForm(forms.ModelForm):
    deadline = forms.DateTimeField(
        label="Окончание приема заявок",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )

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

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("procedure") == Tender.Procedure.AUCTION and not cleaned.get("auction_step"):
            self.add_error("auction_step", "Укажите шаг для открытого аукциона.")
        return cleaned


class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ("price", "delivery_days", "warranty_months", "comment")
        widgets = {"comment": forms.Textarea(attrs={"rows": 4})}


class TenderLotForm(forms.ModelForm):
    class Meta:
        model = TenderLot
        fields = ("title", "description", "quantity", "unit", "budget")


class TenderDocumentForm(forms.ModelForm):
    class Meta:
        model = TenderDocument
        fields = ("title", "file", "visibility")


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
