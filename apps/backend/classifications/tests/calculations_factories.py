"""
Shared factories for derived-calculation tests — SBGC-65.

Builders produce valid 100-point submissions and canonical population
snapshots without touching the database.  Pure-mathematics tests reuse
these helpers so scenario construction stays one obvious place.
"""

from __future__ import annotations

import random

from classifications.calculations.profiles import (
    PopulationSnapshot,
    Profile,
    SubmissionRecord,
    build_population_snapshot,
)


def profile(micro: float, macro: float, mystiko: float) -> Profile:
    return Profile(micro=micro, macro=macro, mystiko=mystiko)


def balanced(
    micro: float = 33.0, macro: float = 33.0, mystiko: float = 34.0
) -> Profile:
    return Profile(micro=micro, macro=macro, mystiko=mystiko)


def submission(
    identifier: str,
    challenge: Profile,
    reward: Profile,
    role: str = "community",
) -> SubmissionRecord:
    return SubmissionRecord(
        identifier=identifier,
        challenge=challenge,
        reward=reward,
        role=role,
    )


def identical_submissions(
    count: int,
    *,
    role: str = "community",
    identifier_prefix: str = "sub",
    challenge: Profile | None = None,
    reward: Profile | None = None,
    first_roles: dict[int, str] | None = None,
) -> list[SubmissionRecord]:
    """``count`` identical submissions, optionally overriding leading roles."""
    challenge = challenge or balanced()
    reward = reward or balanced(40.0, 30.0, 30.0)
    result: list[SubmissionRecord] = []
    for index in range(count):
        member_role = role
        if first_roles and index in first_roles:
            member_role = first_roles[index]
        result.append(
            SubmissionRecord(
                identifier=f"{identifier_prefix}-{index:04d}",
                challenge=challenge,
                reward=reward,
                role=member_role,
            )
        )
    return result


def scattered_submissions(
    count: int,
    *,
    seed: int = 1,
    roles: dict[int, str] | None = None,
    base_challenge: Profile | None = None,
    base_reward: Profile | None = None,
    spread: float = 6.0,
) -> list[SubmissionRecord]:
    """``count`` valid submissions with bounded symmetric perturbation."""
    rng = random.Random(seed)
    base_challenge = base_challenge or balanced()
    base_reward = base_reward or balanced(40.0, 30.0, 30.0)
    result: list[SubmissionRecord] = []
    for index in range(count):
        challenge = _perturb(rng, base_challenge, spread)
        reward = _perturb(rng, base_reward, spread)
        result.append(
            SubmissionRecord(
                identifier=f"sub-{index:04d}",
                challenge=challenge,
                reward=reward,
                role=(roles or {}).get(index, "community"),
            )
        )
    return result


def _perturb(rng: random.Random, base: Profile, spread: float) -> Profile:
    while True:
        values = [
            max(0.0, base.micro + rng.uniform(-spread, spread)),
            max(0.0, base.macro + rng.uniform(-spread, spread)),
            max(0.0, base.mystiko + rng.uniform(-spread, spread)),
        ]
        total = sum(values)
        if total <= 0:
            continue
        scaled = [100.0 * value / total for value in values]
        if all(value > 0 for value in scaled):
            return Profile(micro=scaled[0], macro=scaled[1], mystiko=scaled[2])


def population(
    submissions: list[SubmissionRecord],
) -> PopulationSnapshot:
    return build_population_snapshot(submissions)


__all__ = [
    "balanced",
    "identical_submissions",
    "population",
    "profile",
    "scattered_submissions",
    "submission",
]
