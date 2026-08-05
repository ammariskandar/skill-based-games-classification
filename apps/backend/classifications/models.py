"""
Editorial classification models — SBGC-46.

One editorial classification per Game with separate Challenge and Reward
profile models.  Each profile independently contains Micro / Mystiko /
Macro integer scores that must sum to exactly 100.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from classifications.validation import validate_score_distribution


class EditorialClassification(models.Model):
    """One editorial classification per Game."""

    game = models.OneToOneField(
        "games.Game",
        on_delete=models.CASCADE,
        related_name="editorial_classification",
    )

    notes = models.TextField(blank=True)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_editorial_classifications",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["game__name", "game__id"]

    def __str__(self) -> str:
        game_name = self.game.name if self.game_id else "(unsaved)"
        return f"Editorial classification for {game_name}"


# ---------------------------------------------------------------------------
# Challenge profile
# ---------------------------------------------------------------------------


class ChallengeProfile(models.Model):
    """Challenge component of an editorial classification."""

    classification = models.OneToOneField(
        EditorialClassification,
        on_delete=models.CASCADE,
        related_name="challenge_profile",
    )

    micro_score = models.PositiveSmallIntegerField(
        help_text="Challenge Micro score — moment-to-moment skill demands.",
        verbose_name="Challenge Micro",
    )

    mystiko_score = models.PositiveSmallIntegerField(
        help_text="Challenge Mystiko score — depth, knowledge, and discovery.",
        verbose_name="Challenge Mystiko",
    )

    macro_score = models.PositiveSmallIntegerField(
        help_text="Challenge Macro score — strategic and long-term demands.",
        verbose_name="Challenge Macro",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(micro_score__gte=0, micro_score__lte=100)
                    & models.Q(mystiko_score__gte=0, mystiko_score__lte=100)
                    & models.Q(macro_score__gte=0, macro_score__lte=100)
                ),
                name="challenge_scores_range_ck",
            ),
        ]

    def __str__(self) -> str:
        return f"Challenge {self.micro_score}/{self.mystiko_score}/{self.macro_score}"

    def clean(self) -> None:
        super().clean()
        validate_score_distribution(
            self.micro_score,
            self.mystiko_score,
            self.macro_score,
            profile_label="Challenge",
        )


# ---------------------------------------------------------------------------
# Reward profile
# ---------------------------------------------------------------------------


class RewardProfile(models.Model):
    """Reward component of an editorial classification."""

    classification = models.OneToOneField(
        EditorialClassification,
        on_delete=models.CASCADE,
        related_name="reward_profile",
    )

    micro_score = models.PositiveSmallIntegerField(
        help_text="Reward Micro score — immediate feedback and pacing.",
        verbose_name="Reward Micro",
    )

    mystiko_score = models.PositiveSmallIntegerField(
        help_text="Reward Mystiko score — discovery-based satisfaction.",
        verbose_name="Reward Mystiko",
    )

    macro_score = models.PositiveSmallIntegerField(
        help_text="Reward Macro score — long-term progression and achievement.",
        verbose_name="Reward Macro",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(micro_score__gte=0, micro_score__lte=100)
                    & models.Q(mystiko_score__gte=0, mystiko_score__lte=100)
                    & models.Q(macro_score__gte=0, macro_score__lte=100)
                ),
                name="reward_scores_range_ck",
            ),
        ]

    def __str__(self) -> str:
        return f"Reward {self.micro_score}/{self.mystiko_score}/{self.macro_score}"

    def clean(self) -> None:
        super().clean()
        validate_score_distribution(
            self.micro_score,
            self.mystiko_score,
            self.macro_score,
            profile_label="Reward",
        )


__all__ = [
    "ChallengeProfile",
    "EditorialClassification",
    "RewardProfile",
]
