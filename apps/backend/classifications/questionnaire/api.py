"""
Questionnaire API router — SBGC-172 / SBGC-173 (Epic SBGC-171).

``POST /api/v1/questionnaire/resolve-aesthetic`` resolves a Game's dominant
and secondary aesthetics from its Q1/Q2 answers and returns the Part 1
(Challenge) / Part 2 (Reward) question-set dispatch contract.

``POST /api/v1/questionnaire/assemble-tree`` additionally returns the concrete
versioned question graph (Q3–Q14 plus branches) for that resolution.

Both endpoints are pure and stateless: they never write ``Game.aesthetic`` or
any submission record.  Canonical persistence and precedence handling belong
to the authenticated persistence tickets (SBGC-175 / SBGC-176).
"""

from __future__ import annotations

from api.errors import STANDARD_ERROR_RESPONSES, ApiException
from api.schemas import ApiErrorResponse
from games.models import Game
from ninja import Router, Schema

from classifications.questionnaire.aesthetic_resolver import resolve_from_options
from classifications.questionnaire.domain import QuestionnaireDomainError
from classifications.questionnaire.registry.v1.assembler import (
    QuestionnaireRegistryError,
    assemble_questionnaire,
)
from classifications.questionnaire.registry.v1.types import (
    AnswerOption,
    QuestionNode,
    ScoreModifier,
)

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


# ---------------------------------------------------------------------------
# Assembled question tree — SBGC-173
# ---------------------------------------------------------------------------


class AssembleQuestionnaireIn(Schema):
    game_slug: str
    q1_option_id: str
    q2_option_id: str


class ScoreModifierOut(Schema):
    micro: int = 0
    macro: int = 0
    mystiko: int = 0


class AnswerOptionOut(Schema):
    id: str
    text: str
    modifiers: ScoreModifierOut
    next_question_id: str | None = None


class QuestionNodeOut(Schema):
    id: str
    root_id: str
    text: str
    target: str
    options: list[AnswerOptionOut]
    is_branch: bool
    parent_id: str | None = None
    helper_text: str | None = None


class AssembledQuestionnaireOut(Schema):
    version: str
    game_slug: str
    game_name: str
    dominant_aesthetic: str
    secondary_aesthetic: str | None
    is_true_aesthetic: bool
    part1_challenge_nodes: list[QuestionNodeOut]
    part2_reward_nodes: list[QuestionNodeOut]


def _modifier_out(modifiers: ScoreModifier) -> ScoreModifierOut:
    return ScoreModifierOut(
        micro=modifiers.micro,
        macro=modifiers.macro,
        mystiko=modifiers.mystiko,
    )


def _option_out(option: AnswerOption) -> AnswerOptionOut:
    return AnswerOptionOut(
        id=option.id,
        text=option.text,
        modifiers=_modifier_out(option.modifiers),
        next_question_id=option.next_question_id,
    )


def _node_out(node: QuestionNode) -> QuestionNodeOut:
    return QuestionNodeOut(
        id=node.id,
        root_id=node.root_id,
        text=node.text,
        target=node.target.value,
        options=[_option_out(option) for option in node.options],
        is_branch=node.is_branch,
        parent_id=node.parent_id,
        helper_text=node.helper_text,
    )


@router.post(
    "/assemble-tree",
    response={
        200: AssembledQuestionnaireOut,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    summary="Assemble the versioned questionnaire tree",
    description=(
        "Resolve a publicly listed Game's aesthetics and return the concrete "
        "v1.0.0 question graph (Q3–Q14 plus branch nodes) for that session "
        "(SBGC-173)."
    ),
)
def get_assembled_questionnaire_tree(request, payload: AssembleQuestionnaireIn):
    game = Game.objects.publicly_listable().filter(slug=payload.game_slug).first()
    if game is None:
        raise ApiException(
            404,
            "NOT_FOUND",
            f"Published game '{payload.game_slug}' not found.",
        )

    try:
        resolution = resolve_from_options(payload.q1_option_id, payload.q2_option_id)
        assembled = assemble_questionnaire(resolution)
    except QuestionnaireDomainError as exc:
        raise ApiException(422, "VALIDATION_ERROR", str(exc)) from exc
    except QuestionnaireRegistryError as exc:
        raise ApiException(422, "VALIDATION_ERROR", str(exc)) from exc

    return AssembledQuestionnaireOut(
        version=assembled.version,
        game_slug=game.slug,
        game_name=game.name,
        dominant_aesthetic=assembled.dominant_aesthetic,
        secondary_aesthetic=assembled.secondary_aesthetic,
        is_true_aesthetic=assembled.is_true_aesthetic,
        part1_challenge_nodes=[
            _node_out(node) for node in assembled.part1_challenge_nodes
        ],
        part2_reward_nodes=[_node_out(node) for node in assembled.part2_reward_nodes],
    )
