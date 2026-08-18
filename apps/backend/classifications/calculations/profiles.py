"""
Profile and population-snapshot primitives — SBGC-65.

Profiles are stored in the canonical display order (Micro, Macro, Mystiko).
The six marginal analysis dimensions use the frozen analysis order
(C_micro, C_mystiko, C_macro, R_micro, R_mystiko, R_macro).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from classifications.calculations.constants import PROFILE_ANALYSIS_ORDER
from classifications.calculations.errors import CalculationInvariantError


@dataclass(frozen=True)
class Profile:
    """A three-component profile on the 100-point simplex (percent units)."""

    micro: float
    macro: float
    mystiko: float

    def components(self) -> tuple[float, float, float]:
        """Return (micro, macro, mystiko) in canonical display order."""
        return (self.micro, self.macro, self.mystiko)

    def total(self) -> float:
        return self.micro + self.macro + self.mystiko


@dataclass(frozen=True)
class SubmissionRecord:
    """One valid submission snapshot with its immutable role snapshot."""

    identifier: str
    challenge: Profile
    reward: Profile
    role: str

    def component(self, profile: str, dimension: str) -> float:
        source = self.challenge if profile == "challenge" else self.reward
        return getattr(source, dimension)


@dataclass(frozen=True)
class PopulationSnapshot:
    """A canonically ordered, validated input population.

    ``raw_n`` is the count of valid submissions before any statistical
    rejection.  ``submissions`` is sorted by ascending stable identifier
    so row/retrieval order can never act as an unrecorded mathematical input.
    """

    submissions: tuple[SubmissionRecord, ...]
    population_hash: str = field(default="")

    @property
    def raw_n(self) -> int:
        return len(self.submissions)

    def role_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for submission in self.submissions:
            counts[submission.role] = counts.get(submission.role, 0) + 1
        return counts

    def resample_indices(self, indices: list[int]) -> PopulationSnapshot:
        """Build a bootstrap resample from submission indices (with replacement)."""
        return PopulationSnapshot(
            submissions=tuple(self.submissions[i] for i in indices)
        )


def canonical_population_hash(submissions: list[SubmissionRecord]) -> str:
    """SHA-256 of the canonical input-population serialization."""
    digest = hashlib.sha256()
    for submission in sorted(submissions, key=lambda s: s.identifier):
        parts = [
            submission.identifier,
            repr(submission.challenge.micro),
            repr(submission.challenge.macro),
            repr(submission.challenge.mystiko),
            repr(submission.reward.micro),
            repr(submission.reward.macro),
            repr(submission.reward.mystiko),
            submission.role,
        ]
        digest.update(("|".join(parts) + "\n").encode("utf-8"))
    return digest.hexdigest()


def build_population_snapshot(
    submissions: list[SubmissionRecord],
) -> PopulationSnapshot:
    """Validate, canonicalize, and hash an input population.

    Invalid submissions are excluded before N is established (section 4).
    A submission is invalid when any score is missing, non-finite, outside
    [0, 100], or when either profile fails to total exactly 100.
    """
    valid: list[SubmissionRecord] = []
    for submission in submissions:
        try:
            _validate_submission(submission)
        except CalculationInvariantError:
            continue
        valid.append(submission)

    canonical = sorted(valid, key=lambda s: s.identifier)
    return PopulationSnapshot(
        submissions=tuple(canonical),
        population_hash=canonical_population_hash(canonical),
    )


def _validate_submission(submission: SubmissionRecord) -> None:
    for label, profile in (
        ("challenge", submission.challenge),
        ("reward", submission.reward),
    ):
        total = profile.total()
        for name, value in (
            ("micro", profile.micro),
            ("macro", profile.macro),
            ("mystiko", profile.mystiko),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise CalculationInvariantError(f"{label} {name} is not numeric")
            if value != value or value in (float("inf"), float("-inf")):
                raise CalculationInvariantError(f"{label} {name} is not finite")
            if value < 0 or value > 100:
                raise CalculationInvariantError(f"{label} {name} out of range")
        if total != total or total in (float("inf"), float("-inf")):
            raise CalculationInvariantError(f"{label} total is not finite")
        if abs(total - 100) > 1e-9:
            raise CalculationInvariantError(
                f"{label} profile totals {total} instead of 100"
            )


def analysis_values(submission: SubmissionRecord) -> list[float]:
    """Six marginal values in the frozen analysis order."""
    return [
        submission.component(profile, dimension)
        for profile, dimension in PROFILE_ANALYSIS_ORDER
    ]


__all__ = [
    "PopulationSnapshot",
    "Profile",
    "SubmissionRecord",
    "analysis_values",
    "build_population_snapshot",
    "canonical_population_hash",
]
