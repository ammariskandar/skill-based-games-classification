"""
Editorial classification submission service — SBGC-63.

Create and edit human editorial classification submissions.  Each
submission is owned by one ``Game`` and one ``submitted_by`` User, with
``updated_by`` recording the operator who last changed the record.  Role
and base-weight provenance are snapshotted at creation and never silently
re-resolved on edit.

No statistical/derived scoring is implemented here (SBGC-65 owns that).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.db import IntegrityError, transaction
from games.models import Game

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    EditorialGroupProfile,
    RewardProfile,
)
from classifications.roles import BASE_WEIGHTS, EditorialRole
from classifications.validation import validate_score_distribution


@dataclass(frozen=True)
class ScoreDistribution:
    """Immutable three-score distribution for one profile."""

    micro: int
    mystiko: int
    macro: int

    def __post_init__(self) -> None:
        for name in ("micro", "mystiko", "macro"):
            if isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be an integer, not a boolean.")

    def validate(self, *, profile_label: str) -> None:
        validate_score_distribution(
            self.micro, self.mystiko, self.macro, profile_label=profile_label
        )


class EditorialRoleError(Exception):
    """Raised when a User's editorial role cannot be resolved uniquely."""


class EditorialSubmissionError(Exception):
    """Raised for invalid submission identity operations."""


def _resolve_group_flags(groups) -> tuple[bool, bool]:
    """Return (has_moderator, has_community_leader) for a Group collection.

    ``groups`` may be ``None`` or an iterable/queryset of Group instances.
    """
    if groups is None:
        profiles = EditorialGroupProfile.objects.none().values_list(
            "is_moderator", "is_community_leader"
        )
    else:
        profiles = EditorialGroupProfile.objects.filter(group__in=groups).values_list(
            "is_moderator", "is_community_leader"
        )

    has_moderator = False
    has_community_leader = False
    for is_moderator, is_community_leader in profiles:
        has_moderator = has_moderator or is_moderator
        has_community_leader = has_community_leader or is_community_leader
    return (has_moderator, has_community_leader)


def group_set_has_role_conflict(groups) -> bool:
    """Return True when *groups* resolve to both Moderator and Community Leader.

    This is the reusable editorial-role group-selection validator used by
    both the User Admin form and the domain role resolver.
    """
    has_moderator, has_community_leader = _resolve_group_flags(groups)
    return has_moderator and has_community_leader


def resolve_editorial_role(user) -> str:
    """Return the user's current editorial statistical role.

    Resolution order:

    1. ``user.is_superuser`` → SUPERUSER.
    2. Moderator flag present → MODERATOR.
    3. Community Leader flag present → COMMUNITY_LEADER.
    4. Neither flag → COMMUNITY.

    A user belonging to both a Moderator group and a Community Leader group
    is a conflict and raises ``EditorialRoleError`` rather than silently
    resolving to a higher role.
    """
    if not hasattr(user, "pk") or user.pk is None:
        raise TypeError("user must be saved before resolving a role.")

    if getattr(user, "is_superuser", False):
        return EditorialRole.SUPERUSER

    groups = getattr(user, "groups", None)
    has_moderator, has_community_leader = _resolve_group_flags(
        groups.all() if groups is not None else None
    )

    if has_moderator and has_community_leader:
        raise EditorialRoleError(
            "User resolves to both Moderator and Community Leader groups."
        )

    if has_moderator:
        return EditorialRole.MODERATOR
    if has_community_leader:
        return EditorialRole.COMMUNITY_LEADER
    return EditorialRole.COMMUNITY


def create_submission(
    *,
    game: Game,
    submitted_by: AbstractBaseUser,
    updated_by: AbstractBaseUser,
    challenge: ScoreDistribution,
    reward: ScoreDistribution,
    notes: str = "",
) -> EditorialClassification:
    """Create a complete editorial submission atomically."""
    _validate_participants(game, submitted_by, updated_by)

    if EditorialClassification.objects.filter(
        game=game, submitted_by=submitted_by
    ).exists():
        raise EditorialSubmissionError(
            "This user has already submitted scores for this game."
        )

    role = resolve_editorial_role(submitted_by)
    challenge.validate(profile_label="Challenge")
    reward.validate(profile_label="Reward")

    with transaction.atomic():
        submission = EditorialClassification(
            game=game,
            submitted_by=submitted_by,
            submitted_role=role,
            submitted_base_weight=BASE_WEIGHTS[role],
            updated_by=updated_by,
            notes=notes,
        )
        submission.full_clean()
        _persist_submission(submission, challenge, reward)

    return submission


