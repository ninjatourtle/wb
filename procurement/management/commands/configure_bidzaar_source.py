from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from procurement.models import Organization, TenderImportSource


DEFAULT_URL = (
    "https://bidzaar.com/app/requests/public/buy"
    "?sorting.key=publishDate&sorting.direction=desc&logic=and"
    "&filters%5B0%5D.operator=in&filters%5B0%5D.field=companyId"
    "&filters%5B0%5D.value=%5Bd49cfd05-5cfc-4144-be60-82d64bbfbf4a%5D"
)


class Command(BaseCommand):
    help = "Создает или обновляет источник закупок Wildberries на Bidzaar"

    def add_arguments(self, parser):
        parser.add_argument("--owner", default="customer")
        parser.add_argument("--organization-inn", default="7701234567")
        parser.add_argument("--url", default=DEFAULT_URL)

    def handle(self, *args, **options):
        try:
            owner = User.objects.get(username=options["owner"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Пользователь {options['owner']} не найден") from exc
        try:
            organization = Organization.objects.get(inn=options["organization_inn"])
        except Organization.DoesNotExist as exc:
            raise CommandError(f"Организация с ИНН {options['organization_inn']} не найдена") from exc

        source, created = TenderImportSource.objects.update_or_create(
            name="Wildberries на Bidzaar",
            defaults={
                "url": options["url"],
                "adapter": TenderImportSource.Adapter.BIDZAAR,
                "organization": organization,
                "owner": owner,
                "is_active": True,
                "cancel_missing": False,
            },
        )
        action = "создан" if created else "обновлен"
        self.stdout.write(self.style.SUCCESS(f"Источник {action}: {source}"))
