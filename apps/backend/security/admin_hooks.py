"""Owner-exclusive account reactivation hook — SBGC-106.

Extends the standard ``UserAdmin`` so that a security-locked account can only
be reactivated by the configured system owner, and so user mutations are
subject to high-risk write pacing.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
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


class ProtectedGroupAdminMixin:
    """SBGC-186 — protect the rotation-critical Moderator group from rename/delete.

    Applied to the group admin (``classifications.admin.EditorialGroupAdmin``)
    so the group the rotation engine relies on can never be renamed or removed
    through the Django Admin.  Only the ``name`` change of the protected group
    is blocked; membership and other groups remain editable.
    """

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.name == settings.MODERATOR_GROUP_NAME:
            return False
        return super().has_delete_permission(request, obj)  # type: ignore[reportAttributeAccessIssue]

    def save_model(self, request, obj, form, change):
        if change and "name" in form.changed_data:
            original = Group.objects.get(pk=obj.pk)
            if original.name == settings.MODERATOR_GROUP_NAME:
                raise PermissionDenied(
                    "The protected 'Moderator' group cannot be renamed."
                )
        super().save_model(request, obj, form, change)  # type: ignore[reportAttributeAccessIssue]
