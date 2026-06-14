import json

from django.core.management.base import BaseCommand

from procurement.imports import sync_active_sources


class Command(BaseCommand):
    help = "Синхронизирует тендеры из активных внешних источников"

    def handle(self, *args, **options):
        result = sync_active_sources()
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
