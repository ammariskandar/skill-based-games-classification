"""
Django Admin registrations for the read-only Security registry catalogs —
SBGC-108.

Both the error-code registry and the tech-stack registry are registered under
the ``security`` app so they appear together in a shared Admin sidebar
category, separate from the Games domain.  Each model is unmanaged
(``managed = False``); nothing here is ever persisted or migrated.
"""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from games.errors import ERROR_REGISTRY

from security.models import DependencyRegistryEntry, ErrorRegistryEntry
from security.views import dependency_registry_view


class ReadOnlyRegistryAdmin(admin.ModelAdmin):
    """Shared read-only behavior for the virtual registry catalogs.

    Access follows Django's standard permission model: superusers bypass, and
    staff/group members granted the model's ``view`` permission (e.g.
    ``security.view_errorregistryentry``) may read the catalog.  The registries
    are never editable or deletable, even by superusers.
    """

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def _require_view_permission(self, request) -> None:
        """Enforce the built-in changelist guard bypassed by our overrides.

        Django's stock ``changelist_view`` raises ``PermissionDenied`` unless the
        caller passes ``has_view_or_change_permission``; the custom changelist
        views below replace that method wholesale, so the guard is reinstated
        here.  Superusers bypass, permission-granted staff pass, everyone else
        is denied (403).
        """
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied(
                "You do not have the view permission for this Security registry."
            )


@admin.register(ErrorRegistryEntry)
class ErrorRegistryAdmin(ReadOnlyRegistryAdmin):
    """Read-only catalog view over the canonical error-code registry."""

    change_list_template = "admin/security/error_registry.html"

    def changelist_view(self, request, extra_context=None):
        self._require_view_permission(request)
        context = {
            **self.admin_site.each_context(request),
            "title": "System Error Code Registry",
            "opts": self.opts,
            "error_entries": sorted(
                ERROR_REGISTRY.values(), key=lambda entry: entry.code.value
            ),
        }
        template = self.change_list_template or "admin/change_list.html"
        return TemplateResponse(request, template, context)


@admin.register(DependencyRegistryEntry)
class DependencyRegistryAdmin(ReadOnlyRegistryAdmin):
    """Admin sidebar entry rendering the tech-stack dependency catalog.

    Delegates to the authorization-enforcing ``dependency_registry_view``,
    which mirrors the standard Admin permission model (superuser bypass, or a
    grant of ``security.view_dependencyregistryentry``) and renders
    ``admin/security/dependency_registry.html``.
    """

    def changelist_view(self, request, extra_context=None):
        self._require_view_permission(request)
        return dependency_registry_view(request)
