from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from .views import RateLimitedLoginView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", RateLimitedLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("accounts/password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("", include("procurement.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "procurement.views.error_403"
handler404 = "procurement.views.error_404"
handler500 = "procurement.views.error_500"
