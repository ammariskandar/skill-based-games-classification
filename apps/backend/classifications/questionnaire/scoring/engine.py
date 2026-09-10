"""
Scoring accumulator & ratio normalizer — SBGC-174 (Epic SBGC-171).

Pure functions:

* :func:`compute_raw_profile` — accumulates per-step-floored dimension scores
  from answered option modifiers (a negative modifier never creates a negative
  running balance; later positives build up from 0).
* :func:`normalize_profile` — ratio-normalizes a raw profile to a 100-point
  integer distribution using the Largest Remainder method with a fixed
  tie-break order (Micro ≻ Macro ≻ Mystiko) and a zero-total fallback of
  ``(33, 33, 34)``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from classifications.questionnaire.registry.v1.types import (
    AnswerOption,
    ProfileTarget,
    QuestionNode,
)
from classifications.questionnaire.scoring.types import DimensionScore

#: Static dimension tie-break priority (Micro ≻ Macro ≻ Mystiko).
_DIMENSION_PRIORITY = ("micro", "macro", "mystiko")


def compute_raw_profile(
    answers: dict[str, str],
    nodes: Sequence[QuestionNode],
    target: ProfileTarget,
) -> DimensionScore:
    """Accumulate *answers* into a raw profile with per-step zero-flooring.

    *answers* maps a question node id to its selected option id.  Questions
    whose ``target`` differs from *target* are ignored, and unknown
    question/option ids are skipped (the submission validator owns hard
    rejection — SBGC-176).
    """
    micro = 0
    macro = 0
    mystiko = 0

    node_map = {node.id: node for node in nodes if node.target is target}

    for question_id, option_id in answers.items():
        node = node_map.get(question_id)
        if node is None:
            continue
        option: AnswerOption | None = next(
            (candidate for candidate in node.options if candidate.id == option_id),
            None,
        )
        if option is None:
            continue

        micro = max(0, micro + option.modifiers.micro)
        macro = max(0, macro + option.modifiers.macro)
        mystiko = max(0, mystiko + option.modifiers.mystiko)

    return DimensionScore(micro=micro, macro=macro, mystiko=mystiko)


def normalize_profile(raw: DimensionScore) -> DimensionScore:
    """Normalize *raw* to a 100-point integer distribution (Hamilton–Hare)."""
    total = raw.total
    if total == 0:
        return DimensionScore(micro=33, macro=33, mystiko=34)

    raw_values = {
        "micro": raw.micro,
        "macro": raw.macro,
        "mystiko": raw.mystiko,
    }
    exact = {
        dimension: (value / total) * 100.0 for dimension, value in raw_values.items()
    }
    floors = {
        dimension: math.floor(exact[dimension]) for dimension in _DIMENSION_PRIORITY
    }

    remainder = 100 - sum(floors.values())

    # Sort by: fractional remainder (desc), then raw magnitude (desc), then the
    # static dimension priority.  ``priority`` is a negative index so a higher
    # priority dimension sorts earlier under ``reverse=True``.
    fractions = [
        (
            exact[dimension] - floors[dimension],
            raw_values[dimension],
            -index,
            dimension,
        )
        for index, dimension in enumerate(_DIMENSION_PRIORITY)
    ]
    fractions.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

    allocations = dict(floors)
    for index in range(remainder):
        allocations[fractions[index][3]] += 1

    return DimensionScore(
        micro=allocations["micro"],
        macro=allocations["macro"],
        mystiko=allocations["mystiko"],
    )


__all__ = ["compute_raw_profile", "normalize_profile"]
