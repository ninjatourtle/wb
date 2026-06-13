from django.db import migrations, models
import django.db.models.deletion


def assign_customer_to_applications(apps, schema_editor):
    Organization = apps.get_model("procurement", "Organization")
    SupplierApplication = apps.get_model("procurement", "SupplierApplication")
    customer = Organization.objects.filter(kind="customer").order_by("pk").first()
    if not customer and SupplierApplication.objects.exists():
        customer = Organization.objects.create(name="Основной заказчик", kind="customer")

    for application in SupplierApplication.objects.select_related("reviewed_by").all():
        reviewer_customer = None
        if application.reviewed_by_id:
            reviewer_customer = Organization.objects.filter(
                kind="customer",
                profiles__user_id=application.reviewed_by_id,
            ).first()
        application.customer = reviewer_customer or customer
        application.save(update_fields=["customer"])


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0009_alter_supplierapplication_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="supplierapplication",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="supplier_applications",
                to="procurement.organization",
            ),
        ),
        migrations.AddField(
            model_name="supplierapplication",
            name="customer",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="supplier_accreditations",
                to="procurement.organization",
            ),
        ),
        migrations.RunPython(assign_customer_to_applications, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="supplierapplication",
            name="customer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="supplier_accreditations",
                to="procurement.organization",
            ),
        ),
        migrations.AddConstraint(
            model_name="supplierapplication",
            constraint=models.UniqueConstraint(
                fields=("organization", "customer"),
                name="one_supplier_application_per_customer",
            ),
        ),
        migrations.AlterField(
            model_name="tender",
            name="number",
            field=models.CharField(max_length=40, verbose_name="Номер"),
        ),
        migrations.AddConstraint(
            model_name="tender",
            constraint=models.UniqueConstraint(
                fields=("organization", "number"),
                name="unique_tender_number_per_org",
            ),
        ),
    ]
