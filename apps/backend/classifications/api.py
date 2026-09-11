"""
Classifications API router — SBGC-38 / SBGC-216 / SBGC-174.

Community score-submission endpoint (``/games/{slug}/submit-score``) and the
staff-gated delta-recalculation trigger (``/recalculate-delta``).
"""

from __future__ import annotations

from typing import Literal

from api.errors import STANDARD_ERROR_RESPONSES, ApiException
from games.models import Game
from ninja import Field, Router, Schema
from pydantic import field_validator

from classifications.services.delta_recalculation import (
    can_trigger_delta_recalculation,
    dispatch_delta_recalculation,
)
from classifications.services.submission_ingestion import (
    ingest_score_submission,
)

router = Router(tags=["Submissions"])


class DimensionScoresIn(Schema):
    micro: int = Field(..., ge=0, le=100)
    mystiko: int = Field(..., ge=0, le=100)
    macro: int = Field(..., ge=0, le=100)


class ScoreSubmissionIn(Schema):
    challenge: DimensionScoresIn
    reward: DimensionScoresIn
    aesthetic: Literal["SENSORY", "FANTASY", "NARRATIVE", "CHALLENGE"] | None = None

    @field_validator("aesthetic", mode="before")
    @classmethod
    def normalize_aesthetic(cls, value: object) -> object:
        """Accept any casing and validate against the canonical taxonomy.

        The canonical stored values are uppercase (SBGC-172); the picker and
        legacy clients may send lower case, so normalize before the ``Literal``
        membership check (an unknown value still fails with 422).
        """
        if isinstance(value, str):
            return value.strip().upper()
        return value


class ScoreSubmissionOut(Schema):
    id: int
    game_slug: str
    aesthetic: str | None = None
    is_duplicate: bool
    is_updated: bool
    is_created: bool
    submitted_at: str


@router.post(
    "/games/{slug}/submit-score",
    response={200: ScoreSubmissionOut, 201: ScoreSubmissionOut},
    summary="Submit community game scores",
    description=(
        "Ingest a community user's Challenge/Reward score submission with "
        "temporal duplicate rejection, in-place supersession, and 15-day "
        "branching (SBGC-216)."
    ),
)
def submit_game_score(request, slug: str, payload: ScoreSubmissionIn):
    if not request.user.is_authenticated:
        raise ApiException(401, "AUTHENTICATION_ERROR", "Authentication required.")

    challenge_sum = (
        payload.challenge.micro + payload.challenge.mystiko + payload.challenge.macro
    )
    if challenge_sum != 100:
        raise ApiException(
            422,
            "VALIDATION_ERROR",
            "Challenge scores must sum to exactly 100.",
        )

    reward_sum = payload.reward.micro + payload.reward.mystiko + payload.reward.macro
    if reward_sum != 100:
        raise ApiException(
            422,
            "VALIDATION_ERROR",
            "Reward scores must sum to exactly 100.",
        )

    game = Game.objects.publicly_listable().filter(slug=slug).first()
    if game is None:
        raise ApiException(404, "NOT_FOUND", "Game not found.")

    result = ingest_score_submission(
        user=request.user,
        game=game,
        payload=payload.model_dump(),
    )

    submitted_at = (
        getattr(result.submission, "updated_at", None) or result.submission.created_at
    ).isoformat()

    response_data = ScoreSubmissionOut(
        id=result.submission.pk,
        game_slug=game.slug,
        aesthetic=getattr(result.submission, "aesthetic", None),
        is_duplicate=result.is_duplicate,
        is_updated=result.is_updated,
        is_created=result.is_created,
        submitted_at=submitted_at,
    )
    return result.status_code, response_data


# ---------------------------------------------------------------------------
# Delta recalculation trigger — SBGC-174
# ---------------------------------------------------------------------------


class DeltaTriggerOut(Schema):
    status: str
    message: str
    recipient_email: str | None


@router.post(
    "/recalculate-delta",
    response={202: DeltaTriggerOut, **STANDARD_ERROR_RESPONSES},
    summary="Trigger a delta recalculation",
    description=(
        "Queue a global delta recalculation for all published Games with new or "
        "mutated submissions since their last completed calculation (SBGC-174)."
    ),
)
def trigger_delta_recalculation(request):
    user = request.user
    if not user.is_authenticated:
        raise ApiException(401, "AUTHENTICATION_ERROR", "Authentication required.")

    if not can_trigger_delta_recalculation(user):
        raise ApiException(
            403,
            "AUTHORIZATION_ERROR",
            "Only Superusers and Moderators may trigger recalculations.",
        )

    dispatch_delta_recalculation(user)

    return 202, DeltaTriggerOut(
        status="queued",
        message="Delta recalculation worker started successfully.",
        recipient_email=user.email or None,
    )
