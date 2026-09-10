"""
Questionnaire API router — SBGC-172 / SBGC-173 / SBGC-176 (Epic SBGC-171).

* ``POST /api/v1/questionnaire/resolve-aesthetic`` — resolve a Game's
  dominant/secondary aesthetics from its Q1/Q2 answers.
* ``POST /api/v1/questionnaire/assemble-tree`` — return the concrete versioned
  question graph (Q3–Q14 plus branches) for that resolution.
* ``GET /api/v1/questionnaire/{slug}/session`` — authenticated conflict status
  and the user's previous questionnaire result.
* ``POST /api/v1/questionnaire/{slug}/submit`` — authoritative re-computation
  and persistence through the SBGC-175 precedence engine.

The resolve/assemble endpoints are pure and stateless; the session/submit
endpoints are the authenticated persistence boundary (SBGC-175 / SBGC-176).
"""

from __future__ import annotations

from api.errors import STANDARD_ERROR_RESPONSES, ApiException
from api.schemas import ApiErrorResponse
from games.models import Game
from ninja import Router, Schema

from classifications.models import QuestionnaireClassification, QuestionnaireResult
from classifications.questionnaire.aesthetic_resolver import resolve_from_options
from classifications.questionnaire.domain import QuestionnaireDomainError
from classifications.questionnaire.registry.v1.assembler import (
    QuestionnaireRegistryError,
    assemble_questionnaire,
)
from classifications.questionnaire.registry.v1.types import (
    AnswerOption,
    ProfileTarget,
    QuestionNode,
    ScoreModifier,
)
from classifications.questionnaire.schemas import (
    ConflictRequiredOut,
    DimensionScoreSchema,
    PrecedenceEvaluationSchema,
    QuestionnairePreviousResultSchema,
    QuestionnaireSessionOut,
    QuestionnaireSubmitIn,
    QuestionnaireSubmitOut,
)
from classifications.questionnaire.scoring.compensation import resolve_quality_spec
from classifications.questionnaire.scoring.engine import (
    compute_raw_profile,
    normalize_profile,
)
from classifications.services.questionnaire_precedence import (
    evaluate_manual_conflict,
    ingest_questionnaire_submission,
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


# ---------------------------------------------------------------------------
# Authenticated session retrieval & submission — SBGC-176
# ---------------------------------------------------------------------------


def _precedence_schema(precedence) -> PrecedenceEvaluationSchema:
    return PrecedenceEvaluationSchema(
        has_conflict=precedence.has_conflict,
        requires_user_choice=precedence.requires_user_choice,
        manual_submission_id=precedence.manual_submission_id,
        manual_created_at=precedence.manual_created_at,
        age_days=precedence.age_days,
    )


@router.get(
    "/{slug}/session",
    response={200: QuestionnaireSessionOut, **STANDARD_ERROR_RESPONSES},
    summary="Retrieve questionnaire session, conflict status, and previous results",
)
def get_questionnaire_session(request, slug: str):
    if not request.user.is_authenticated:
        raise ApiException(
            401,
            "AUTHENTICATION_ERROR",
            "You must be logged in to access questionnaire sessions.",
        )

    game = Game.objects.publicly_listable().filter(slug=slug).first()
    if game is None:
        raise ApiException(404, "NOT_FOUND", f"Published game '{slug}' not found.")

    precedence = evaluate_manual_conflict(request.user, game)

    previous: QuestionnairePreviousResultSchema | None = None
    classification = (
        QuestionnaireClassification.objects.filter(user=request.user, game=game)
        .select_related("latest_result")
        .first()
    )
    if classification is not None:
        result: QuestionnaireResult = classification.latest_result
        previous = QuestionnairePreviousResultSchema(
            result_id=result.pk,
            version=result.version,
            dominant_aesthetic=result.dominant_aesthetic,
            secondary_aesthetic=result.secondary_aesthetic,
            is_true_aesthetic=result.is_true_aesthetic,
            q15_rating=result.q15_rating,
            adjusted_challenge=DimensionScoreSchema(
                micro=result.adjusted_challenge_micro,
                macro=result.adjusted_challenge_macro,
                mystiko=result.adjusted_challenge_mystiko,
            ),
            adjusted_reward=DimensionScoreSchema(
                micro=result.adjusted_reward_micro,
                macro=result.adjusted_reward_macro,
                mystiko=result.adjusted_reward_mystiko,
            ),
            status=classification.status,
            created_at=result.created_at.isoformat(),
        )

    return 200, QuestionnaireSessionOut(
        game_slug=game.slug,
        game_name=game.name,
        canonical_aesthetic=game.aesthetic,
        precedence=_precedence_schema(precedence),
        previous_result=previous,
    )


@router.post(
    "/{slug}/submit",
    response={
        200: QuestionnaireSubmitOut,
        201: QuestionnaireSubmitOut,
        409: ConflictRequiredOut,
        # Explicit concrete statuses rather than Ninja's ``codes_4xx`` group, so
        # the 409 conflict contract is not shadowed by the standard envelope
        # (``codes_4xx`` contains 409).
        400: ApiErrorResponse,
        401: ApiErrorResponse,
        403: ApiErrorResponse,
        404: ApiErrorResponse,
        422: ApiErrorResponse,
    },
    summary="Validate and persist completed questionnaire traversal",
)
def submit_questionnaire(request, slug: str, payload: QuestionnaireSubmitIn):
    if not request.user.is_authenticated:
        raise ApiException(
            401,
            "AUTHENTICATION_ERROR",
            "You must be logged in to submit a questionnaire.",
        )

    game = Game.objects.publicly_listable().filter(slug=slug).first()
    if game is None:
        raise ApiException(404, "NOT_FOUND", f"Published game '{slug}' not found.")

    # 1. Resolve the aesthetic and assemble the active registry tree.
    try:
        resolution = resolve_from_options(payload.q1_option_id, payload.q2_option_id)
        assembled = assemble_questionnaire(resolution)
    except QuestionnaireDomainError as exc:
        raise ApiException(422, "VALIDATION_ERROR", str(exc)) from exc
    except QuestionnaireRegistryError as exc:
        raise ApiException(422, "VALIDATION_ERROR", str(exc)) from exc

    # 2. Traversal integrity: every answer must belong to the tree with a
    #    valid option.  (Client raw/normalized values are never trusted.)
    all_nodes = (*assembled.part1_challenge_nodes, *assembled.part2_reward_nodes)
    node_map = {node.id: node for node in all_nodes}
    for question_id, option_id in payload.answers.items():
        node = node_map.get(question_id)
        if node is None:
            raise ApiException(
                422,
                "VALIDATION_ERROR",
                f"Question node '{question_id}' does not belong to the assembled tree.",
            )
        if not any(option.id == option_id for option in node.options):
            raise ApiException(
                422,
                "VALIDATION_ERROR",
                f"Option '{option_id}' is not valid for question '{question_id}'.",
            )

    # 3. Authoritative re-computation of raw and normalized profiles.
    raw_challenge = compute_raw_profile(
        payload.answers, assembled.part1_challenge_nodes, ProfileTarget.CHALLENGE
    )
    normalized_challenge = normalize_profile(raw_challenge)
    raw_reward = compute_raw_profile(
        payload.answers, assembled.part2_reward_nodes, ProfileTarget.REWARD
    )
    normalized_reward = normalize_profile(raw_reward)

    # 4. Q15 quality-tier delta bounds.
    quality_spec = resolve_quality_spec(payload.q15_rating)
    for dimension in ("micro", "macro", "mystiko"):
        _assert_within_quality_delta(
            profile="Challenge",
            adjusted=getattr(payload.adjusted_challenge, dimension),
            normalized=getattr(normalized_challenge, dimension),
            permitted=quality_spec.permitted_delta,
            rating=payload.q15_rating,
        )
        _assert_within_quality_delta(
            profile="Reward",
            adjusted=getattr(payload.adjusted_reward, dimension),
            normalized=getattr(normalized_reward, dimension),
            permitted=quality_spec.permitted_delta,
            rating=payload.q15_rating,
        )

    # 5. Precedence conflict gate (no records written on 409).
    conflict = evaluate_manual_conflict(request.user, game)
    if conflict.requires_user_choice and payload.conflict_resolution is None:
        return 409, ConflictRequiredOut(
            message=(
                "A recent manual submission exists. Please choose whether to "
                "overwrite it or keep it."
            ),
            precedence=_precedence_schema(conflict),
        )

    # 6. Atomic persistence through the precedence engine.
    scoring_dict = {
        "version": payload.version,
        "dominant_aesthetic": assembled.dominant_aesthetic,
        "secondary_aesthetic": assembled.secondary_aesthetic,
        "is_true_aesthetic": assembled.is_true_aesthetic,
        "answers": payload.answers,
        "q15_rating": payload.q15_rating,
        "raw": {
            "challenge": raw_challenge.to_dict(),
            "reward": raw_reward.to_dict(),
        },
        "normalized": {
            "challenge": normalized_challenge.to_dict(),
            "reward": normalized_reward.to_dict(),
        },
        "adjusted": {
            "challenge": payload.adjusted_challenge.model_dump(),
            "reward": payload.adjusted_reward.model_dump(),
        },
    }
    outcome = ingest_questionnaire_submission(
        user=request.user,
        game=game,
        scoring_result=scoring_dict,
        conflict_resolution=payload.conflict_resolution,
    )

    status_code = 200 if payload.conflict_resolution == "OVERWRITE" else 201
    return status_code, QuestionnaireSubmitOut(
        success=True,
        questionnaire_result_id=outcome.questionnaire_result_id,
        classification_status=outcome.classification_status,
        is_active_in_calculation=outcome.is_active_in_calculation,
        routed_to_editorial=outcome.routed_to_editorial,
        message=outcome.message,
        challenge=payload.adjusted_challenge,
        reward=payload.adjusted_reward,
    )


def _assert_within_quality_delta(
    *,
    profile: str,
    adjusted: int,
    normalized: int,
    permitted: int,
    rating: int,
) -> None:
    if abs(adjusted - normalized) > permitted:
        raise ApiException(
            422,
            "VALIDATION_ERROR",
            (
                f"Adjusted {profile} score ({adjusted}) deviates from the "
                f"normalized score ({normalized}) by more than the permitted "
                f"delta ±{permitted} for rating {rating}."
            ),
        )
