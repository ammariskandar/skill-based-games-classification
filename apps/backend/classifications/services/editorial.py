"""
Editorial classification service — SBGC-46 / SBGC-63.

Backward-compatible wrapper around the canonical submission service.  The
canonical API is now ``create_submission`` / ``update_submission`` in
``classifications.services.submissions``.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from games.models import Game

from classifications.models import EditorialClassification
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
    update_submission,
)


def set_editorial_classification(
    *,
    game: Game,
    updated_by: AbstractBaseUser,
    challenge: ScoreDistribution,
    reward: ScoreDistribution,
    notes: str = "",
) -> EditorialClassification:
    """Create or update the ``updated_by`` user's submission for *game*.

    ``submitted_by`` defaults to ``updated_by`` for backward compatibility.
    Prefer ``create_submission`` / ``update_submission`` for new callers that
    need distinct submitter and operator attribution.
    """
    existing = None
    if not isinstance(game, Game) or game.pk is None:
        raise TypeError("game must be a saved Game instance.")
    if updated_by is None or updated_by.pk is None:
        raise TypeError("updated_by must be a saved user.")

    existing = EditorialClassification.objects.filter(
        game=game, submitted_by=updated_by
    ).first()

    if existing is None:
        return create_submission(
            game=game,
            submitted_by=updated_by,
            updated_by=updated_by,
            challenge=challenge,
            reward=reward,
            notes=notes,
        )

    return update_submission(
        existing,
        updated_by=updated_by,
        challenge=challenge,
        reward=reward,
        notes=notes,
    )


__all__ = ["ScoreDistribution", "set_editorial_classification"]
