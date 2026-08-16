"""
Game deletion service — SBGC-182.

Canonical application entry point for hard-deleting a canonical ``Game``.
Deletion is local application lifecycle behavior only:

- never contacts Steam or any external service;
- never attempts to delete anything upstream;
- delegates the actual relational cascade to Django's collector.

Archive/hide (``listing_status == archived``) is a reversible editorial
state and is deliberately separate from deletion.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from games.models import Game


class GameDeletionError(Exception):
    """Domain error for an invalid Game deletion attempt."""


@dataclass(frozen=True)
class GameDeletionResult:
    """The identity of a successfully deleted Game."""

    game_id: int
    source_type: str
    slug: str


def delete_game(game: Game) -> GameDeletionResult:
    """Hard-delete *game* and return its pre-deletion identity.

    Raises:
        GameDeletionError: The game is unsaved or otherwise ineligible.
    """
    if not isinstance(game, Game):
        raise TypeError(f"game must be a Game instance, got {type(game).__name__}.")
    if game.pk is None:
        raise GameDeletionError("game must be saved before deletion.")

    result = GameDeletionResult(
        game_id=game.pk,
        source_type=game.source_type,
        slug=game.slug,
    )

    with transaction.atomic():
        # Django's collector cascades EditorialClassification ->
        # ChallengeProfile / RewardProfile.  User records are PROTECT and
        # are never deleted as part of this cascade.
        game.delete()

    return result


__all__ = ["GameDeletionError", "GameDeletionResult", "delete_game"]
