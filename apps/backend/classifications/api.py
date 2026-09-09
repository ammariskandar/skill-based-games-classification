"""
Classifications API router — SBGC-38 / SBGC-216.

Community score-submission endpoint.  ``/games/{slug}/submit-score`` accepts a
six-dimensional Challenge/Reward profile from an authenticated community user
and runs it through the temporal duplicate/supersession ingestion pipeline.
"""

from __future__ import annotations

from api.errors import ApiException
from games.models import Game
from ninja import Field, Router, Schema

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


class ScoreSubmissionOut(Schema):
    id: int
    game_slug: str
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
        is_duplicate=result.is_duplicate,
        is_updated=result.is_updated,
        is_created=result.is_created,
        submitted_at=submitted_at,
    )
    return result.status_code, response_data
