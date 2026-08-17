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
from django.utils import timezone

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

    def validate_constraints(self, exclude=None):
        """Suppress the raw CheckConstraint name in favour of the friendly message."""
        try:
            super().validate_constraints(exclude)
        except ValidationError as exc:
            new_dict = {}
            for field, messages in exc.message_dict.items():
                filtered = [m for m in messages if not _is_db_constraint_message(m)]
                if filtered:
                    new_dict[field] = filtered
            if new_dict:
                raise ValidationError(new_dict) from exc


def _is_db_constraint_message(message: str) -> bool:
    return "is violated" in message or "Constraint" in message or "_ck" in message


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
            models.CheckConstraint(
                condition=(
                    models.Q(
                        submitted_role=EditorialRole.SUPERUSER,
                        submitted_base_weight=BASE_WEIGHTS[EditorialRole.SUPERUSER],
                    )
                    | models.Q(
                        submitted_role=EditorialRole.MODERATOR,
                        submitted_base_weight=BASE_WEIGHTS[EditorialRole.MODERATOR],
                    )
                    | models.Q(
                        submitted_role=EditorialRole.COMMUNITY_LEADER,
                        submitted_base_weight=BASE_WEIGHTS[
                            EditorialRole.COMMUNITY_LEADER
                        ],
                    )
                    | models.Q(
                        submitted_role=EditorialRole.COMMUNITY,
                        submitted_base_weight=BASE_WEIGHTS[EditorialRole.COMMUNITY],
                    )
                ),
                name="editorial_submission_role_weight_ck",
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

    def clean(self) -> None:
        super().clean()
        expected = BASE_WEIGHTS.get(self.submitted_role)
        if (
            expected is not None
            and self.submitted_base_weight is not None
            and self.submitted_base_weight != expected
        ):
            label = dict(EditorialRole.choices).get(
                self.submitted_role, self.submitted_role
            )
            raise ValidationError(
                {
                    "submitted_base_weight": (
                        f"Base weight for role {label} must be {expected}."
                    )
                }
            )

    def validate_constraints(self, exclude=None):
        """Translate the known duplicate-submission constraint into friendly wording."""
        try:
            super().validate_constraints(exclude)
        except ValidationError as exc:
            new_dict = {}
            for field, messages in exc.message_dict.items():
                new_dict[field] = [
                    "This user has already submitted scores for this game."
                    if "already exists" in m
                    else m
                    for m in messages
                ]
            raise ValidationError(new_dict) from exc

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

    def validate_constraints(self, exclude=None):
        try:
            super().validate_constraints(exclude)
        except ValidationError as exc:
            new_dict = {}
            for field, messages in exc.message_dict.items():
                filtered = [m for m in messages if not _is_db_constraint_message(m)]
                if filtered:
                    new_dict[field] = filtered
            if new_dict:
                raise ValidationError(new_dict) from exc


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

    def validate_constraints(self, exclude=None):
        try:
            super().validate_constraints(exclude)
        except ValidationError as exc:
            new_dict = {}
            for field, messages in exc.message_dict.items():
                filtered = [m for m in messages if not _is_db_constraint_message(m)]
                if filtered:
                    new_dict[field] = filtered
            if new_dict:
                raise ValidationError(new_dict) from exc


# ---------------------------------------------------------------------------
# Derived-classification persistence — SBGC-65
#
# Derived statistics are mathematical outputs, never editable editorial
# inputs.  Snapshots carry full provenance; the DB is the last-resort
# integrity layer for one-current-per-Game promotion.
# ---------------------------------------------------------------------------


class CalculationEpoch(models.Model):
    """One daily calculation batch.

    A scheduler (platform cron or equivalent) normally starts one epoch per
    calendar day around 00:00 system time.  Scheduler behavior is operational;
    the cutoff semantics are normative (Part E.1).
    """

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        PARTIAL = "partial", "Partial"

    epoch_id = models.CharField(max_length=64, unique=True)
    cutoff_at = models.DateTimeField()
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    master_version = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.RUNNING
    )
    games_attempted = models.PositiveIntegerField(default=0)
    games_succeeded = models.PositiveIntegerField(default=0)
    games_failed = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-cutoff_at"]

    def __str__(self) -> str:
        return f"Calculation epoch {self.epoch_id}"


