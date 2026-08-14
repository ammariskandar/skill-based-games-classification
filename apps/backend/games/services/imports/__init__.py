"""
Steam game import services — SBGC-54.

Persistence boundary between SBGC-53 import-foundation DTOs and the
canonical ``Game`` model.

Orchestration:

    Steam App ID
      → SteamImportFoundation.prepare_candidate()  (network, no transaction)
      → SteamGamePersistenceService.persist()      (transaction, no network)
      → canonical Game row
"""

from __future__ import annotations

from games.services.imports.steam import (
    SteamGameImportResult,
    SteamGameImportService,
    SteamGameImportStatus,
    SteamGamePersistenceService,
    SteamGameRefreshResult,
    SteamGameRefreshService,
    SteamGameRefreshStatus,
    SteamRefreshError,
    build_steam_game_slug,
)

__all__ = [
    "SteamGameImportResult",
    "SteamGameImportService",
    "SteamGameImportStatus",
    "SteamGamePersistenceService",
    "SteamGameRefreshResult",
    "SteamGameRefreshService",
    "SteamGameRefreshStatus",
    "SteamRefreshError",
    "build_steam_game_slug",
]
