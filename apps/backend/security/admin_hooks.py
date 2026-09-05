"""Owner-exclusive account reactivation hook — SBGC-106.

Extends the standard ``UserAdmin`` so that a security-locked account can only
be reactivated by the configured system owner, and so user mutations are
subject to high-risk write pacing.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied

from security.models_cache import (
    clear_user_security_locked,
    is_user_security_locked,
)
from security.throttling_admin import HardenedModelAdminMixin


class HardenedUserAdmin(HardenedModelAdminMixin, UserAdmin):
    """UserAdmin with security-lockout guards and high-risk write pacing."""

    is_high_risk = True

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and is_user_security_locked(obj.pk):
            owner = getattr(settings, "DJANGO_OWNER_USERNAME", "")
            if getattr(request.user, "username", "") != owner:
                readonly.append("is_active")
        return readonly

    def save_model(self, request, obj, form, change):
        if change and "is_active" in form.changed_data and obj.is_active:
            owner = getattr(settings, "DJANGO_OWNER_USERNAME", "")
            if is_user_security_locked(obj.pk):
                if getattr(request.user, "username", "") != owner:
                    raise PermissionDenied(
                        "Only the system OWNER can reactivate a "
                        "security-locked account."
                    )
                clear_user_security_locked(obj.pk)
        super().save_model(request, obj, form, change)
