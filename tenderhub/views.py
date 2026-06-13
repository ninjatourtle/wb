from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import HttpResponse


class RateLimitedLoginView(LoginView):
    max_attempts = 5
    lock_seconds = 15 * 60

    def _cache_key(self):
        ip = self.request.headers.get("X-Real-IP") or self.request.META.get("REMOTE_ADDR", "unknown")
        username = self.request.POST.get("username", "").strip().lower()
        return f"login-attempts:{ip}:{username}"

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and cache.get(self._cache_key(), 0) >= self.max_attempts:
            return HttpResponse("Слишком много попыток входа. Повторите через 15 минут.", status=429)
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self._cache_key()
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, self.lock_seconds)
        cache.touch(key, self.lock_seconds)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._cache_key())
        messages.success(self.request, "Вход выполнен.")
        return super().form_valid(form)
