"""
Django Admin registration for the Game model — SBGC-45 / SBGC-56.
"""

from django.contrib import admin, messages

from games.models import Game, SourceType
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
    from config.steam import steam_client_config_from_settings

    from games.services.imports.steam import (
        SteamGamePersistenceService,
        SteamGameRefreshService,
    )
    from games.services.steam.adapters.app_details import SteamAppDetailsAdapter
    from games.services.steam.client import SteamClient
    from games.services.steam.import_foundation import SteamImportFoundation

    client = SteamClient(steam_client_config_from_settings())
    foundation = SteamImportFoundation(SteamAppDetailsAdapter(client))
    return SteamGameRefreshService(foundation, SteamGamePersistenceService())


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "source_type",
        "external_id",
        "content_type",
        "listing_status",
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
    )

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
        "last_steam_refresh_at",
    )

    def get_readonly_fields(self, request, obj=None):
        """Freeze source identity and source-owned metadata (SBGC-59/61).

        Existing records never expose ``source_type`` or ``external_id``.
        Steam-owned metadata (``name``, ``content_type``) is also readonly
        for Steam Games — refresh owns those fields, so Admin editing would
        be overwritten on the next refresh.  Local/editorial fields stay
        editable for both sources.

        Creation (``obj is None``) still permits choosing source and
        external ID so the real Steam import / manual create flows are not
        affected.
        """
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly.extend(("source_type", "external_id"))
            if obj.is_steam:
                readonly.extend(("name", "content_type"))
        return readonly

    actions = ("refresh_from_steam",)

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
