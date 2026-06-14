from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("procurement", "0013_tenderimportsource_adapter")]

    operations = [
        migrations.AddField(
            model_name="tenderlot",
            name="external_id",
            field=models.CharField(blank=True, max_length=200, verbose_name="ID во внешней системе"),
        ),
        migrations.AddConstraint(
            model_name="tenderlot",
            constraint=models.UniqueConstraint(
                condition=~models.Q(external_id=""),
                fields=("tender", "external_id"),
                name="unique_external_lot_per_tender",
            ),
        ),
    ]
