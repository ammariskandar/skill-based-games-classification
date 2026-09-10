"""
Questionnaire API schemas — SBGC-176 (Epic SBGC-171).

Request/response contracts for the authenticated session retrieval and
submission-persistence endpoints.  Sum-to-100 validation is enforced at the
schema layer for both the adjusted Challenge and Reward profiles.
"""

from __future__ import annotations

from typing import Literal

from api.schemas import ApiRequestSchema
from ninja import Schema
from pydantic import Field, model_validator


class DimensionScoreSchema(ApiRequestSchema):
    """One three-dimensional profile constrained to sum to exactly 100."""

    micro: int = Field(ge=0, le=100)
    macro: int = Field(ge=0, le=100)
    mystiko: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _validate_sum_100(self) -> DimensionScoreSchema:
        total = self.micro + self.macro + self.mystiko
        if total != 100:
            raise ValueError(f"Dimension scores must sum to 100, got {total}")
        return self


class PrecedenceEvaluationSchema(Schema):
    """Conflict metadata for a user's existing manual submission."""

    has_conflict: bool
    requires_user_choice: bool
    manual_submission_id: int | None = None
    manual_created_at: str | None = None
    age_days: int | None = None


class QuestionnairePreviousResultSchema(Schema):
    """Summary of the user's most recent questionnaire result."""

    result_id: int
    version: str
    dominant_aesthetic: str
    secondary_aesthetic: str | None
    is_true_aesthetic: bool
    q15_rating: int
    adjusted_challenge: DimensionScoreSchema
    adjusted_reward: DimensionScoreSchema
    status: str
    created_at: str


class QuestionnaireSessionOut(Schema):
    """Session initialization payload (conflict status + previous result)."""

    game_slug: str
    game_name: str
    canonical_aesthetic: str | None
    precedence: PrecedenceEvaluationSchema
    previous_result: QuestionnairePreviousResultSchema | None = None


class QuestionnaireSubmitIn(ApiRequestSchema):
    """A completed questionnaire traversal submitted for persistence."""

    version: str = "v1.0.0"
    q1_option_id: str
    q2_option_id: str
    answers: dict[str, str] = Field(
        description="Map of node ID to chosen option ID, e.g. {'Q3': 'OPT_Q3_HUGE'}"
    )
    q15_rating: int = Field(ge=1, le=10)
    adjusted_challenge: DimensionScoreSchema
    adjusted_reward: DimensionScoreSchema
    conflict_resolution: Literal["OVERWRITE", "KEEP_MANUAL"] | None = None


class QuestionnaireSubmitOut(Schema):
    """Outcome of a validated questionnaire submission."""

    success: bool
    questionnaire_result_id: int
    classification_status: str
    is_active_in_calculation: bool
    routed_to_editorial: bool
    message: str
    challenge: DimensionScoreSchema
    reward: DimensionScoreSchema


class ConflictRequiredOut(Schema):
    """HTTP 409 body when a recent manual submission needs a user decision."""

    error: str = "conflict_resolution_required"
    message: str
    precedence: PrecedenceEvaluationSchema


__all__ = [
    "ConflictRequiredOut",
    "DimensionScoreSchema",
    "PrecedenceEvaluationSchema",
    "QuestionnairePreviousResultSchema",
    "QuestionnaireSessionOut",
    "QuestionnaireSubmitIn",
    "QuestionnaireSubmitOut",
]
