"""
Questionnaire API router — SBGC-172 (Epic SBGC-171).

``POST /api/v1/questionnaire/resolve-aesthetic`` resolves a Game's dominant
and secondary aesthetics from its Q1/Q2 answers and returns the Part 1
(Challenge) / Part 2 (Reward) question-set dispatch contract.

The resolver is pure and stateless: it never writes ``Game.aesthetic`` or any
submission record.  Canonical persistence and precedence handling belong to
the authenticated persistence tickets (SBGC-175 / SBGC-176).
"""

from __future__ import annotations

from api.errors import STANDARD_ERROR_RESPONSES, ApiException
from api.schemas import ApiErrorResponse
from games.models import Game
from ninja import Router, Schema

from classifications.questionnaire.aesthetic_resolver import resolve_from_options
from classifications.questionnaire.domain import QuestionnaireDomainError

router = Router(tags=["Questionnaire"])


class AestheticResolveIn(Schema):
    game_slug: str
    q1_option_id: str
    q2_option_id: str


class Part2SplitOut(Schema):
    is_split: bool
    q9_to_q11_set: str
    q12_to_q14_set: str


class AestheticResolveOut(Schema):
    game_slug: str
    game_name: str
    dominant_aesthetic: str
    secondary_aesthetic: str | None
    is_true_aesthetic: bool
    part1_challenge_set: str
    part2_reward_config: Part2SplitOut


@router.post(
    "/resolve-aesthetic",
    response={
        200: AestheticResolveOut,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    summary="Resolve questionnaire aesthetics",
    description=(
        "Resolve a publicly listed Game's dominant/secondary aesthetics from "
        "its Q1/Q2 answers and return the Part 1/Part 2 question-set routing "
        "(SBGC-172)."
    ),
)
def resolve_questionnaire_aesthetic(request, payload: AestheticResolveIn):
    game = Game.objects.publicly_listable().filter(slug=payload.game_slug).first()
    if game is None:
        raise ApiException(
            404,
            "NOT_FOUND",
            f"Active game '{payload.game_slug}' not found.",
        )

    try:
        resolution = resolve_from_options(payload.q1_option_id, payload.q2_option_id)
    except QuestionnaireDomainError as exc:
        raise ApiException(422, "VALIDATION_ERROR", str(exc)) from exc

    secondary = resolution.secondary_aesthetic
    return AestheticResolveOut(
        game_slug=game.slug,
        game_name=game.name,
        dominant_aesthetic=resolution.dominant_aesthetic.value,
        secondary_aesthetic=secondary.value if secondary is not None else None,
        is_true_aesthetic=resolution.is_true_aesthetic,
        part1_challenge_set=resolution.part1_challenge_set.value,
        part2_reward_config=Part2SplitOut(
            is_split=resolution.part2_reward_config.is_split,
            q9_to_q11_set=resolution.part2_reward_config.q9_to_q11_set.value,
            q12_to_q14_set=resolution.part2_reward_config.q12_to_q14_set.value,
        ),
    )
