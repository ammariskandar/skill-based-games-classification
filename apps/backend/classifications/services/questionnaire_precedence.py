"""
Questionnaire precedence & persistence engine — SBGC-175 (Epic SBGC-171).

Implements the community conflict state machine that turns a completed
questionnaire into a calculation-pool row:

* Staff (Superuser / Moderator / Community Leader) → routed to
  ``EditorialClassification`` (zero ``UserGameScoreSubmission`` rows).
* No existing manual submission → direct promotion.
* Manual submission age >= 10 days → automatic in-place overwrite.
* Manual submission age < 10 days → requires an explicit resolution
  (``OVERWRITE`` or ``KEEP_MANUAL``).

Every attempt is audited immutably in ``QuestionnaireResult`` regardless of
the outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from games.models import Game

from classifications.models import (
    EditorialClassification,
    QuestionnaireClassification,
    QuestionnaireResult,
    UserGameScoreSubmission,
)
from classifications.services.submission_ingestion import is_editorial_submitter
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
    update_submission,
)

TEN_DAYS = timedelta(days=10)
CONFLICT_RESOLUTIONS = ("OVERWRITE", "KEEP_MANUAL")


@dataclass(frozen=True)
class PrecedenceEvaluation:
    """Whether a manual submission conflicts with an incoming questionnaire."""

    has_conflict: bool
    requires_user_choice: bool
    manual_submission_id: int | None
    manual_created_at: str | None
    age_days: int | None


@dataclass(frozen=True)
class IngestionOutcome:
    """Result of one questionnaire ingestion."""

    questionnaire_result_id: int
    classification_status: str
    is_active_in_calculation: bool
    routed_to_editorial: bool
    message: str


def _dims(source: dict[str, Any], profile: str) -> tuple[int, int, int]:
    data = source[profile]
    return data["micro"], data["macro"], data["mystiko"]


def evaluate_manual_conflict(user: User, game: Game) -> PrecedenceEvaluation:
    """Evaluate whether an existing manual submission conflicts with a questionnaire."""
    latest_manual = (
        UserGameScoreSubmission.objects.filter(
            user=user,
            game=game,
            source=UserGameScoreSubmission.SubmissionSource.MANUAL,
        )
        .order_by("-created_at")
        .first()
    )

    if latest_manual is None:
        return PrecedenceEvaluation(
            has_conflict=False,
            requires_user_choice=False,
            manual_submission_id=None,
            manual_created_at=None,
            age_days=None,
        )

    age = timezone.now() - latest_manual.created_at
    requires_choice = age < TEN_DAYS
    return PrecedenceEvaluation(
        has_conflict=True,
        requires_user_choice=requires_choice,
        manual_submission_id=latest_manual.pk,
        manual_created_at=latest_manual.created_at.isoformat(),
        age_days=age.days,
    )


def ingest_questionnaire_submission(
    user: User,
    game: Game,
    scoring_result: dict[str, Any],
    conflict_resolution: str | None = None,
) -> IngestionOutcome:
    """Persist a questionnaire and apply the precedence state machine."""
    with transaction.atomic():
        result = QuestionnaireResult.objects.create(
            user=user,
            game=game,
            version=scoring_result["version"],
            dominant_aesthetic=scoring_result["dominant_aesthetic"],
            secondary_aesthetic=scoring_result.get("secondary_aesthetic"),
            is_true_aesthetic=scoring_result["is_true_aesthetic"],
            answers=scoring_result["answers"],
            q15_rating=scoring_result["q15_rating"],
            **_score_fields(scoring_result),
        )

        # Staff gate: never write a community row.
        if is_editorial_submitter(user):
            _route_staff_to_editorial(user, game, result)
            classification, _ = QuestionnaireClassification.objects.update_or_create(
                user=user,
                game=game,
                defaults={
                    "latest_result": result,
                    "status": (
                        QuestionnaireClassification.PrecedenceStatus.STAFF_EDITORIAL_ROUTED
                    ),
                },
            )
            return IngestionOutcome(
                questionnaire_result_id=result.pk,
                classification_status=classification.status,
                is_active_in_calculation=True,
                routed_to_editorial=True,
                message="Staff questionnaire routed to EditorialClassification.",
            )

        # Community precedence evaluation.
        conflict = evaluate_manual_conflict(user, game)

        if conflict.requires_user_choice and conflict_resolution == "KEEP_MANUAL":
            classification, _ = QuestionnaireClassification.objects.update_or_create(
                user=user,
                game=game,
                defaults={
                    "latest_result": result,
                    "status": (
                        QuestionnaireClassification.PrecedenceStatus.ARCHIVED_KEPT_MANUAL
                    ),
                },
            )
            return IngestionOutcome(
                questionnaire_result_id=result.pk,
                classification_status=classification.status,
                is_active_in_calculation=False,
                routed_to_editorial=False,
                message=(
                    "Questionnaire result archived. Manual submission preserved "
                    "in calculation pool."
                ),
            )

        if (
            conflict.requires_user_choice
            and conflict_resolution not in CONFLICT_RESOLUTIONS
        ):
            raise ValueError(
                "A recent manual submission requires an explicit resolution "
                "('OVERWRITE' or 'KEEP_MANUAL')."
            )

        _promote_to_user_game_score_submission(user, game, result)

        classification, _ = QuestionnaireClassification.objects.update_or_create(
            user=user,
            game=game,
            defaults={
                "latest_result": result,
                "status": (
                    QuestionnaireClassification.PrecedenceStatus.ACTIVE_IN_CALCULATION
                ),
            },
        )
        return IngestionOutcome(
            questionnaire_result_id=result.pk,
            classification_status=classification.status,
            is_active_in_calculation=True,
            routed_to_editorial=False,
            message="Questionnaire promoted to active calculation submission.",
        )


def _score_fields(scoring_result: dict[str, Any]) -> dict[str, int]:
    raw_challenge = _dims(scoring_result["raw"], "challenge")
    raw_reward = _dims(scoring_result["raw"], "reward")
    normalized_challenge = _dims(scoring_result["normalized"], "challenge")
    normalized_reward = _dims(scoring_result["normalized"], "reward")
    adjusted_challenge = _dims(scoring_result["adjusted"], "challenge")
    adjusted_reward = _dims(scoring_result["adjusted"], "reward")

    micro, macro, mystiko = raw_challenge
    raw_reward_micro, raw_reward_macro, raw_reward_mystiko = raw_reward
    norm_challenge_micro, norm_challenge_macro, norm_challenge_mystiko = (
        normalized_challenge
    )
    norm_reward_micro, norm_reward_macro, norm_reward_mystiko = normalized_reward
    adj_challenge_micro, adj_challenge_macro, adj_challenge_mystiko = adjusted_challenge
    adj_reward_micro, adj_reward_macro, adj_reward_mystiko = adjusted_reward

    return {
        "raw_challenge_micro": micro,
        "raw_challenge_macro": macro,
        "raw_challenge_mystiko": mystiko,
        "raw_reward_micro": raw_reward_micro,
        "raw_reward_macro": raw_reward_macro,
        "raw_reward_mystiko": raw_reward_mystiko,
        "normalized_challenge_micro": norm_challenge_micro,
        "normalized_challenge_macro": norm_challenge_macro,
        "normalized_challenge_mystiko": norm_challenge_mystiko,
        "normalized_reward_micro": norm_reward_micro,
        "normalized_reward_macro": norm_reward_macro,
        "normalized_reward_mystiko": norm_reward_mystiko,
        "adjusted_challenge_micro": adj_challenge_micro,
        "adjusted_challenge_macro": adj_challenge_macro,
        "adjusted_challenge_mystiko": adj_challenge_mystiko,
        "adjusted_reward_micro": adj_reward_micro,
        "adjusted_reward_macro": adj_reward_macro,
        "adjusted_reward_mystiko": adj_reward_mystiko,
    }


def _promote_to_user_game_score_submission(
    user: User, game: Game, result: QuestionnaireResult
) -> None:
    """Overwrite the latest community row (or create one) with adjusted scores."""
    existing = (
        UserGameScoreSubmission.objects.select_for_update()
        .filter(user=user, game=game)
        .order_by("-created_at", "-id")
        .first()
    )
    adjusted = {
        "challenge_micro": result.adjusted_challenge_micro,
        "challenge_mystiko": result.adjusted_challenge_mystiko,
        "challenge_macro": result.adjusted_challenge_macro,
        "reward_micro": result.adjusted_reward_micro,
        "reward_mystiko": result.adjusted_reward_mystiko,
        "reward_macro": result.adjusted_reward_macro,
    }
    if existing is not None:
        existing.source = UserGameScoreSubmission.SubmissionSource.QUESTIONNAIRE
        existing.questionnaire_result = result
        for field, value in adjusted.items():
            setattr(existing, field, value)
        existing.save()
    else:
        UserGameScoreSubmission.objects.create(
            user=user,
            game=game,
            source=UserGameScoreSubmission.SubmissionSource.QUESTIONNAIRE,
            questionnaire_result=result,
            **adjusted,
        )


def _route_staff_to_editorial(
    user: User, game: Game, result: QuestionnaireResult
) -> None:
    """Pipe staff questionnaire scores into the editorial flow."""
    challenge = ScoreDistribution(
        micro=result.adjusted_challenge_micro,
        mystiko=result.adjusted_challenge_mystiko,
        macro=result.adjusted_challenge_macro,
    )
    reward = ScoreDistribution(
        micro=result.adjusted_reward_micro,
        mystiko=result.adjusted_reward_mystiko,
        macro=result.adjusted_reward_macro,
    )
    editorial = (
        EditorialClassification.objects.select_for_update()
        .filter(game=game, submitted_by=user)
        .first()
    )
    if editorial is not None:
        update_submission(
            editorial,
            updated_by=user,
            challenge=challenge,
            reward=reward,
        )
    else:
        create_submission(
            game=game,
            submitted_by=user,
            updated_by=user,
            challenge=challenge,
            reward=reward,
        )


__all__ = [
    "CONFLICT_RESOLUTIONS",
    "TEN_DAYS",
    "IngestionOutcome",
    "PrecedenceEvaluation",
    "evaluate_manual_conflict",
    "ingest_questionnaire_submission",
]
