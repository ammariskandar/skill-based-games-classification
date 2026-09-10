"""
Scoring data contracts — SBGC-174 (Epic SBGC-171).

Immutable value types shared by the scoring accumulator, the ratio
normalizer, and the Q15 compensation engine.  No Django, ORM, cache, or
network imports.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Self


class QualityTier(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
    PERFECT = "PERFECT"


@dataclass(frozen=True)
class DimensionScore:
    """A three-dimensional Challenge or Reward profile (integers)."""

    micro: int
    macro: int
    mystiko: int

    def __post_init__(self) -> None:
        if self.micro < 0 or self.macro < 0 or self.mystiko < 0:
            raise ValueError(f"Negative scores prohibited: {self}")

    @property
    def total(self) -> int:
        return self.micro + self.macro + self.mystiko

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> Self:
        return cls(
            micro=data["micro"],
            macro=data["macro"],
            mystiko=data["mystiko"],
        )


@dataclass(frozen=True)
class QualitySpec:
    """Quality tier plus the permitted per-dimension Q15 adjustment delta."""

    tier: QualityTier
    permitted_delta: int


@dataclass(frozen=True)
class CalculatedProfilePair:
    """Raw, normalized, and adjusted scores for one profile."""

    raw: DimensionScore
    normalized: DimensionScore
    adjusted: DimensionScore


@dataclass(frozen=True)
class FullScoringResult:
    """The complete scoring output for a questionnaire session."""

    challenge: CalculatedProfilePair
    reward: CalculatedProfilePair
    q15_rating: int
    quality_spec: QualitySpec


__all__ = [
    "CalculatedProfilePair",
    "DimensionScore",
    "FullScoringResult",
    "QualitySpec",
    "QualityTier",
]
