"""
Editorial classification models — SBGC-46.

One editorial classification per Game with separate Challenge and Reward
profile models.  Each profile independently contains Micro / Mystiko /
Macro integer scores that must sum to exactly 100.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from classifications.roles import BASE_WEIGHTS, EditorialRole
from classifications.validation import validate_score_distribution


def _reject_boolean_scores(instance, profile_label: str) -> None:
    """Reject boolean values on score fields before Django field coercion.

    Django ``PositiveSmallIntegerField.to_python()`` converts ``True → 1``
    and ``False → 0`` during ``clean_fields()``, which runs before
    ``clean()``.  This helper inspects the raw instance attributes and
    raises ``ValidationError`` with profile-specific messages while
    booleans are still detectable.
    """
    errors: dict[str, list[str]] = {}
    for attr, label in (
        ("micro_score", f"{profile_label} Micro"),
        ("mystiko_score", f"{profile_label} Mystiko"),
        ("macro_score", f"{profile_label} Macro"),
    ):
        value = getattr(instance, attr)
        if isinstance(value, bool):
            errors.setdefault(attr, []).append(
                f"{label} must be an integer, not a boolean."
            )
    if errors:
        raise ValidationError(errors)


class EditorialGroupProfile(models.Model):
    """Editorial statistical-role metadata attached to a Django Group.

    Moderator and Community Leader flags are mutually exclusive.  Neither
    flag resolves to the Community statistical role.  Superuser is never a
    Group flag — it derives solely from ``User.is_superuser``.
    """

    group = models.OneToOneField(
        "auth.Group",
        on_delete=models.CASCADE,
        related_name="editorial_profile",
    )

    is_moderator = models.BooleanField(default=False)
    is_community_leader = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(is_moderator=True, is_community_leader=True),
                name="editorial_group_role_exclusive_ck",
            ),
        ]

    def __str__(self) -> str:
        return f"Editorial role profile for {self.group}"

    def clean(self) -> None:
        super().clean()
        if self.is_moderator and self.is_community_leader:
            raise ValidationError(
                {"__all__": ["A group cannot be both Moderator and Community Leader."]}
            )


class EditorialClassification(models.Model):
    """A single human editorial classification submission for one Game.

    A Game may have many submissions from different users, but each user may
    submit at most once per Game (``(game, submitted_by)`` unique).
    """

    game = models.ForeignKey(
        "games.Game",
        on_delete=models.CASCADE,
        related_name="editorial_classification",
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_editorial_classifications",
    )

    submitted_role = models.CharField(
        max_length=32,
        choices=EditorialRole.choices,
        default=EditorialRole.COMMUNITY,
    )

    submitted_base_weight = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=BASE_WEIGHTS[EditorialRole.COMMUNITY],
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
        verbose_name = "Editorial classification submission"
        verbose_name_plural = "Editorial classification submissions"
        constraints = [
            models.UniqueConstraint(
                fields=["game", "submitted_by"],
                name="editorial_submission_game_user_uniq",
            ),
        ]

    def __str__(self) -> str:
        game_name = self.game.name if self.game_id else "(unsaved)"  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
        submitter = (
            self.submitted_by.username
            if self.submitted_by_id  # type: ignore[reportAttributeAccessIssue]
            else "(unsaved submitter)"
        )
        return f"Editorial classification for {game_name} by {submitter}"

    if TYPE_CHECKING:
        challenge_profile: ChallengeProfile
        reward_profile: RewardProfile


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
            models.CheckConstraint(
                condition=models.Q(
                    micro_score=(
                        100 - models.F("mystiko_score") - models.F("macro_score")
                    )
                ),
                name="challenge_scores_total_100_ck",
            ),
        ]

    def __str__(self) -> str:
        return f"Challenge {self.micro_score}/{self.mystiko_score}/{self.macro_score}"

    @property
    def dominant_skill_category(self) -> str | None:
        from classifications.skills import dominant_skill_category

        return dominant_skill_category(
            micro_score=self.micro_score,
            mystiko_score=self.mystiko_score,
            macro_score=self.macro_score,
        )

    def clean_fields(self, exclude=None):
        _reject_boolean_scores(self, "Challenge")
        super().clean_fields(exclude=exclude)

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
            models.CheckConstraint(
                condition=models.Q(
                    micro_score=(
                        100 - models.F("mystiko_score") - models.F("macro_score")
                    )
                ),
                name="reward_scores_total_100_ck",
            ),
        ]

    def __str__(self) -> str:
        return f"Reward {self.micro_score}/{self.mystiko_score}/{self.macro_score}"

    @property
    def dominant_skill_category(self) -> str | None:
        from classifications.skills import dominant_skill_category

        return dominant_skill_category(
            micro_score=self.micro_score,
            mystiko_score=self.mystiko_score,
            macro_score=self.macro_score,
        )

    def clean_fields(self, exclude=None):
        _reject_boolean_scores(self, "Reward")
        super().clean_fields(exclude=exclude)

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
    "EditorialGroupProfile",
    "RewardProfile",
]
