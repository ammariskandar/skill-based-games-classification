"""
Steam refresh-service composition root — SBGC-183.

Single place that wires the Steam transport, import foundation, and
persistence service into a ``SteamGameRefreshService``.  Both the Game Admin
refresh action and the scheduled refresh command use this factory, so there is
one canonical composition and no duplicated wiring.
"""

from __future__ import annotations

from games.services.imports.steam import (
    SteamGamePersistenceService,
    SteamGameRefreshService,
)


def build_steam_refresh_service() -> SteamGameRefreshService:
    """Compose the canonical Steam refresh service from configured settings."""
    from config.steam import steam_client_config_from_settings

    from games.services.steam.adapters.app_details import SteamAppDetailsAdapter
    from games.services.steam.client import SteamClient
    from games.services.steam.import_foundation import SteamImportFoundation

    client = SteamClient(steam_client_config_from_settings())
    foundation = SteamImportFoundation(SteamAppDetailsAdapter(client))
    return SteamGameRefreshService(foundation, SteamGamePersistenceService())


__all__ = ["build_steam_refresh_service"]
