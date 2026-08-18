"""
Shared result value objects — SBGC-65.

Method results carry the continuous (pre-reconciliation) profiles, the
reconciled integer profiles, and diagnostics.  All non-READY results have
null profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from classifications.calculations.profiles import Profile

# Method statuses (Part IV / B.21).
READY = "READY"
NO_SUBMISSIONS = "NO_SUBMISSIONS"
INSUFFICIENT_ANCHOR = "INSUFFICIENT_ANCHOR"
INSUFFICIENT_SAMPLE_FOR_IFOREST = "INSUFFICIENT_SAMPLE_FOR_IFOREST"
INSUFFICIENT_SAMPLE_FOR_LOOP = "INSUFFICIENT_SAMPLE_FOR_LOOP"
NO_SURVIVING_SUBMISSIONS = "NO_SURVIVING_SUBMISSIONS"
CALCULATION_ERROR = "CALCULATION_ERROR"
INSUFFICIENT_METHOD_1 = "INSUFFICIENT_METHOD_1"
INSUFFICIENT_METHOD_2 = "INSUFFICIENT_METHOD_2"
INSUFFICIENT_METHOD_3 = "INSUFFICIENT_METHOD_3"
UNIFIED_CALCULATION_UNSTABLE = "UNIFIED_CALCULATION_UNSTABLE"
UNIFIED_CALCULATION_ERROR = "UNIFIED_CALCULATION_ERROR"

# Confidence statuses.
PROVISIONAL_READY = "PROVISIONAL_READY"
BOUNDARY_CALIBRATION_UNAVAILABLE = "BOUNDARY_CALIBRATION_UNAVAILABLE"

# Regimes.
REGIME_PROVISIONAL = "provisional"
REGIME_UNIFIED = "unified"
REGIME_NONE = "none"

# Final snapshot statuses.
SNAPSHOT_NO_SUBMISSIONS = "NO_SUBMISSIONS"


@dataclass(frozen=True)
class MethodResult:
    """One method's complete output for one population."""

    method: str
    status: str
    raw_challenge: Profile | None = None
    raw_reward: Profile | None = None
    integer_challenge: tuple[int, int, int] | None = None
    integer_reward: tuple[int, int, int] | None = None
    survivors: int | None = None
    rejected: int | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == READY


@dataclass(frozen=True)
class ConfidenceResult:
    """A complete confidence-layer result."""

    version: str
    status: str
    level_raw: float | None = None
    level_displayed: float | None = None
    label: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


def confidence_label(level: float) -> str:
    """Final categorical label (Part D.2)."""
    if level < 40:
        return "Low"
    if level < 65:
        return "Moderate"
    if level < 80:
        return "Substantial"
    if level < 90:
        return "High"
    if level < 97:
        return "Very high"
    return "Exceptional"


__all__ = [
    "BOUNDARY_CALIBRATION_UNAVAILABLE",
    "CALCULATION_ERROR",
    "ConfidenceResult",
    "INSUFFICIENT_ANCHOR",
    "INSUFFICIENT_METHOD_1",
    "INSUFFICIENT_METHOD_2",
    "INSUFFICIENT_METHOD_3",
    "INSUFFICIENT_SAMPLE_FOR_IFOREST",
    "INSUFFICIENT_SAMPLE_FOR_LOOP",
    "MethodResult",
    "NO_SUBMISSIONS",
    "NO_SURVIVING_SUBMISSIONS",
    "PROVISIONAL_READY",
    "READY",
    "REGIME_NONE",
    "REGIME_PROVISIONAL",
    "REGIME_UNIFIED",
    "SNAPSHOT_NO_SUBMISSIONS",
    "UNIFIED_CALCULATION_ERROR",
    "UNIFIED_CALCULATION_UNSTABLE",
    "confidence_label",
]
