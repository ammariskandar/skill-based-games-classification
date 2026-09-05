"""
Django Admin registration for the Game model — SBGC-45 / SBGC-56 / SBGC-67 / SBGC-69.
"""

from classifications.models import ClassificationSnapshot
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch
from django.template.response import TemplateResponse
from security.throttling_admin import HardenedModelAdmin

from games.errors import ERROR_REGISTRY
from games.forms import GameForm
from games.models import (
    ErrorRegistryEntry,
    Game,
    ListingStatus,
    SourceType,
    SteamRefreshGameAttempt,
    SteamRefreshRun,
)
from games.services.imports.steam import (
    SteamGameRefreshStatus,
    SteamRefreshError,
)
from games.services.steam.adapters import SteamAdapterError
from games.services.steam.errors import SteamError


def _build_steam_refresh_service():
    """Composition root for the Admin refresh action.

    Lazy imports keep the transport wiring out of the module import
    surface.  Tests patch this function with a fake service — no network
    in automated tests.
    """
    from games.services.imports.factory import build_steam_refresh_service

    return build_steam_refresh_service()


def _apply_listing_status(
    modeladmin, request, queryset, target: str, verb: str
) -> None:
    """Transition selected Games to *target* listing status via full validation.

    Only changes the editorial ``listing_status``; it never touches source
    identity, content type, classifications, or other metadata.  Games already
    in the target state are skipped, and a Game that fails ``full_clean()`` is
    skipped without partial mutation.
    """
    updated = 0
    skipped = 0
    for game in queryset:
        if game.listing_status == target:
            skipped += 1
            continue
        try:
            game.listing_status = target
            game.full_clean()
            game.save()
        except ValidationError:
            skipped += 1
            continue
        modeladmin.log_change(request, game, f"Listing status set to {target}")
        updated += 1

    level = messages.SUCCESS if updated else messages.WARNING
    modeladmin.message_user(
        request,
        f"{updated} Games {verb}; {skipped} skipped.",
        level=level,
    )