class ClassificationSnapshot(models.Model):
    """One immutable versioned derived-result snapshot for one Game/epoch.

    Exactly one snapshot per Game is current.  A failed run never becomes
    current; the previous successful snapshot remains the published fallback
    and is marked stale internally (Part E.3).
    """

    game = models.ForeignKey(
        "games.Game",
        on_delete=models.CASCADE,
        related_name="classification_snapshots",
    )

    epoch = models.ForeignKey(
        CalculationEpoch,
        on_delete=models.PROTECT,
        related_name="snapshots",
    )

    regime = models.CharField(max_length=16)
    status = models.CharField(max_length=48)

    input_population_hash = models.CharField(max_length=64, blank=True)
    received_count = models.PositiveIntegerField(default=0)
    invalid_count = models.PositiveIntegerField(default=0)
    validated_count = models.PositiveIntegerField(default=0)
    cutoff_at = models.DateTimeField()
    calculated_at = models.DateTimeField(default=timezone.now)

    master_version = models.CharField(max_length=64, blank=True)
    methods_version = models.CharField(max_length=64, blank=True)
    bhpcm_version = models.CharField(max_length=64, blank=True)
    confidence_final_version = models.CharField(max_length=64, blank=True)

    method_1_status = models.CharField(max_length=48, blank=True)
    method_2_status = models.CharField(max_length=48, blank=True)
    method_3_status = models.CharField(max_length=48, blank=True)

    method_1_raw_challenge = models.JSONField(null=True, blank=True)
    method_1_raw_reward = models.JSONField(null=True, blank=True)
    method_1_integer_challenge = models.JSONField(null=True, blank=True)
    method_1_integer_reward = models.JSONField(null=True, blank=True)

    method_2_raw_challenge = models.JSONField(null=True, blank=True)
    method_2_raw_reward = models.JSONField(null=True, blank=True)
    method_2_integer_challenge = models.JSONField(null=True, blank=True)
    method_2_integer_reward = models.JSONField(null=True, blank=True)

    method_3_raw_challenge = models.JSONField(null=True, blank=True)
    method_3_raw_reward = models.JSONField(null=True, blank=True)
    method_3_integer_challenge = models.JSONField(null=True, blank=True)
    method_3_integer_reward = models.JSONField(null=True, blank=True)

    unified_raw_challenge = models.JSONField(null=True, blank=True)
    unified_raw_reward = models.JSONField(null=True, blank=True)
    unified_integer_challenge = models.JSONField(null=True, blank=True)
    unified_integer_reward = models.JSONField(null=True, blank=True)

    confidence_final = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    confidence_label = models.CharField(max_length=16, blank=True)
    confidence_provenance = models.JSONField(default=dict, blank=True)
    conflict_classification = models.CharField(max_length=32, blank=True)

    provenance = models.JSONField(default=dict, blank=True)

    is_current = models.BooleanField(default=False)
    became_current_at = models.DateTimeField(null=True, blank=True)
    is_stale = models.BooleanField(default=False)

    attempt_count = models.PositiveIntegerField(default=1)
    failure_category = models.CharField(max_length=48, blank=True)
    error_summary = models.TextField(blank=True)

    class Meta:
        ordering = ["game__id", "-calculated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["game"],
                condition=models.Q(is_current=True),
                name="classification_snapshot_single_current_uniq",
            ),
        ]

    def __str__(self) -> str:
        game_id = self.game_id  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
        return f"Classification snapshot for {game_id} @ {self.cutoff_at}"


class BoundaryCalibration(models.Model):
    """Static per-Game/per-version boundary-continuity constant (Part D3.3).

    Calibrated once at the calibration moment; never silently recomputed by
    ordinary submission activity within the same calculation version.
    """

    game = models.ForeignKey(
        "games.Game",
        on_delete=models.CASCADE,
        related_name="boundary_calibrations",
    )

    master_version = models.CharField(max_length=64)
    status = models.CharField(max_length=48, blank=True)
    delta = models.FloatField(default=0.0)
    calibration_population_hash = models.CharField(max_length=64, blank=True)
    population_size = models.PositiveIntegerField(default=0)
    subset_count_attempted = models.PositiveIntegerField(default=0)
    subset_count_ready = models.PositiveIntegerField(default=0)
    sampler_version = models.CharField(max_length=64, blank=True)
    seed_or_stream = models.CharField(max_length=256, blank=True)
    calibrated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "master_version"],
                name="boundary_calibration_game_version_uniq",
            ),
        ]

    def __str__(self) -> str:
        game_id = self.game_id  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
        return f"Boundary calibration for {game_id} v{self.master_version}"


class CalculationAttempt(models.Model):
    """One attempt (initial or retry) at calculating a Game inside an epoch.

    Maximum four attempts per Game per epoch: attempt 1 = initial scheduled
    attempt, attempts 2-4 = retries 1-3 (ticket section 9).
    """

    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    game = models.ForeignKey(
        "games.Game",
        on_delete=models.CASCADE,
        related_name="calculation_attempts",
    )

    epoch = models.ForeignKey(
        CalculationEpoch,
        on_delete=models.CASCADE,
        related_name="attempts",
    )

    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices)
    failure_category = models.CharField(max_length=48, blank=True)
    error_summary = models.TextField(blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "epoch", "attempt_number"],
                name="calculation_attempt_game_epoch_number_uniq",
            ),
        ]

    def __str__(self) -> str:
        game_id = self.game_id  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
        epoch_id = self.epoch_id  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
        return f"Attempt {self.attempt_number} for {game_id} in epoch {epoch_id}"


__all__ = [
    "BoundaryCalibration",
    "CalculationAttempt",
    "CalculationEpoch",
    "ChallengeProfile",
    "ClassificationSnapshot",
    "EditorialClassification",
    "EditorialGroupProfile",
    "RewardProfile",
]
