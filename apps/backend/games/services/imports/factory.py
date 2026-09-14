"""
Steam service composition roots — SBGC-183 / SBGC-126.

Single places that wire the Steam transport, import foundation, and persistence
service.  The Game Admin refresh action and the scheduled refresh command share
``build_steam_refresh_service``; the initial catalogue import command uses
``build_steam_import_service``.  One canonical composition each, no duplicated
wiring.
"""

from __future__ import annotations

from games.services.imports.steam import (
    SteamGameImportService,
    SteamGamePersistenceService,
    SteamGameRefreshService,
)


def _build_foundation():
    """Compose the network-side import foundation from configured settings."""
    from config.steam import steam_client_config_from_settings

    from games.services.steam.adapters.app_details import SteamAppDetailsAdapter
    from games.services.steam.client import SteamClient
    from games.services.steam.import_foundation import SteamImportFoundation

    client = SteamClient(steam_client_config_from_settings())
    return SteamImportFoundation(SteamAppDetailsAdapter(client))


def build_steam_refresh_service() -> SteamGameRefreshService:
    """Compose the canonical Steam refresh service from configured settings."""
    return SteamGameRefreshService(_build_foundation(), SteamGamePersistenceService())


def build_steam_import_service() -> SteamGameImportService:
    """Compose the canonical Steam import service from configured settings."""
    return SteamGameImportService(_build_foundation(), SteamGamePersistenceService())


__all__ = ["build_steam_import_service", "build_steam_refresh_service"]
