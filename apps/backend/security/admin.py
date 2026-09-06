"""
Django Admin registrations for the read-only Security registry catalogs —
SBGC-108.

Both the error-code registry and the tech-stack registry are registered under
the ``security`` app so they appear together in a shared Admin sidebar
category, separate from the Games domain.  Each model is unmanaged
(``managed = False``); nothing here is ever persisted or migrated.
"""

from django.contrib import admin
from django.template.response import TemplateResponse
from games.errors import ERROR_REGISTRY

from security.models import DependencyRegistryEntry, ErrorRegistryEntry
from security.views import dependency_registry_view


def _is_active_staff(request) -> bool:
    user = request.user  # pyright: ignore[reportAttributeAccessIssue]
    return bool(user.is_active and user.is_staff)  # pyright: ignore[reportAttributeAccessIssue]


class ReadOnlyRegistryAdmin(admin.ModelAdmin):
    """Shared read-only behavior for the virtual registry catalogs."""

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        # The security app carries no real permission codenames; keep its
        # catalog entries visible to any active staff member in the sidebar.
        return _is_active_staff(request)

    def has_view_permission(self, request, obj=None):
        # Read-only registry: any active staff member may view the catalog.
        return _is_active_staff(request)


@admin.register(ErrorRegistryEntry)
class ErrorRegistryAdmin(ReadOnlyRegistryAdmin):
    """Read-only catalog view over the canonical error-code registry."""

    change_list_template = "admin/security/error_registry.html"

    def changelist_view(self, request, extra_context=None):
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

    Delegates to the staff-guarded ``dependency_registry_view``, which enforces
    the authorization contract (anonymous -> login redirect, non-staff -> 403,
    staff -> 200) and renders ``admin/security/dependency_registry.html``.
    """

    def changelist_view(self, request, extra_context=None):
        return dependency_registry_view(request)
