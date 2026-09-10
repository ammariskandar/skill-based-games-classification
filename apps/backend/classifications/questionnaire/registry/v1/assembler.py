"""
Hybrid question assembler (v1.0.0) — SBGC-173.

Turns an :class:`AestheticResolutionResult` into the concrete question graph
for one session:

* Part 1 (Challenge) is always the dominant set's Q3–Q8 plus branches.
* Part 2 (Reward) is the dominant set's Q9–Q14 plus branches for a true
  aesthetic, or a 50/50 split — Q9–Q11 from the secondary set, Q12–Q14 from
  the dominant set — for a hybrid aesthetic.

Child branch nodes never separate from their root, and every set is
structurally validated at import time (see
:func:`classifications.questionnaire.registry.v1.types.build_set`).

Pure functions only: no Django, ORM, cache, or network access.
"""

from __future__ import annotations

from classifications.questionnaire.domain import (
    AestheticCategory,
    AestheticResolutionResult,
)
from classifications.questionnaire.registry.v1.set_a import SET_A
from classifications.questionnaire.registry.v1.set_b import SET_B
from classifications.questionnaire.registry.v1.set_c import SET_C
from classifications.questionnaire.registry.v1.set_d import SET_D
from classifications.questionnaire.registry.v1.types import (
    REGISTRY_VERSION,
    AssembledQuestionnaire,
    QuestionNode,
    QuestionSetDefinition,
)

REGISTRY_MAP: dict[AestheticCategory, QuestionSetDefinition] = {
    AestheticCategory.SENSORY: SET_A,
    AestheticCategory.FANTASY: SET_B,
    AestheticCategory.NARRATIVE: SET_C,
    AestheticCategory.CHALLENGE: SET_D,
}

#: Reward roots routed from the secondary set in a hybrid split.
SECONDARY_PART2_ROOTS = frozenset({"Q9", "Q10", "Q11"})

#: Reward roots routed from the dominant set in a hybrid split.
DOMINANT_PART2_ROOTS = frozenset({"Q12", "Q13", "Q14"})


class QuestionnaireRegistryError(ValueError):
    """Raised when a resolution cannot be assembled from the registry."""


def assemble_questionnaire(
    resolution: AestheticResolutionResult,
) -> AssembledQuestionnaire:
    """Assemble the question graph for *resolution*."""
    dominant_cat = resolution.dominant_aesthetic
    secondary_cat = resolution.secondary_aesthetic

    dominant_def = REGISTRY_MAP.get(dominant_cat)
    if dominant_def is None:
        raise QuestionnaireRegistryError(
            f"Cannot assemble questionnaire for dominant aesthetic {dominant_cat}."
        )

    # Part 1 (Challenge) is always 100% the dominant set.
    part1_nodes = dominant_def.part1_questions

    if resolution.is_true_aesthetic or secondary_cat is None:
        # True aesthetic — the dominant set owns the whole of Part 2.
        part2_nodes = dominant_def.part2_questions
    else:
        secondary_def = REGISTRY_MAP.get(secondary_cat)
        if secondary_def is None:
            raise QuestionnaireRegistryError(
                "Cannot assemble hybrid questionnaire with secondary "
                f"aesthetic {secondary_cat}."
            )
        q9_to_q11 = _nodes_for_roots(
            secondary_def.part2_questions, SECONDARY_PART2_ROOTS
        )
        q12_to_q14 = _nodes_for_roots(
            dominant_def.part2_questions, DOMINANT_PART2_ROOTS
        )
        part2_nodes = (*q9_to_q11, *q12_to_q14)

    return AssembledQuestionnaire(
        version=REGISTRY_VERSION,
        dominant_aesthetic=dominant_cat.value,
        secondary_aesthetic=secondary_cat.value if secondary_cat is not None else None,
        is_true_aesthetic=resolution.is_true_aesthetic,
        part1_challenge_nodes=part1_nodes,
        part2_reward_nodes=part2_nodes,
    )


def _nodes_for_roots(
    nodes: tuple[QuestionNode, ...], roots: frozenset[str]
) -> tuple[QuestionNode, ...]:
    """Return every node whose ``root_id`` is in *roots*, preserving order."""
    return tuple(node for node in nodes if node.root_id in roots)


__all__ = [
    "DOMINANT_PART2_ROOTS",
    "REGISTRY_MAP",
    "SECONDARY_PART2_ROOTS",
    "QuestionnaireRegistryError",
    "assemble_questionnaire",
]
