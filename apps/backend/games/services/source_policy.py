"""
Source-specific Game policy helpers — SBGC-61.

Small, pure capability checks shared by the manual service, Steam refresh
service, and Admin.  They contain no network I/O, no database queries, and
no authorization decisions — those remain at their respective boundaries.

The canonical source identity rules live on ``Game`` itself:

    manual  → source_type == manual, external_id is NULL
    steam   → source_type == steam, valid nonempty external_id
"""

from __future__ import annotations

from games.models import Game


def can_manual_edit(game: Game) -> bool:
    """Return ``True`` when *game* is eligible for the manual edit workflow.

    Steam Games are never edited through the manual service (SBGC-59).
    """
    return game.is_manual


def can_steam_refresh(game: Game) -> bool:
    """Return ``True`` when *game* is eligible for Steam metadata refresh.

    Manual Games are rejected before any Steam call (SBGC-56).
    """
    return game.is_steam


__all__ = ["can_manual_edit", "can_steam_refresh"]