def update_submission(
    submission: EditorialClassification,
    *,
    updated_by: AbstractBaseUser | None = None,
    challenge: ScoreDistribution | None = None,
    reward: ScoreDistribution | None = None,
    notes: str | None = None,
) -> EditorialClassification:
    """Edit editorial input fields without changing submission identity."""
    if not isinstance(submission, EditorialClassification):
        raise TypeError("submission must be an EditorialClassification instance.")
    if submission.pk is None:
        raise EditorialSubmissionError("submission must be saved before updating.")
    if updated_by is not None and updated_by.pk is None:
        raise TypeError("updated_by must be a saved user.")

    if challenge is not None:
        challenge.validate(profile_label="Challenge")
    if reward is not None:
        reward.validate(profile_label="Reward")

    with transaction.atomic():
        if notes is not None:
            submission.notes = notes
        if updated_by is not None:
            submission.updated_by = updated_by
        submission.full_clean()
        submission.save(update_fields=["notes", "updated_by"])

        if challenge is not None:
            _set_profile(submission, ChallengeProfile, "challenge_profile", challenge)
        if reward is not None:
            _set_profile(submission, RewardProfile, "reward_profile", reward)

    submission.refresh_from_db()
    return submission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_participants(
    game: Game,
    submitted_by: AbstractBaseUser,
    updated_by: AbstractBaseUser,
) -> None:
    if not isinstance(game, Game):
        raise TypeError("game must be a Game instance.")
    if game.pk is None:
        raise TypeError("game must be saved before creating a submission.")
    if submitted_by is None or submitted_by.pk is None:
        raise TypeError("submitted_by must be a saved user.")
    if updated_by is None or updated_by.pk is None:
        raise TypeError("updated_by must be a saved user.")


def _persist_submission(submission, challenge, reward) -> None:
    """Save the submission + profiles, translating a lost duplicate race.

    A concurrent request may win the ``(game, submitted_by)`` uniqueness
    race after the service pre-check.  The nested atomic block keeps the
    outer transaction usable so the known duplicate can be reported as a
    domain error instead of a raw IntegrityError.
    """
    try:
        with transaction.atomic():
            submission.save()
            _create_profile(
                submission, ChallengeProfile, "challenge_profile", challenge
            )
            _create_profile(submission, RewardProfile, "reward_profile", reward)
    except IntegrityError as exc:
        if _is_duplicate_submission_integrity_error(exc):
            raise EditorialSubmissionError(
                "This user has already submitted scores for this game."
            ) from exc
        raise


def _is_duplicate_submission_integrity_error(exc: IntegrityError) -> bool:
    """Return True when *exc* is the known (game, submitted_by) unique violation."""
    message = str(exc)
    return "editorial_submission_game_user_uniq" in message or (
        "classifications_editorialclassification" in message
        and "submitted_by_id" in message
    )


def _create_profile(submission, profile_model, related_name, distribution) -> None:
    instance = profile_model(classification=submission)
    _apply_distribution(instance, distribution)
    instance.full_clean()
    instance.save()
    setattr(submission, related_name, instance)


def _update_profile(profile, distribution) -> None:
    _apply_distribution(profile, distribution)
    profile.full_clean()
    profile.save()


def _set_profile(submission, profile_model, related_name, distribution) -> None:
    try:
        profile = getattr(submission, related_name)
    except profile_model.DoesNotExist:
        profile = None
    if profile is None:
        _create_profile(submission, profile_model, related_name, distribution)
    else:
        _update_profile(profile, distribution)


def _apply_distribution(profile, distribution: ScoreDistribution) -> None:
    profile.micro_score = distribution.micro
    profile.mystiko_score = distribution.mystiko
    profile.macro_score = distribution.macro


__all__ = [
    "EditorialRoleError",
    "EditorialSubmissionError",
    "ScoreDistribution",
    "create_submission",
    "group_set_has_role_conflict",
    "resolve_editorial_role",
    "update_submission",
]
