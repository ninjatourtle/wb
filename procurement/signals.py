from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import LoginEvent


def _client_ip(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def _user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""


@receiver(user_logged_in)
def record_successful_login(sender, request, user, **kwargs):
    LoginEvent.objects.create(
        user=user,
        username=user.get_username(),
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        success=True,
    )


@receiver(user_login_failed)
def record_failed_login(sender, credentials, request, **kwargs):
    username = str(credentials.get("username") or credentials.get("email") or "")[:150]
    LoginEvent.objects.create(
        username=username,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        success=False,
    )
