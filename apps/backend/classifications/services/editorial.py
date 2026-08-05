"""
Editorial classification service — SBGC-46.

Single entry point for creating or updating a complete editorial
classification (parent + Challenge + Reward) in one atomic operation.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from games.models import Game

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
)
from classifications.validation import validate_score_distribution


@dataclass(frozen=True)
class ScoreDistribution:
    """Immutable three-score distribution for one profile."""

    micro: int
    mystiko: int
    macro: int

    def __post_init__(self) -> None:
        # Basic type/range checks at construction — the full profile-context
        # validation runs in the service with a profile label.
        for name in ("micro", "mystiko", "macro"):
            v = getattr(self, name)
            if isinstance(v, bool):
                raise TypeError(f"{name} must be an integer, not a boolean.")

    def validate(self, *, profile_label: str) -> None:
        validate_score_distribution(
            self.micro, self.mystiko, self.macro, profile_label=profile_label
        )


def set_editorial_classification(
    *,
    game: Game,
    updated_by: AbstractBaseUser,
    challenge: ScoreDistribution,
    reward: ScoreDistribution,
    notes: str = "",
) -> EditorialClassification:
    """Create or update a complete editorial classification atomically.

    Args:
        game: Must be a saved ``Game`` instance.
        updated_by: Must be a saved user.
        challenge: Challenge profile score distribution.
        reward: Reward profile score distribution.
        notes: Optional editorial notes.

    Returns:
        The saved ``EditorialClassification`` with both profiles attached.

    Raises:
        TypeError: Invalid game or user.
        ValidationError: Invalid score distribution for either profile.
    """
    if not isinstance(game, Game):
        raise TypeError("game must be a Game instance.")
    if game.pk is None:
        raise TypeError("game must be saved before creating a classification.")
    if updated_by is None or updated_by.pk is None:
        raise TypeError("updated_by must be a saved user.")

    # Validate both distributions before touching the database.
    challenge.validate(profile_label="Challenge")
    reward.validate(profile_label="Reward")

    with transaction.atomic():
        parent, _created = EditorialClassification.objects.update_or_create(
            game=game,
            defaults={
                "notes": notes,
                "updated_by": updated_by,
            },
        )
        parent.full_clean()

        _upsert_profile(
            parent,
            ChallengeProfile,
            "challenge_profile",
            challenge,
        )
        _upsert_profile(
            parent,
            RewardProfile,
            "reward_profile",
            reward,
        )

    return parent


def _upsert_profile(
    parent: EditorialClassification,
    profile_model,
    related_name: str,
    distribution: ScoreDistribution,
) -> None:
    """Create or update one profile row linked to *parent*."""
    existing = getattr(parent, related_name, None)
    fields = {
        "micro_score": distribution.micro,
        "mystiko_score": distribution.mystiko,
        "macro_score": distribution.macro,
    }
    if existing is not None:
        for attr, value in fields.items():
            setattr(existing, attr, value)
        existing.full_clean()
        existing.save()
    else:
        instance = profile_model(classification=parent, **fields)
        instance.full_clean()
        instance.save()
