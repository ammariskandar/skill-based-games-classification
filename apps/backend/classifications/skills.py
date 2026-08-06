"""
Skill and profile vocabularies — SBGC-49.

Helper enumerations and pure functions for editorial classification
score analysis.  No database access, no network access, no migrations.
"""

from __future__ import annotations

from django.db import models

from classifications.validation import validate_score_distribution


class SkillCategory(models.TextChoices):
    """The three skill dimensions used in editorial classification."""

    MICRO = "micro", "Micro"
    MYSTIKO = "mystiko", "Mystiko"
    MACRO = "macro", "Macro"


class EditorialProfile(models.TextChoices):
    """The two independent editorial profiles."""

    CHALLENGE = "challenge", "Challenge"
    REWARD = "reward", "Reward"


def dominant_skill_category(
    *,
    micro_score: int,
    mystiko_score: int,
    macro_score: int,
) -> str | None:
    """
    Return the ``SkillCategory`` value with the strictly highest score,
    or ``None`` when two or more scores tie for first place.

    Validates range and total exactly 100 via the shared score-distribution
    validator (booleans, non-integers, out-of-range, and wrong totals are
    rejected before dominance is calculated).

    Raises:
        ValidationError: If the three scores do not form a valid
            distribution (range 0–100 each, total exactly 100, no booleans).
    """
    # Reuse the shared validator for type, range, and total checks.
    validate_score_distribution(
        micro_score, mystiko_score, macro_score, profile_label="Score"
    )

    scores: dict[str, int] = {
        SkillCategory.MICRO: micro_score,
        SkillCategory.MYSTIKO: mystiko_score,
        SkillCategory.MACRO: macro_score,
    }

    highest = max(scores.values())
    # Count how many categories share the highest score.
    winners = [k for k, v in scores.items() if v == highest]

    if len(winners) == 1:
        return winners[0]

    return None


__all__ = [
    "EditorialProfile",
    "SkillCategory",
    "dominant_skill_category",
]
