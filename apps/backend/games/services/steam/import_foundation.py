"""
Steam import foundation — SBGC-53.

Thin service that combines App ID validation, app-details fetching,
and candidate normalisation.  Does NOT persist Games, generate slugs,
select listing status, or create classifications.
"""

from __future__ import annotations

from games.services.steam.adapters import SteamAdapterError
from games.services.steam.adapters.app_details import SteamAppDetailsAdapter
from games.services.steam.dto import (
    LookupStatus,
    SteamAppId,
    SteamAppLookupResult,
    SteamGameImportCandidate,
)


class SteamImportFoundation:
    """Prepares import candidates from Steam data.  No persistence."""

    def __init__(self, adapter: SteamAppDetailsAdapter):
        self._adapter = adapter

    def prepare_candidate(self, app_id: str) -> SteamAppLookupResult:
        """Validate *app_id* and return a ``SteamAppLookupResult``.

        - Valid app details → ``LookupStatus.FOUND`` with candidate.
        - ``success=false`` → ``LookupStatus.UNAVAILABLE``.
        - Malformed payloads → adapter exceptions propagate unchanged.
        - Transport exceptions (timeout, connection, etc.) propagate unchanged.
        """
        # Validate App ID.
        try:
            sid = SteamAppId(app_id)
        except (TypeError, ValueError) as exc:
            raise SteamAdapterError(
                f"Invalid Steam App ID {app_id!r}: {exc}",
                code="STEAM_INVALID_APP_ID",
            ) from exc

        try:
            details = self._adapter.fetch(sid)
        except SteamAdapterError as exc:
            if getattr(exc, "code", None) == "STEAM_APP_UNAVAILABLE":
                return SteamAppLookupResult(
                    status=LookupStatus.UNAVAILABLE,
                    app_id=sid.value,
                )
            # Malformed payload, missing fields, etc. — propagate.
            raise

        candidate = SteamGameImportCandidate(
            app_id=details.app_id,
            name=details.name,
            content_type=details.content_type,
            short_description=details.short_description,
            header_image_url=details.header_image_url,
            website_url=details.website_url,
            is_free=details.is_free,
            developers=details.developers,
            publishers=details.publishers,
        )

        return SteamAppLookupResult(
            status=LookupStatus.FOUND,
            app_id=sid.value,
            candidate=candidate,
        )
