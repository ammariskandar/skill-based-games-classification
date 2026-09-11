"""
Aesthetic consensus, tiebreaker & confidence calibration — SBGC-227.

Aggregates the directed ``(primary, secondary)`` aesthetic votes contributed by
questionnaire submissions into a single canonical aesthetic pair, and calibrates
the Game's overall classification confidence:

* **Uncontested winner** → the modal pair wins, and an *agreement bonus* of +1%
  per full 10 votes of surplus agreement is added (capped at 100%).
* **Top-vote tie** → the winner is chosen at random from the tied leaders and a
  disagreement *penalty* (0 / 1 / 5 / 10) is deducted, floored at 0%.

The disagreement severity is a function of how much the tied pairs share:

| Relationship                              | Penalty |
| ----------------------------------------- | ------- |
| Same primary, different secondary         | 0       |
| Same secondary, different primary         | 1       |
| A component shared in the opposite slot   | 5       |
| No shared component at all                | 10      |

The spec's "inverted order" row is expressed as an XOR (exactly one opposite-slot
match).  We generalise it to *any* opposite-slot match so an exact swap
(``F+S`` vs ``S+F``) is also a partial disagreement rather than falling through
every row; this is a superset of the four listed examples.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from games.models import Aesthetic

CANONICAL_AESTHETICS: tuple[str, ...] = tuple(Aesthetic.values)

PENALTY_PRIMARY_AGREEMENT = 0
PENALTY_SECONDARY_AGREEMENT = 1
PENALTY_OPPOSITE_SLOT = 5
PENALTY_TOTAL_DISAGREEMENT = 10

BONUS_PER_SURPLUS = 1
BONUS_SURPLUS_STEP = 10


@dataclass(frozen=True)
class AestheticPair:
    """A directed primary/secondary aesthetic vote."""

    primary: str
    secondary: str

    @staticmethod
    def parse(value: object) -> AestheticPair | None:
        """Coerce an untrusted value into a valid pair, or ``None``."""
        if isinstance(value, AestheticPair):
            return value
        if isinstance(value, (tuple, list)) and len(value) == 2:
            primary, secondary = value
        elif isinstance(value, dict):
            primary = value.get("primary")
            secondary = value.get("secondary")
        else:
            return None
        if not isinstance(primary, str) or not isinstance(secondary, str):
            return None
        primary = primary.upper()
        secondary = secondary.upper()
        if primary not in CANONICAL_AESTHETICS or secondary not in CANONICAL_AESTHETICS:
            return None
        return AestheticPair(primary, secondary)


@dataclass(frozen=True)
class ConsensusResult:
    """Outcome of aggregating a game's aesthetic votes."""

    primary: str | None
    secondary: str | None
    winner_votes: int
    total_votes: int
    is_tie: bool
    penalty: int
    bonus: int
    confidence: int
    tied_pairs: tuple[AestheticPair, ...]


def disagreement_penalty(a: AestheticPair, b: AestheticPair) -> int:
    """Confidence penalty (percent points) for two tied winning pairs."""
    if a.primary == b.primary and a.secondary == b.secondary:
        return 0
    if a.primary == b.primary:
        return PENALTY_PRIMARY_AGREEMENT
    if a.secondary == b.secondary:
        return PENALTY_SECONDARY_AGREEMENT
    opposite = a.primary == b.secondary or a.secondary == b.primary
    if opposite:
        return PENALTY_OPPOSITE_SLOT
    return PENALTY_TOTAL_DISAGREEMENT


def agreement_bonus(winner_votes: int, total_votes: int) -> int:
    """+1% per full 10 votes of surplus agreement (never negative)."""
    surplus = max(0, winner_votes - (total_votes - winner_votes))
    return (surplus // BONUS_SURPLUS_STEP) * BONUS_PER_SURPLUS


def resolve_aesthetic_consensus(
    votes: Iterable[object],
    base_confidence: float = 100.0,
    rng: random.Random | None = None,
) -> ConsensusResult:
    """Aggregate aesthetic votes and calibrate confidence.

    Unparseable votes are ignored.  With no usable votes the canonical aesthetic
    is left unresolved and the base confidence is returned unchanged.
    """
    parsed = [pair for pair in (AestheticPair.parse(v) for v in votes) if pair]
    base = max(0.0, min(100.0, float(base_confidence)))

    if not parsed:
        return ConsensusResult(
            primary=None,
            secondary=None,
            winner_votes=0,
            total_votes=0,
            is_tie=False,
            penalty=0,
            bonus=0,
            confidence=int(round(base)),
            tied_pairs=(),
        )

    counts = Counter(parsed)
    top = max(counts.values())
    leaders = sorted(
        (pair for pair, count in counts.items() if count == top),
        key=lambda pair: (pair.primary, pair.secondary),
    )
    total = len(parsed)

    if len(leaders) == 1:
        winner = leaders[0]
        bonus = agreement_bonus(top, total)
        confidence = int(round(min(100.0, base + bonus)))
        return ConsensusResult(
            primary=winner.primary,
            secondary=winner.secondary,
            winner_votes=top,
            total_votes=total,
            is_tie=False,
            penalty=0,
            bonus=bonus,
            confidence=confidence,
            tied_pairs=(),
        )

    penalty = max(
        disagreement_penalty(leaders[i], leaders[j])
        for i in range(len(leaders))
        for j in range(i + 1, len(leaders))
    )
    chooser = rng if rng is not None else random
    winner = chooser.choice(leaders)
    confidence = int(round(max(0.0, base - penalty)))
    return ConsensusResult(
        primary=winner.primary,
        secondary=winner.secondary,
        winner_votes=top,
        total_votes=total,
        is_tie=True,
        penalty=penalty,
        bonus=0,
        confidence=confidence,
        tied_pairs=tuple(leaders),
    )


__all__ = [
    "CANONICAL_AESTHETICS",
    "AestheticPair",
    "ConsensusResult",
    "agreement_bonus",
    "disagreement_penalty",
    "resolve_aesthetic_consensus",
]
