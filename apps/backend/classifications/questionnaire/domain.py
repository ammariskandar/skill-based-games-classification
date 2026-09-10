"""
Questionnaire domain vocabulary — SBGC-172 (Epic SBGC-171).

ORM-free vocabulary for the score-generation questionnaire:

* :class:`AestheticCategory` — the four true aesthetics plus the
  ``COLLABORATIVE`` and ``NONE`` sentinels and the ``SPECIAL_FLOW`` outcome.
* :class:`QuestionSetId` — the immutable Part 1 (Challenge) and Part 2
  (Reward) question-set identifiers.
* The Q1/Q2 option registry mapping every answer option to its aesthetic.
* :class:`Part2SplitConfig` / :class:`AestheticResolutionResult` — the
  question-set dispatch contract consumed by the question registry
  (SBGC-173) and the live radar engine (SBGC-174 / SBGC-179).

No Django, ORM, or network imports — this module is pure vocabulary and is
mirrored one-to-one by the TypeScript taxonomy
(``apps/frontend/src/lib/questionnaire/``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AestheticCategory(StrEnum):
    """Reason-for-fun taxonomy produced by Questions 1 and 2."""

    SENSORY = "SENSORY"
    FANTASY = "FANTASY"
    NARRATIVE = "NARRATIVE"
    CHALLENGE = "CHALLENGE"
    COLLABORATIVE = "COLLABORATIVE"
    NONE = "NONE"
    SPECIAL_FLOW = "SPECIAL_FLOW"


class QuestionSetId(StrEnum):
    """Immutable questionnaire set identifiers (Part 1 Challenge / Part 2 Reward)."""

    SET_1A = "1A"
    SET_1B = "1B"
    SET_1C = "1C"
    SET_1D = "1D"
    SET_2A = "2A"
    SET_2B = "2B"
    SET_2C = "2C"
    SET_2D = "2D"
    SPECIAL = "SPECIAL"


@dataclass(frozen=True)
class AestheticOption:
    """One Q1/Q2 answer option and its deterministic aesthetic category."""

    option_id: str
    label: str
    category: AestheticCategory


@dataclass(frozen=True)
class Part2SplitConfig:
    """Reward (Part 2) question-set routing for Q9–Q14."""

    is_split: bool
    q9_to_q11_set: QuestionSetId
    q12_to_q14_set: QuestionSetId


@dataclass(frozen=True)
class AestheticResolutionResult:
    """Resolved aesthetic plus the Part 1/Part 2 dispatch contract."""

    dominant_aesthetic: AestheticCategory
    secondary_aesthetic: AestheticCategory | None
    is_true_aesthetic: bool
    part1_challenge_set: QuestionSetId
    part2_reward_config: Part2SplitConfig


class QuestionnaireDomainError(ValueError):
    """Base class for questionnaire domain-rule violations."""


class UnknownOptionError(QuestionnaireDomainError):
    """An option identifier is not part of the Q1/Q2 registry."""

    def __init__(self, option_id: str) -> None:
        self.option_id = option_id
        super().__init__(f"Unknown questionnaire option '{option_id}'.")


class InvalidOptionSelectionError(QuestionnaireDomainError):
    """A structurally valid option is not selectable in the given question."""

    def __init__(self, option_id: str, question: str) -> None:
        self.option_id = option_id
        self.question = question
        super().__init__(f"Option '{option_id}' cannot be selected for {question}.")


class UnresolvableAestheticError(QuestionnaireDomainError):
    """The category pair does not map onto the resolution matrix."""

    def __init__(self, cat1: AestheticCategory, cat2: AestheticCategory) -> None:
        super().__init__(f"No aesthetic resolution exists for '{cat1}' + '{cat2}'.")


# ---------------------------------------------------------------------------
# Q1 / Q2 option registry
# ---------------------------------------------------------------------------

# Question 1 — "primary reason for fun".  ``OPT_NONE`` is intentionally
# excluded: it is only offered in Question 2.
PRIMARY_OPTIONS: tuple[AestheticOption, ...] = (
    AestheticOption("OPT_S1", "The music is good", AestheticCategory.SENSORY),
    AestheticOption(
        "OPT_S2",
        "The graphics and/or art is beautiful",
        AestheticCategory.SENSORY,
    ),
    AestheticOption(
        "OPT_S3",
        "It gets my blood pumping from the action",
        AestheticCategory.SENSORY,
    ),
    AestheticOption(
        "OPT_S4", "It provides a thrilling scare", AestheticCategory.SENSORY
    ),
    AestheticOption("OPT_S5", "It is sexually gratifying", AestheticCategory.SENSORY),
    AestheticOption("OPT_S6", "It is therapeutic", AestheticCategory.SENSORY),
    AestheticOption(
        "OPT_F1",
        "I get to turn things I envision into a reality",
        AestheticCategory.FANTASY,
    ),
    AestheticOption(
        "OPT_F2",
        "I get to live a life I normally would not be able to",
        AestheticCategory.FANTASY,
    ),
    AestheticOption(
        "OPT_F3",
        "I get to experience new things or places",
        AestheticCategory.FANTASY,
    ),
    AestheticOption(
        "OPT_F4",
        "I get to improve on mistakes others have made in the past",
        AestheticCategory.FANTASY,
    ),
    AestheticOption(
        "OPT_N1", "It has a very compelling story", AestheticCategory.NARRATIVE
    ),
    AestheticOption(
        "OPT_N2",
        "I really enjoy the character development",
        AestheticCategory.NARRATIVE,
    ),
    AestheticOption(
        "OPT_C1",
        "It's difficult, and that alone makes it fun",
        AestheticCategory.CHALLENGE,
    ),
    AestheticOption(
        "OPT_C2",
        "I feel like I am much better than everyone in this game",
        AestheticCategory.CHALLENGE,
    ),
    AestheticOption(
        "OPT_C3",
        "It is incredibly rewarding to see my strategies pay off",
        AestheticCategory.CHALLENGE,
    ),
    AestheticOption(
        "OPT_C4",
        "It's fun beating my own or other people's records",
        AestheticCategory.CHALLENGE,
    ),
    AestheticOption(
        "OPT_COL",
        "It's just fun playing/competing with friends",
        AestheticCategory.COLLABORATIVE,
    ),
)

NONE_OPTION = AestheticOption("OPT_NONE", "None of the above.", AestheticCategory.NONE)

# Question 2 offers every Q1 option except the Q1 selection, plus OPT_NONE.
SECONDARY_OPTION_POOL: tuple[AestheticOption, ...] = (*PRIMARY_OPTIONS, NONE_OPTION)

OPTION_BY_ID: dict[str, AestheticOption] = {
    option.option_id: option for option in SECONDARY_OPTION_POOL
}


def map_option_to_category(option_id: str) -> AestheticCategory:
    """Return the aesthetic category for *option_id*.

    Raises :class:`UnknownOptionError` for identifiers outside the registry.
    """
    try:
        return OPTION_BY_ID[option_id].category
    except KeyError:
        raise UnknownOptionError(option_id) from None


def available_secondary_options(q1_option_id: str) -> tuple[AestheticOption, ...]:
    """Return the Question 2 option set for a given Question 1 selection.

    Q2 excludes the exact option selected in Q1 and always appends
    ``OPT_NONE``.  ``OPT_NONE`` itself is not a valid Q1 selection.
    """
    primary = OPTION_BY_ID.get(q1_option_id)
    if primary is None:
        raise UnknownOptionError(q1_option_id)
    if primary.category is AestheticCategory.NONE:
        raise InvalidOptionSelectionError(q1_option_id, "Question 1")
    return (
        *(o for o in PRIMARY_OPTIONS if o.option_id != q1_option_id),
        NONE_OPTION,
    )


__all__ = [
    "AestheticCategory",
    "AestheticOption",
    "AestheticResolutionResult",
    "InvalidOptionSelectionError",
    "NONE_OPTION",
    "OPTION_BY_ID",
    "PRIMARY_OPTIONS",
    "Part2SplitConfig",
    "QuestionSetId",
    "QuestionnaireDomainError",
    "SECONDARY_OPTION_POOL",
    "UnknownOptionError",
    "UnresolvableAestheticError",
    "available_secondary_options",
    "map_option_to_category",
]
