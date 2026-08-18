"""
Largest-remainder integer reconciliation — SBGC-65 (Part III / B.16).

Converts a raw profile on the 100-point simplex into non-negative integers
summing exactly to 100.  Tie priority: Micro > Macro > Mystiko.
"""

from __future__ import annotations

import math

from classifications.calculations.constants import TIE_PRIORITY, TIE_TOLERANCE
from classifications.calculations.errors import CalculationInvariantError
from classifications.calculations.profiles import Profile

# Display-order component names: (micro, macro, mystiko).
_COMPONENTS = ("micro", "macro", "mystiko")


def largest_remainder(raw: tuple[float, float, float]) -> tuple[int, int, int]:
    """Reconcile a (micro, macro, mystiko) raw profile to integers summing 100.

    Raises:
        CalculationInvariantError: the residual r is outside {0, 1, 2} or a
            component is non-finite.
    """
    if any(
        (v != v) or v in (float("inf"), float("-inf")) or v < 0 or v > 100 for v in raw
    ):
        raise CalculationInvariantError("raw profile contains an invalid component")

    floors = [math.floor(v) for v in raw]
    residual = 100 - sum(floors)
    if residual not in (0, 1, 2):
        raise CalculationInvariantError(
            f"largest-remainder residual {residual} outside {{0, 1, 2}}"
        )
    if residual == 0:
        return (floors[0], floors[1], floors[2])

    remainders = [v - f for v, f in zip(raw, floors, strict=False)]

    # Award the residual points to the largest fractional remainders.  Two
    # remainders within TIE_TOLERANCE are tied and resolve by the fixed
    # priority Micro (0) > Macro (1) > Mystiko (2) (B.16.4).
    awarded = []
    pending = [0, 1, 2]
    for _ in range(residual):
        best = max(pending, key=lambda j: remainders[j])
        tied = [
            j for j in pending if abs(remainders[j] - remainders[best]) <= TIE_TOLERANCE
        ]
        pick = min(tied, key=lambda j: _TIE_RANK[j])
        awarded.append(pick)
        pending.remove(pick)

    awarded_set = set(awarded)
    return (
        floors[0] + (1 if 0 in awarded_set else 0),
        floors[1] + (1 if 1 in awarded_set else 0),
        floors[2] + (1 if 2 in awarded_set else 0),
    )


def largest_remainder_profile(raw: Profile) -> tuple[int, int, int]:
    """Reconcile a ``Profile`` to integer (micro, macro, mystiko) components."""
    return largest_remainder(raw.components())


_TIE_RANK = {_COMPONENTS.index(name): rank for rank, name in enumerate(TIE_PRIORITY)}


def fractions_tied(a: float, b: float) -> bool:
    """True when two remainders are tied within the frozen tolerance (B.16.4)."""
    return abs(a - b) <= TIE_TOLERANCE


__all__ = ["fractions_tied", "largest_remainder", "largest_remainder_profile"]
