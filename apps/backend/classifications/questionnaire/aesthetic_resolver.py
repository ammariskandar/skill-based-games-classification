"""
Aesthetic combinatoric resolver — SBGC-172 (Epic SBGC-171).

Turns the Question 1 and Question 2 categories into a deterministic
:class:`AestheticResolutionResult`:

* **True aesthetics** — identical categories, a ``COLLABORATIVE`` Q1 with a
  standard Q2, or a standard Q1 with a ``COLLABORATIVE``/``NONE`` Q2.  The
  surviving aesthetic routes all of Part 2 (Q9–Q14) to one set.
* **Hybrid aesthetics** — two different standard categories.  The Q1 category
  dominates Part 1 and the Q12–Q14 half of Part 2; the Q2 category supplies
  the Q9–Q11 half (the 50/50 split).
* **Special flow** — ``COLLABORATIVE`` + ``NONE`` has no aesthetic basis and
  is flagged for the reserved special path.

Pure functions only: no Django, ORM, cache, or network access.
"""

from __future__ import annotations

from classifications.questionnaire.domain import (
    OPTION_BY_ID,
    AestheticCategory,
    AestheticResolutionResult,
    InvalidOptionSelectionError,
    Part2SplitConfig,
    QuestionSetId,
    UnknownOptionError,
    UnresolvableAestheticError,
    map_option_to_category,
)

#: Part 1 (Challenge, Q3–Q8) — one set per canonical aesthetic.
PART1_SET_MAP: dict[AestheticCategory, QuestionSetId] = {
    AestheticCategory.SENSORY: QuestionSetId.SET_1A,
    AestheticCategory.FANTASY: QuestionSetId.SET_1B,
    AestheticCategory.NARRATIVE: QuestionSetId.SET_1C,
    AestheticCategory.CHALLENGE: QuestionSetId.SET_1D,
}

#: Part 2 (Reward, Q9–Q14) — one set per canonical aesthetic.
PART2_SET_MAP: dict[AestheticCategory, QuestionSetId] = {
    AestheticCategory.SENSORY: QuestionSetId.SET_2A,
    AestheticCategory.FANTASY: QuestionSetId.SET_2B,
    AestheticCategory.NARRATIVE: QuestionSetId.SET_2C,
    AestheticCategory.CHALLENGE: QuestionSetId.SET_2D,
}

_CANONICAL_AESTHETICS = frozenset(PART1_SET_MAP)


def resolve_aesthetic(
    cat1: AestheticCategory, cat2: AestheticCategory
) -> AestheticResolutionResult:
    """Resolve the Q1/Q2 category pair into its dispatch contract.

    Raises :class:`UnresolvableAestheticError` when the pair cannot occur
    (e.g. ``COLLABORATIVE`` in both questions, or ``NONE`` in Q1).
    """
    # 1. Collaborative + None → reserved special flow.
    if cat1 is AestheticCategory.COLLABORATIVE:
        if cat2 is AestheticCategory.NONE:
            return _special_flow_result()
        # 2. Collaborative Q1 + standard Q2 → true aesthetic of Q2.
        if cat2 in _CANONICAL_AESTHETICS:
            return _build_true_aesthetic_result(cat2)
        raise UnresolvableAestheticError(cat1, cat2)

    if cat1 not in _CANONICAL_AESTHETICS:
        raise UnresolvableAestheticError(cat1, cat2)

    # 3. Standard Q1 + Collaborative / None / identical Q2 → true aesthetic of Q1.
    if cat2 in (AestheticCategory.COLLABORATIVE, AestheticCategory.NONE, cat1):
        return _build_true_aesthetic_result(cat1)

    # 4. Two different standard aesthetics → hybrid 50/50 split.
    if cat2 in _CANONICAL_AESTHETICS:
        return AestheticResolutionResult(
            dominant_aesthetic=cat1,
            secondary_aesthetic=cat2,
            is_true_aesthetic=False,
            part1_challenge_set=PART1_SET_MAP[cat1],
            part2_reward_config=Part2SplitConfig(
                is_split=True,
                q9_to_q11_set=PART2_SET_MAP[cat2],
                q12_to_q14_set=PART2_SET_MAP[cat1],
            ),
        )

    raise UnresolvableAestheticError(cat1, cat2)


def resolve_from_options(
    q1_option_id: str, q2_option_id: str
) -> AestheticResolutionResult:
    """Resolve raw Q1/Q2 option identifiers into their dispatch contract.

    Validates both options against the registry and enforces that the Q2
    selection is available for the given Q1 selection: unknown options,
    ``OPT_NONE`` in Q1, and replaying the Q1 option in Q2 are all rejected.
    """
    cat1 = map_option_to_category(q1_option_id)  # UnknownOptionError if absent
    if cat1 is AestheticCategory.NONE:
        raise InvalidOptionSelectionError(q1_option_id, "Question 1")

    if q2_option_id not in OPTION_BY_ID:
        raise UnknownOptionError(q2_option_id)
    if q2_option_id == q1_option_id:
        raise InvalidOptionSelectionError(q2_option_id, "Question 2")

    cat2 = map_option_to_category(q2_option_id)
    return resolve_aesthetic(cat1, cat2)


def _build_true_aesthetic_result(
    dominant: AestheticCategory,
) -> AestheticResolutionResult:
    """True aesthetic: both Part 2 halves route to the dominant set."""
    part2_set = PART2_SET_MAP[dominant]
    return AestheticResolutionResult(
        dominant_aesthetic=dominant,
        secondary_aesthetic=None,
        is_true_aesthetic=True,
        part1_challenge_set=PART1_SET_MAP[dominant],
        part2_reward_config=Part2SplitConfig(
            is_split=False,
            q9_to_q11_set=part2_set,
            q12_to_q14_set=part2_set,
        ),
    )


def _special_flow_result() -> AestheticResolutionResult:
    """Reserved special-flow outcome for COLLABORATIVE + NONE."""
    return AestheticResolutionResult(
        dominant_aesthetic=AestheticCategory.SPECIAL_FLOW,
        secondary_aesthetic=None,
        is_true_aesthetic=False,
        part1_challenge_set=QuestionSetId.SPECIAL,
        part2_reward_config=Part2SplitConfig(
            is_split=False,
            q9_to_q11_set=QuestionSetId.SPECIAL,
            q12_to_q14_set=QuestionSetId.SPECIAL,
        ),
    )


__all__ = [
    "PART1_SET_MAP",
    "PART2_SET_MAP",
    "resolve_aesthetic",
    "resolve_from_options",
]
