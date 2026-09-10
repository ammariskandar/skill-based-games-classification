"""
Questionnaire registry v1.0.0 — SBGC-173.

Public surface for the versioned registry: the four aesthetic sets, the
hybrid assembler, and the universal schema.
"""

from __future__ import annotations

from classifications.questionnaire.registry.v1.assembler import (
    DOMINANT_PART2_ROOTS,
    REGISTRY_MAP,
    SECONDARY_PART2_ROOTS,
    QuestionnaireRegistryError,
    assemble_questionnaire,
)
from classifications.questionnaire.registry.v1.set_a import SET_A
from classifications.questionnaire.registry.v1.set_b import SET_B
from classifications.questionnaire.registry.v1.set_c import SET_C
from classifications.questionnaire.registry.v1.set_d import SET_D
from classifications.questionnaire.registry.v1.types import (
    REGISTRY_VERSION,
    AnswerOption,
    AssembledQuestionnaire,
    Dimension,
    ProfileTarget,
    QuestionNode,
    QuestionRegistryError,
    QuestionSetDefinition,
    ScoreModifier,
    build_set,
    opt,
    question,
    validate_question_set,
)

__all__ = [
    "DOMINANT_PART2_ROOTS",
    "REGISTRY_MAP",
    "REGISTRY_VERSION",
    "SECONDARY_PART2_ROOTS",
    "SET_A",
    "SET_B",
    "SET_C",
    "SET_D",
    "AnswerOption",
    "AssembledQuestionnaire",
    "Dimension",
    "ProfileTarget",
    "QuestionNode",
    "QuestionRegistryError",
    "QuestionSetDefinition",
    "QuestionnaireRegistryError",
    "ScoreModifier",
    "assemble_questionnaire",
    "build_set",
    "opt",
    "question",
    "validate_question_set",
]
