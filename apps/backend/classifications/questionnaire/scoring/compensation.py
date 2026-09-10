"""
Q15 coupled proportional compensation — SBGC-174 (Epic SBGC-171).

Applies a quality-bounded slider adjustment to one dimension and redistributes
the negation of that delta proportionally across the other two dimensions,
preserving a strict 100-point total and keeping every dimension within
``[0, 100]``.

Pure functions only — no Django, ORM, cache, or network access.
"""

from __future__ import annotations

import math

from classifications.questionnaire.scoring.types import (
    DimensionScore,
    QualitySpec,
    QualityTier,
)

#: (low, high) inclusive rating band → quality spec.
QUALITY_TIER_MAP: dict[tuple[int, int], QualitySpec] = {
    (1, 3): QualitySpec(QualityTier.LOW, 90),
    (4, 5): QualitySpec(QualityTier.MODERATE, 30),
    (6, 7): QualitySpec(QualityTier.HIGH, 10),
    (8, 9): QualitySpec(QualityTier.VERY_HIGH, 5),
    (10, 10): QualitySpec(QualityTier.PERFECT, 1),
}

_DIMENSIONS = ("micro", "macro", "mystiko")


def resolve_quality_spec(rating: int) -> QualitySpec:
    """Return the quality tier/spec for a Q15 rating in ``[1, 10]``."""
    if not 1 <= rating <= 10:
        raise ValueError(f"Q15 rating must be between 1 and 10, got {rating}")
    for (low, high), spec in QUALITY_TIER_MAP.items():
        if low <= rating <= high:
            return spec
    raise ValueError(f"Unhandled rating: {rating}")


def apply_proportional_compensation(
    normalized: DimensionScore,
    active_dimension: str,
    target_value: int,
    rating: int,
) -> DimensionScore:
    """Apply a coupled, quality-bounded slider adjustment to one dimension."""
    if active_dimension not in _DIMENSIONS:
        raise ValueError(f"Unknown dimension '{active_dimension}'.")

    spec = resolve_quality_spec(rating)
    current_value = getattr(normalized, active_dimension)

    # 1. Clamp the target into the permitted quality window around the base.
    min_allowed = max(0, current_value - spec.permitted_delta)
    max_allowed = min(100, current_value + spec.permitted_delta)
    x_new = max(min_allowed, min(max_allowed, target_value))

    delta_x = x_new - current_value
    if delta_x == 0:
        return normalized

    companion_keys = [
        dimension for dimension in _DIMENSIONS if dimension != active_dimension
    ]
    y_key, z_key = companion_keys[0], companion_keys[1]
    y_base = getattr(normalized, y_key)
    z_base = getattr(normalized, z_key)

    delta_budget = -delta_x

    # 2. Pass 1 — unconstrained proportional allocation (equal split on 0/0).
    yz_sum = y_base + z_base
    if yz_sum == 0:
        delta_y = delta_budget / 2.0
        delta_z = delta_budget / 2.0
    else:
        delta_y = delta_budget * (y_base / yz_sum)
        delta_z = delta_budget * (z_base / yz_sum)

    y_candidate = y_base + delta_y
    z_candidate = z_base + delta_z

    # 3. Pass 2 — boundary overflow absorption (defensive: the x_new clamp
    #    already guarantees companions stay within [0, 100], but keep the
    #    containment guard so any future range widening stays safe).
    if y_candidate < 0.0:
        excess = 0.0 - y_candidate
        y_candidate = 0.0
        z_candidate -= excess
    elif y_candidate > 100.0:
        excess = y_candidate - 100.0
        y_candidate = 100.0
        z_candidate += excess

    if z_candidate < 0.0:
        excess = 0.0 - z_candidate
        z_candidate = 0.0
        y_candidate -= excess
    elif z_candidate > 100.0:
        excess = z_candidate - 100.0
        z_candidate = 100.0
        y_candidate += excess

    # 4. Pass 3 — integer discretization & remainder absorption.  The residual
    #    is always in {0, 1}: floor(y+z) can drop at most 1 below 100 - x_new.
    y_floor = math.floor(y_candidate)
    z_floor = math.floor(z_candidate)
    residual = 100 - (x_new + y_floor + z_floor)

    y_remainder = y_candidate - y_floor
    z_remainder = z_candidate - z_floor

    if residual > 0:
        if (y_remainder >= z_remainder and y_floor + 1 <= 100) or z_floor + 1 > 100:
            y_floor += residual
        else:
            z_floor += residual
    elif residual < 0:
        if (y_remainder <= z_remainder and y_floor - 1 >= 0) or z_floor - 1 < 0:
            y_floor += residual
        else:
            z_floor += residual

    result = {active_dimension: x_new, y_key: y_floor, z_key: z_floor}
    return DimensionScore.from_dict(result)


__all__ = [
    "QUALITY_TIER_MAP",
    "apply_proportional_compensation",
    "resolve_quality_spec",
]
