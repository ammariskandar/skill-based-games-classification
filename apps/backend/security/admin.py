"""
Django Admin registrations for the Security app.

* Read-only registry catalogs (SBGC-108) — unmanaged virtual models.
* User-report moderation desk + scheduled deletions (SBGC-223).
"""

from classifications.roles import EditorialRole
from classifications.services.submissions import (
    EditorialRoleError,
    resolve_editorial_role,
)
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from games.errors import ERROR_REGISTRY

from security.models import (
    DependencyRegistryEntry,
    ErrorRegistryEntry,
    ScheduledAccountDeletion,
    UserReport,
)
from security.services.reporting import (
    ReportValidationError,
    dismiss_report,
    enforce_bio_change,
    enforce_username_change,
    schedule_permanent_ban,
)
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


# ---------------------------------------------------------------------------
# User-report moderation desk — SBGC-223
# ---------------------------------------------------------------------------


class ModerationAccessMixin:
    """Gate the moderation desk to Superusers, Moderators, and Community Leaders.

    Access follows the editorial-role resolver: any role other than COMMUNITY
    (superuser, moderator, community leader) passes; a conflicted role resolves
    to no access rather than erroring.
    """

    def _has_moderation_access(self, request) -> bool:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or not user.is_staff:
            return False
        if getattr(user, "is_superuser", False):
            return True
        try:
            return resolve_editorial_role(user) != EditorialRole.COMMUNITY
        except EditorialRoleError:
            return False

    def has_module_permission(self, request):
        return self._has_moderation_access(request)

    def has_view_permission(self, request, obj=None):
        return self._has_moderation_access(request)

    def has_change_permission(self, request, obj=None):
        return self._has_moderation_access(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


_REASON_BADGE_STYLE = (
    "display:inline-block;padding:0 .4rem;margin:0 .15rem .15rem 0;"
    "border:1px solid #8b949e55;border-radius:9999px;font-size:.6875rem;"
    "background:#8b949e22;color:#e6edf3;white-space:nowrap;"
)


@admin.register(UserReport)
class UserReportAdmin(ModerationAccessMixin, admin.ModelAdmin):
    """Read-only triage desk with dismiss + take-action workflows."""

    class Media:
        css = {"all": ("security/admin.css",)}

    list_display = (
        "offending_link",
        "repeat_offender_badge",
        "reporting_user",
        "reasons_display",
        "brigading_badge",
        "other_preview",
        "status",
        "created_at",
        "take_action_link",
    )
    list_filter = ("status", "possible_brigading", "created_at")
    search_fields = (
        "offending_user__username",
        "reporting_user__username",
        "other_description",
    )
    list_select_related = ("offending_user", "reporting_user", "actioned_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = [field.name for field in UserReport._meta.fields]
    actions = ("dismiss_selected",)

    @admin.display(description="Action")
    def take_action_link(self, obj):
        url = reverse("admin:security_userreport_take_action", args=[obj.pk])
        return format_html('<a class="button" href="{}">Take action</a>', url)

    @admin.display(description="Offending user")
    def offending_link(self, obj):
        base = settings.PUBLIC_SITE_URL.rstrip("/")
        url = f"{base}/profile/{obj.offending_user.username}"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" '
            'style="font-weight:700">{}</a>',
            url,
            obj.offending_user.username,
        )

    @admin.display(description="Repeat offender")
    def repeat_offender_badge(self, obj):
        if obj.repeat_offender_at_submission:
            return format_html('<strong style="color:#f85149">{}</strong>', "YES")
        return format_html('<span style="color:#8b949e">{}</span>', "NO")

    @admin.display(description="Reason(s)")
    def reasons_display(self, obj):
        labels = obj.reasons()
        if not labels:
            return "—"
        # `format_html_join` keeps every badge a SafeString; a plain
        # `"".join(...)` over SafeStrings would drop the safe marking and get
        # the markup escaped on render.
        return format_html_join(
            "",
            '<span style="{}">{}</span>',
            ((_REASON_BADGE_STYLE, label) for label in labels),
        )

    @admin.display(description="Brigading")
    def brigading_badge(self, obj):
        if not obj.possible_brigading:
            return "—"
        return format_html(
            '<span style="display:inline-block;padding:.15rem .5rem;'
            "border-radius:9999px;background:#d2991d;color:#0d1117;"
            'font-weight:700;animation:moderation-pulse 1.4s ease-in-out infinite">'
            "{}</span>",
            "\u26a0 BRIGADING SUSPECTED",
        )

    @admin.display(description="Other details")
    def other_preview(self, obj):
        if not obj.other_description:
            return "—"
        preview = obj.other_description[:50]
        suffix = "…" if len(obj.other_description) > 50 else ""
        return f"{preview}{suffix}"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:report_id>/take-action/",
                self.admin_site.admin_view(self.take_action_view),
                name="security_userreport_take_action",
            )
        ]
        return custom + urls

    @admin.action(description="Dismiss selected reports")
    def dismiss_selected(self, request, queryset):
        count = 0
        for report in queryset:
            dismiss_report(report, actor=request.user)
            count += 1
        self.message_user(request, f"{count} report(s) dismissed.")

    def take_action_view(self, request, report_id):
        if not self._has_moderation_access(request):
            raise PermissionDenied
        report = get_object_or_404(UserReport, pk=report_id)

        if request.method == "POST":
            intervention = request.POST.get("intervention", "")
            action_reason = request.POST.get("action_reason", "")
            ban_reason = request.POST.get("ban_reason", "")
            confirm_phrase = request.POST.get("confirm_phrase", "")
            try:
                if intervention == "dismiss":
                    dismiss_report(report, actor=request.user)
                elif intervention == "username":
                    enforce_username_change(
                        report, actor=request.user, reason=action_reason
                    )
                elif intervention == "bio":
                    enforce_bio_change(report, actor=request.user, reason=action_reason)
                elif intervention == "permaban":
                    if confirm_phrase.strip() != "permaban":
                        raise ReportValidationError(
                            'Type "permaban" exactly to confirm the ban.'
                        )
                    schedule_permanent_ban(
                        report, actor=request.user, ban_reason=ban_reason
                    )
                else:
                    raise ReportValidationError("Choose an intervention.")
            except ReportValidationError as exc:
                messages.error(request, str(exc))
            else:
                self.message_user(request, "Moderation action recorded.")
                return redirect("admin:security_userreport_changelist")

        context = {
            **self.admin_site.each_context(request),
            "title": f"Take action on report #{report.pk}",
            "opts": self.opts,
            "report": report,
            "reasons": report.reasons(),
            "public_profile_url": (
                f"{settings.PUBLIC_SITE_URL.rstrip('/')}/profile/"
                f"{report.offending_user.username}"
            ),
        }
        return TemplateResponse(
            request,
            "admin/security/userreport_take_action.html",
            context,
        )


@admin.register(ScheduledAccountDeletion)
class ScheduledAccountDeletionAdmin(ModerationAccessMixin, admin.ModelAdmin):
    """Read-only audit of scheduled permanent-ban purges."""

    list_display = (
        "offending_username_snapshot",
        "scheduled_for",
        "executed",
        "authorized_by",
        "created_at",
    )
    list_filter = ("executed", "scheduled_for")
    search_fields = ("offending_username_snapshot", "ban_reason")
    readonly_fields = [field.name for field in ScheduledAccountDeletion._meta.fields]
    ordering = ("scheduled_for",)
