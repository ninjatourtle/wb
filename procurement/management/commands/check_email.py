from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Проверяет production-настройки SMTP и при необходимости отправляет тестовое письмо."

    def add_arguments(self, parser):
        parser.add_argument("--send-to", help="Адрес для отправки тестового письма")

    def handle(self, *args, **options):
        if not settings.EMAIL_NOTIFICATIONS_ENABLED:
            raise CommandError("EMAIL_NOTIFICATIONS_ENABLED=0")
        if settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
            raise CommandError("Для production требуется SMTP backend")
        if not all((settings.EMAIL_HOST, settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)):
            raise CommandError("Не заполнены EMAIL_HOST, EMAIL_HOST_USER или EMAIL_HOST_PASSWORD")

        connection = get_connection()
        connection.open()
        connection.close()
        self.stdout.write(self.style.SUCCESS("SMTP connection succeeded"))

        if recipient := options["send_to"]:
            send_mail(
                "Проверка почты WB Tender",
                "SMTP настроен и уведомления готовы к отправке.",
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f"Test email sent to {recipient}"))
