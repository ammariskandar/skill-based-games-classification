"""Django application configuration for the security perimeter — SBGC-106."""

from django.apps import AppConfig


class SecurityConfig(AppConfig):
    name = "security"
    verbose_name = "Security"

    def ready(self) -> None:
        # Wire the reCAPTCHA-hardened admin authentication form onto the
        # default AdminSite.  ``django.contrib.admin`` is earlier in
        # INSTALLED_APPS, so ``admin.site`` already exists here.
        from django.contrib import admin

        from security.forms import HardenedAdminAuthenticationForm

        admin.site.login_form = HardenedAdminAuthenticationForm