@admin.register(Game)
class GameAdmin(HardenedModelAdmin):
    form = GameForm

    list_display = (
        "name",
        "source_type",
        "external_id",
        "content_type",
        "listing_status",
        "developer",
        "submission_count",
        "classification_status",
        "updated_at",
    )

    list_filter = (
        "source_type",
        "content_type",
        "listing_status",
    )

    search_fields = (
        "name",
        "slug",
        "external_id",
        "developer",
    )

    ordering = ("name", "id")

    EDITABLE_METADATA_FIELDS = (
        "release_date",
        "developer",
        "description",
        "manual_website_url",
    )

    MANUAL_IMAGE_FIELDS = (
        "manual_image_url",
        "manual_hero_url",
        "manual_capsule_url",
    )

    def get_fieldsets(self, request, obj=None):
        """Expose the per-field "Resume Steam sync" controls for Steam Games
        and the source-aware manual image fields (SBGC-188 / SBGC-190).

        Manual Games and new records see plain editable metadata with no
        Steam ownership controls.
        """
        is_steam = obj is not None and obj.is_steam
        editable = list(self.EDITABLE_METADATA_FIELDS)
        if is_steam:
            resume_for = {
                "release_date": "resume_release_date",
                "developer": "resume_developer",
                "description": "resume_description",
            }
            editable = []
            for field in self.EDITABLE_METADATA_FIELDS:
                editable.append(field)
                if field in resume_for:
                    editable.append(resume_for[field])

        image_fieldset_label = "Manual Image Overrides" if is_steam else "Images"

        identity_fields = ("name", "slug", "source_type", "external_id", "content_type")
        if is_steam:
            # Owner content-type override with its resume control (SBGC-96).
            identity_fields = identity_fields + ("resume_content_type",)

        return [
            (
                "Identity",
                {
                    "fields": identity_fields,
                },
            ),
            ("Publication", {"fields": ("listing_status",)}),
            ("Editable metadata", {"fields": tuple(editable)}),
            (image_fieldset_label, {"fields": self.MANUAL_IMAGE_FIELDS}),
            (
                "Steam metadata",
                {
                    "fields": (
                        "steam_image_url",
                        "library_hero_url",
                        "library_capsule_url",
                        "last_steam_refresh_at",
                    ),
                },
            ),
            (
                "System",
                {
                    "fields": ("display_identity", "created_at", "updated_at"),
                    "classes": ("collapse",),
                },
            ),
        ]

    prepopulated_fields = {
        "slug": ("name",),
    }

    def get_prepopulated_fields(self, request, obj=None):
        """Disable slug-from-name prepopulation for existing Steam Games.

        ``name`` is readonly on Steam Games, so Admin cannot build the
        prepopulate dependency on a field that is not in the form.
        """
        if obj is not None and obj.is_steam:
            return {}
        return self.prepopulated_fields

    readonly_fields = (
        "display_identity",
        "created_at",
        "updated_at",
        # Steam-owned metadata is source-managed — readonly for all
        # records.  Manual/editorial imagery stays on manual_image_url.
        "steam_image_url",
        "library_hero_url",
        "library_capsule_url",
        "last_steam_refresh_at",
    )

    def get_readonly_fields(self, request, obj=None):
        """Freeze source identity and source-owned metadata (SBGC-59/61/96).

        Existing records never expose ``source_type`` or ``external_id``.
        ``name`` stays readonly for Steam Games (Steam-owned), but
        ``content_type`` is now editable for both sources: editing it marks
        the record human-overridden (``content_type_overridden``), so Steam
        refresh preserves the manual decision (SBGC-96).  Local/editorial
        fields stay editable for both sources.

        Creation (``obj is None``) still permits choosing source and
        external ID so the real Steam import / manual create flows are not
        affected.
        """
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly.extend(("source_type", "external_id"))
            if obj.is_steam:
                readonly.append("name")
        return readonly

    def save_model(self, request, obj, form, change):
        """Apply per-field Steam override provenance on Steam Game saves.

        - "Resume Steam sync" is checked → override cleared (resume wins).
        - Otherwise, if the operator changed a field, that field becomes
          human-overridden (no manual override checkbox needed).
        - Fields the operator did not touch keep their existing ownership.

        Manual Games and new records are unaffected.
        """
        if obj.is_steam and change:
            changed = set(form.changed_data)
            cleaned = form.cleaned_data

            if cleaned.get("resume_description"):
                obj.description_overridden = False
            elif "description" in changed:
                obj.description_overridden = True

            if cleaned.get("resume_developer"):
                obj.developer_overridden = False
            elif "developer" in changed:
                obj.developer_overridden = True

            if cleaned.get("resume_release_date"):
                obj.release_date_overridden = False
            elif "release_date" in changed:
                obj.release_date_overridden = True

            if cleaned.get("resume_content_type"):
                obj.content_type_overridden = False
            elif "content_type" in changed:
                obj.content_type_overridden = True

        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Precompute the two derived changelist columns.

        ``_submission_count`` is a reverse-count of editorial submissions;
        ``_current_snapshot`` prefetches the single current classification
        snapshot (if any) so the changelist does not issue N+1 queries.
        """
        queryset = super().get_queryset(request)
        return queryset.annotate(
            _submission_count=Count("editorial_classification"),
        ).prefetch_related(
            Prefetch(
                "classification_snapshots",
                queryset=ClassificationSnapshot.objects.filter(is_current=True),
                to_attr="_current_snapshot",
            ),
        )

    @admin.display(description="Submissions", ordering="_submission_count")
    def submission_count(self, obj):
        return obj._submission_count

    @admin.display(description="Classification")
    def classification_status(self, obj):
        """Readonly current Final Classification status.

        This is a persisted read — it never triggers a statistical
        calculation.  Classification administration itself is owned by
        SBGC-68; this only surfaces the current published status.
        """
        snapshots = getattr(obj, "_current_snapshot", None) or []
        snapshot = snapshots[0] if snapshots else None
        if snapshot is None:
            return "—"
        if snapshot.status == "READY":
            label = snapshot.confidence_label or "Ready"
            return f"Ready · {label}"
        return snapshot.status

    actions = (
        "publish_selected",
        "hide_selected",
        "archive_selected",
        "refresh_from_steam",
    )

    @admin.action(description="Publish selected Games")
    def publish_selected(self, request, queryset):
        """Publish eligible selected Games (listing_status → published)."""
        _apply_listing_status(
            self, request, queryset, ListingStatus.PUBLISHED, "published"
        )

    @admin.action(description="Hide selected Games")
    def hide_selected(self, request, queryset):
        """Hide selected Games (listing_status → draft)."""
        _apply_listing_status(self, request, queryset, ListingStatus.DRAFT, "hidden")

    @admin.action(description="Archive selected Games")
    def archive_selected(self, request, queryset):
        """Archive selected Games (listing_status → archived)."""
        _apply_listing_status(
            self, request, queryset, ListingStatus.ARCHIVED, "archived"
        )

    def get_actions(self, request):
        """Keep only deliberate, source-safe actions for Games (SBGC-182).

        The default ``delete_selected`` bulk action is disabled so canonical
        Game deletion is a deliberate single-object operation with its
        confirmation and cascade summary.  Publish/hide/archive and
        ``refresh_from_steam`` remain.
        """
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="Refresh Steam metadata from Steam")
    def refresh_from_steam(self, request, queryset):
        """Manually refresh selected Steam Games (SBGC-56).

        Manual Games are skipped without any network call.  Known Steam
        errors are reported per game; unexpected exceptions propagate.
        """
        steam_games = list(queryset.filter(source_type=SourceType.STEAM))
        manual_count = queryset.filter(source_type=SourceType.MANUAL).count()

        if not steam_games:
            if manual_count:
                self.message_user(
                    request,
                    "No Steam games selected — manual games cannot refresh.",
                    level=messages.WARNING,
                )
            else:
                self.message_user(request, "No games selected.", level=messages.WARNING)
            return

        service = _build_steam_refresh_service()

        updated = unchanged = unavailable = 0
        errors: list[str] = []
        for game in steam_games:
            try:
                result = service.refresh(game)
            except SteamRefreshError as exc:
                errors.append(f"{game.display_identity}: {exc}")
                continue
            except SteamAdapterError as exc:
                errors.append(f"{game.display_identity}: {exc.message}")
                continue
            except SteamError as exc:
                errors.append(f"{game.display_identity}: {exc.message}")
                continue

            if result.status == SteamGameRefreshStatus.UPDATED:
                updated += 1
                self.log_change(request, game, "Steam metadata refreshed")
            elif result.status == SteamGameRefreshStatus.UNCHANGED:
                unchanged += 1
            else:
                unavailable += 1

        parts: list[str] = []
        if updated:
            parts.append(f"{updated} updated")
        if unchanged:
            parts.append(f"{unchanged} unchanged")
        if unavailable:
            parts.append(f"{unavailable} unavailable")
        if manual_count:
            parts.append(f"{manual_count} manual skipped")
        summary = ", ".join(parts) or "nothing to refresh"

        if errors:
            first = errors[0]
            extra = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            self.message_user(
                request,
                f"Steam refresh finished ({summary}); "
                f"{len(errors)} failed — {first}{extra}.",
                level=messages.ERROR,
            )
        else:
            self.message_user(
                request,
                f"Steam refresh finished ({summary}).",
                level=messages.SUCCESS,
            )


# ---------------------------------------------------------------------------
# Scheduled Steam-refresh audit — read-only inspection (SBGC-183)
# ---------------------------------------------------------------------------


@admin.register(SteamRefreshRun)
class SteamRefreshRunAdmin(admin.ModelAdmin):
    list_display = (
        "scheduled_at",
        "status",
        "selected_count",
        "successful_count",
        "failed_count",
        "finished_at",
        "alert_sent",
    )
    list_filter = ("status",)
    readonly_fields = [field.name for field in SteamRefreshRun._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SteamRefreshGameAttempt)
class SteamRefreshGameAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "run",
        "game",
        "attempt_number",
        "outcome",
        "error_code",
        "timestamp",
    )
    list_filter = ("outcome",)
    list_select_related = ("run", "game")
    readonly_fields = [field.name for field in SteamRefreshGameAttempt._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ErrorRegistryEntry)
class ErrorRegistryAdmin(admin.ModelAdmin):
    """Read-only catalog view over the canonical error-code registry (SBGC-100).

    The model is unmanaged (``managed = False``), so nothing is ever
    persisted or migrated; the view renders from ``games.errors.ERROR_REGISTRY``.
    """

    change_list_template = "admin/games/error_registry.html"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        # Read-only registry: any active staff member may view the catalog.
        user = request.user  # pyright: ignore[reportAttributeAccessIssue]
        return bool(user.is_active and user.is_staff)  # pyright: ignore[reportAttributeAccessIssue]

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
