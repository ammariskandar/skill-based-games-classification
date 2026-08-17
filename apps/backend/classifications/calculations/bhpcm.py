"""
BHPCM_V1 — Bayesian Hierarchical Pluralistic Consensus Model (Part B).

Unifies the three method perspectives in ilr space through a stratified
bootstrap, bounded governance distributions, disagreement-driven expert
influence, posterior synthesis, largest-remainder reconciliation, conflict
classification, and deterministic sensitivity disclosures.

Frozen production settings: B = 10,000 bootstrap replicates and S = 20
governance draws per jointly valid replicate.  Reduced counts may only be
injected for tests whose property does not depend on the frozen counts.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from classifications.calculations.composition import ilr_inv, joint_ilr
from classifications.calculations.constants import (
    BHPCM_BOOTSTRAP_REPLICATES,
    BHPCM_DISAGREEMENT_HALF_LIFE,
    BHPCM_GOVERNANCE_DRAWS,
    BHPCM_KAPPA_E,
    BHPCM_LAMBDA_ALPHA,
    BHPCM_LAMBDA_BETA,
    BHPCM_LAMBDA_MAX,
    BHPCM_LAMBDA_MIN,
    BHPCM_OMEGA_MAX,
    BHPCM_OMEGA_MIN,
    BHPCM_VERSION,
    MASTER_VERSION,
    METHODS_VERSION,
    ROLE_COMMUNITY,
    ROLE_COMMUNITY_LEADER,
    ROLE_MODERATOR,
    ROLE_SUPERUSER,
    SUM_TOLERANCE,
    TIE_TOLERANCE,
)
from classifications.calculations.method1 import method1_calculate
from classifications.calculations.method2 import method2_calculate
from classifications.calculations.method3 import method3_calculate
from classifications.calculations.profiles import PopulationSnapshot, Profile
from classifications.calculations.reconciliation import largest_remainder_profile
from classifications.calculations.results import (
    INSUFFICIENT_METHOD_1,
    INSUFFICIENT_METHOD_2,
    INSUFFICIENT_METHOD_3,
    READY,
    UNIFIED_CALCULATION_ERROR,
    UNIFIED_CALCULATION_UNSTABLE,
    MethodResult,
)

_ROLE_ORDER = (ROLE_SUPERUSER, ROLE_MODERATOR, ROLE_COMMUNITY_LEADER, ROLE_COMMUNITY)

_VEC4 = tuple[float, float, float, float]
_VEC3 = tuple[float, float, float]

_SENSITIVITY_WEIGHTS = (0.30, 0.40, 0.50)


@dataclass(frozen=True)
class BHPCMResult:
    """Complete ``BHPCM_V1`` result for one population."""

    status: str
    official_raw_challenge: Profile | None = None
    official_raw_reward: Profile | None = None
    integer_challenge: tuple[int, int, int] | None = None
    integer_reward: tuple[int, int, int] | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == READY


def central_expert_influence(disagreement: float) -> float:
    """mu_E(D) = 0.30 + 0.20 * 2^(-D/0.25) (Part B.10.3)."""
    return BHPCM_OMEGA_MIN + (BHPCM_OMEGA_MAX - BHPCM_OMEGA_MIN) * (
        2.0 ** (-disagreement / BHPCM_DISAGREEMENT_HALF_LIFE)
    )


def _truncated_beta(
    rng: random.Random, alpha: float, beta: float, low: float, high: float
) -> float:
    """A draw from Beta(alpha, beta) truncated to [low, high] (rejection)."""
    while True:
        value = rng.betavariate(alpha, beta)
        if low <= value <= high:
            return value


def _snapshot_from_indices(
    population: PopulationSnapshot, indices: list[int]
) -> PopulationSnapshot:
    """A bootstrap resample snapshot with canonically sorted indices."""
    return PopulationSnapshot(
        submissions=tuple(population.submissions[i] for i in sorted(indices))
    )


def _zero_count(profile: Profile) -> int:
    return sum(1 for v in profile.components() if v == 0.0)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    size = len(ordered)
    if size % 2 == 1:
        return ordered[size // 2]
    return (ordered[size // 2 - 1] + ordered[size // 2]) / 2.0


def _quantile(values: list[float], q: float) -> float:
    """Linear-interpolation quantile over a list of finite floats."""
    ordered = sorted(values)
    size = len(ordered)
    position = q * (size - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": _mean(values),
        "median": _median(values),
        "p05": _quantile(values, 0.05),
        "p95": _quantile(values, 0.95),
    }


def _component_summaries(
    draws: list[_VEC3], names: tuple[str, str, str]
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for j, name in enumerate(names):
        column = [draw[j] for draw in draws]
        result[name] = {
            "componentwise_posterior_mean": _mean(column),
            "posterior_median": _median(column),
        }
    return result


def _component_intervals(
    draws: list[_VEC3], names: tuple[str, str, str]
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for j, name in enumerate(names):
        column = [draw[j] for draw in draws]
        result[name] = {
            "p05": _quantile(column, 0.05),
            "p95": _quantile(column, 0.95),
            "p25": _quantile(column, 0.25),
            "p75": _quantile(column, 0.75),
        }
    return result


def _directional_probabilities(draws: list[_VEC3], prefix: str) -> dict[str, float]:
    """Pairwise-ordering probabilities (Part B.14.3)."""
    total = len(draws)
    pairs = {
        "micro_gt_macro": (0, 1),
        "micro_gt_mystiko": (0, 2),
        "macro_gt_mystiko": (1, 2),
    }
    result: dict[str, float] = {}
    for label, (a, b) in pairs.items():
        wins = 0.0
        for draw in draws:
            difference = draw[a] - draw[b]
            if difference > TIE_TOLERANCE:
                wins += 1.0
            elif abs(difference) <= TIE_TOLERANCE:
                wins += 0.5
        result[f"{prefix}_{label}"] = wins / total
    return result


def _largest_component_probabilities(
    draws: list[_VEC3], names: tuple[str, str, str]
) -> dict[str, float]:
    total = len(draws)
    counts = {name: 0.0 for name in names}
    for draw in draws:
        best = max(draw)
        tied = [j for j, value in enumerate(draw) if abs(value - best) <= TIE_TOLERANCE]
        share = 1.0 / len(tied)
        for j in tied:
            counts[names[j]] += share
    return {f"pr_{name}_largest": counts[name] / total for name in names}


def _rounded_profile_probabilities(draws: list[_VEC3]) -> dict[str, Any]:
    """Reconciled-integer-triplet probabilities >= 0.5% (Part B.14.4)."""
    total = len(draws)
    counter: Counter[tuple[int, int, int]] = Counter()
    for draw in draws:
        counter[largest_remainder_profile(Profile(*draw))] += 1
    all_triplets = [
        {
            "triplet": list(triplet),
            "probability": round(count / total, 6),
        }
        for triplet, count in counter.items()
    ]
    all_triplets.sort(key=lambda entry: entry["probability"], reverse=True)
    reported = [entry for entry in all_triplets if entry["probability"] >= 0.005]
    most_probable = all_triplets[0] if all_triplets else None
    return {
        "most_probable_triplet": most_probable,
        "reported_triplets": reported,
    }


def _conflict_classification(d0: float) -> str:
    if d0 < 0.10:
        return "Low conflict"
    if d0 < 0.25:
        return "Moderate conflict"
    if d0 < 0.50:
        return "High conflict"
    return "Very high conflict"


def _sensitivity_profiles(z1: _VEC4, z2: _VEC4, z3: _VEC4) -> dict[str, Any]:
    """Deterministic sensitivity disclosures at omega_E in {0.30, 0.40, 0.50}."""
    z_p0: _VEC4 = (
        0.5 * z2[0] + 0.5 * z3[0],
        0.5 * z2[1] + 0.5 * z3[1],
        0.5 * z2[2] + 0.5 * z3[2],
        0.5 * z2[3] + 0.5 * z3[3],
    )
    profiles: dict[str, Any] = {}
    integers: dict[float, tuple[tuple[int, int, int], tuple[int, int, int]]] = {}
    for weight in _SENSITIVITY_WEIGHTS:
        z_u: _VEC4 = (
            weight * z1[0] + (1.0 - weight) * z_p0[0],
            weight * z1[1] + (1.0 - weight) * z_p0[1],
            weight * z1[2] + (1.0 - weight) * z_p0[2],
            weight * z1[3] + (1.0 - weight) * z_p0[3],
        )
        challenge = ilr_inv((z_u[0], z_u[1]))
        reward = ilr_inv((z_u[2], z_u[3]))
        int_challenge = largest_remainder_profile(challenge)
        int_reward = largest_remainder_profile(reward)
        integers[weight] = (int_challenge, int_reward)
        profiles[f"omega_{weight:.2f}"] = {
            "continuous_challenge": list(challenge.components()),
            "continuous_reward": list(reward.components()),
            "integer_challenge": list(int_challenge),
            "integer_reward": list(int_reward),
        }
    low = integers[0.30]
    high = integers[0.50]
    names = (
        "challenge_micro",
        "challenge_macro",
        "challenge_mystiko",
        "reward_micro",
        "reward_macro",
        "reward_mystiko",
    )
    sensitive: list[str] = []
    for index, name in enumerate(names):
        profile_index = 0 if name.startswith("challenge") else 1
        component_index = index % 3
        if (
            abs(
                low[profile_index][component_index]
                - high[profile_index][component_index]
            )
            >= 3
        ):
            sensitive.append(name)
    return {"profiles": profiles, "governance_sensitive_components": sensitive}


def bhpcm_calculate(
    population: PopulationSnapshot,
    method_results: tuple[MethodResult, MethodResult, MethodResult],
    *,
    bootstrap_replicates: int | None = None,
    governance_draws: int | None = None,
    stream_variant: int = 0,
) -> BHPCMResult:
    """Run ``BHPCM_V1`` over the three method perspectives.

    ``stream_variant`` selects the deterministic random stream.  ``0`` is the
    canonical production stream (derived only from the population hash);
    nonzero variants are used exclusively by the bootstrap-stability study
    to confirm a chosen ``B`` is not passing because of one lucky sequence.
    """
    replicates = (
        BHPCM_BOOTSTRAP_REPLICATES
        if bootstrap_replicates is None
        else bootstrap_replicates
    )
    draws_per_replicate = (
        BHPCM_GOVERNANCE_DRAWS if governance_draws is None else governance_draws
    )

    method_1, method_2, method_3 = method_results
    if not method_1.is_ready:
        return BHPCMResult(
            status=INSUFFICIENT_METHOD_1,
            diagnostics={"raw_n": population.raw_n},
        )
    if not method_2.is_ready:
        return BHPCMResult(
            status=INSUFFICIENT_METHOD_2,
            diagnostics={"raw_n": population.raw_n},
        )
    if not method_3.is_ready:
        return BHPCMResult(
            status=INSUFFICIENT_METHOD_3,
            diagnostics={"raw_n": population.raw_n},
        )

    assert method_1.raw_challenge is not None
    assert method_1.raw_reward is not None
    assert method_2.raw_challenge is not None
    assert method_2.raw_reward is not None
    assert method_3.raw_challenge is not None
    assert method_3.raw_reward is not None

    zero_replacement_count = (
        _zero_count(method_1.raw_challenge)
        + _zero_count(method_1.raw_reward)
        + _zero_count(method_2.raw_challenge)
        + _zero_count(method_2.raw_reward)
        + _zero_count(method_3.raw_challenge)
        + _zero_count(method_3.raw_reward)
    )

    # Original-data four-dimensional perspectives.
    z1 = joint_ilr(method_1.raw_challenge, method_1.raw_reward)
    z2 = joint_ilr(method_2.raw_challenge, method_2.raw_reward)
    z3 = joint_ilr(method_3.raw_challenge, method_3.raw_reward)

    # Point conflict from the original dataset (Part B.15).
    z_p0 = tuple(0.5 * a + 0.5 * b for a, b in zip(z2, z3, strict=False))
    d_c0 = math.hypot(z1[0] - z_p0[0], z1[1] - z_p0[1])
    d_r0 = math.hypot(z1[2] - z_p0[2], z1[3] - z_p0[3])
    d0 = math.sqrt((d_c0 * d_c0 + d_r0 * d_r0) / 2.0)
    conflict = _conflict_classification(d0)

    # Frozen reproducible random stream (Part B.22.1).  Variant 0 is the
    # canonical production stream; nonzero variants are study-only.
    stream_identifier = f"BHPCM_V1:{MASTER_VERSION}:{population.population_hash}"
    if stream_variant:
        stream_identifier += f":{stream_variant}"
    rng = random.Random(stream_identifier)

    # Role-stratified index pools.
    role_indices: dict[str, list[int]] = {role: [] for role in _ROLE_ORDER}
    for i, submission in enumerate(population.submissions):
        role_indices.setdefault(submission.role, []).append(i)

    z1s: list[_VEC4] = []
    z2s: list[_VEC4] = []
    z3s: list[_VEC4] = []
    invalid = 0
    for _ in range(replicates):
        indices: list[int] = []
        for role in _ROLE_ORDER:
            pool = role_indices[role]
            if pool:
                indices.extend(rng.choices(pool, k=len(pool)))
        resample = _snapshot_from_indices(population, indices)
        r1 = method1_calculate(resample)
        r2 = method2_calculate(resample)
        r3 = method3_calculate(resample)
        if not (r1.is_ready and r2.is_ready and r3.is_ready):
            invalid += 1
            continue
        assert r1.raw_challenge is not None and r1.raw_reward is not None
        assert r2.raw_challenge is not None and r2.raw_reward is not None
        assert r3.raw_challenge is not None and r3.raw_reward is not None
        z1s.append(joint_ilr(r1.raw_challenge, r1.raw_reward))
        z2s.append(joint_ilr(r2.raw_challenge, r2.raw_reward))
        z3s.append(joint_ilr(r3.raw_challenge, r3.raw_reward))

    valid = replicates - invalid
    # Bootstrap-invalid rule (frozen): a bootstrap replicate is invalid when
    # any method returns a non-ready result for it.  UNIFIED_CALCULATION_UNSTABLE
    # is returned exactly when more than 1% of replicates are invalid:
    #   invalid * 100 > replicates
    # (integer-safe; exactly 1% invalid is allowed, more than 1% is not).
    if invalid * 100 > replicates:
        return BHPCMResult(
            status=UNIFIED_CALCULATION_UNSTABLE,
            diagnostics={
                "raw_n": population.raw_n,
                "bootstrap_target_count": replicates,
                "bootstrap_valid_count": valid,
                "bootstrap_invalid_count": invalid,
            },
        )

    # Posterior draws.
    z_us: list[_VEC4] = []
    u_challenges: list[_VEC3] = []
    u_rewards: list[_VEC3] = []
    omega_1s: list[float] = []
    omega_2s: list[float] = []
    omega_3s: list[float] = []
    lambdas: list[float] = []
    disagreements: list[float] = []
    d_challenges: list[float] = []
    d_rewards: list[float] = []
    expert_influences: list[float] = []

    for b in range(valid):
        zb1 = z1s[b]
        zb2 = z2s[b]
        zb3 = z3s[b]
        for _ in range(draws_per_replicate):
            lam = _truncated_beta(
                rng,
                BHPCM_LAMBDA_ALPHA,
                BHPCM_LAMBDA_BETA,
                BHPCM_LAMBDA_MIN,
                BHPCM_LAMBDA_MAX,
            )
            z_p = tuple(
                lam * a + (1.0 - lam) * b for a, b in zip(zb2, zb3, strict=False)
            )
            d_c = math.hypot(zb1[0] - z_p[0], zb1[1] - z_p[1])
            d_r = math.hypot(zb1[2] - z_p[2], zb1[3] - z_p[3])
            d = math.sqrt((d_c * d_c + d_r * d_r) / 2.0)
            mu_e = central_expert_influence(d)
            omega_e = _truncated_beta(
                rng,
                BHPCM_KAPPA_E * mu_e,
                BHPCM_KAPPA_E * (1.0 - mu_e),
                BHPCM_OMEGA_MIN,
                BHPCM_OMEGA_MAX,
            )
            z_u: _VEC4 = (
                omega_e * zb1[0] + (1.0 - omega_e) * z_p[0],
                omega_e * zb1[1] + (1.0 - omega_e) * z_p[1],
                omega_e * zb1[2] + (1.0 - omega_e) * z_p[2],
                omega_e * zb1[3] + (1.0 - omega_e) * z_p[3],
            )
            challenge = ilr_inv((z_u[0], z_u[1]))
            reward = ilr_inv((z_u[2], z_u[3]))
            if not _draw_is_finite(z_u, challenge, reward, omega_e, lam):
                return BHPCMResult(
                    status=UNIFIED_CALCULATION_ERROR,
                    diagnostics={
                        "raw_n": population.raw_n,
                        "error": "non-finite posterior draw",
                    },
                )
            if not _draw_invariants_hold(omega_e, lam, challenge, reward):
                return BHPCMResult(
                    status=UNIFIED_CALCULATION_ERROR,
                    diagnostics={
                        "raw_n": population.raw_n,
                        "error": "posterior draw invariant violation",
                    },
                )
            z_us.append(z_u)
            u_challenges.append(challenge.components())
            u_rewards.append(reward.components())
            omega_1s.append(omega_e)
            omega_2s.append((1.0 - omega_e) * lam)
            omega_3s.append((1.0 - omega_e) * (1.0 - lam))
            lambdas.append(lam)
            disagreements.append(d)
            d_challenges.append(d_c)
            d_rewards.append(d_r)
            expert_influences.append(omega_e)

    draw_count = len(z_us)

    # Official continuous point estimate: inverse-ilr of the posterior mean.
    mean_z: _VEC4 = (
        _mean([z[0] for z in z_us]),
        _mean([z[1] for z in z_us]),
        _mean([z[2] for z in z_us]),
        _mean([z[3] for z in z_us]),
    )
    official_challenge = ilr_inv((mean_z[0], mean_z[1]))
    official_reward = ilr_inv((mean_z[2], mean_z[3]))
    if (
        abs(official_challenge.total() - 100.0) > SUM_TOLERANCE
        or abs(official_reward.total() - 100.0) > SUM_TOLERANCE
    ):
        return BHPCMResult(
            status=UNIFIED_CALCULATION_ERROR,
            diagnostics={
                "raw_n": population.raw_n,
                "error": "official profile failed sum validation",
            },
        )

    integer_challenge = largest_remainder_profile(official_challenge)
    integer_reward = largest_remainder_profile(official_reward)

    challenge_names = ("challenge_micro", "challenge_macro", "challenge_mystiko")
    reward_names = ("reward_micro", "reward_macro", "reward_mystiko")
    sensitivity = _sensitivity_profiles(z1, z2, z3)

    challenge_intervals = _component_intervals(u_challenges, challenge_names)
    reward_intervals = _component_intervals(u_rewards, reward_names)

    diagnostics: dict[str, Any] = {
        "model": "BHPCM",
        "model_version": BHPCM_VERSION,
        "method_1_version": METHODS_VERSION,
        "method_2_version": METHODS_VERSION,
        "method_3_version": METHODS_VERSION,
        "input_population_hash": population.population_hash,
        "raw_submission_count": population.raw_n,
        "validated_submission_count": population.raw_n,
        "role_counts": population.role_counts(),
        "bootstrap_target_count": replicates,
        "bootstrap_valid_count": valid,
        "bootstrap_invalid_count": invalid,
        "governance_draws_per_bootstrap": draws_per_replicate,
        "posterior_draw_count": draw_count,
        "zero_replacement_count": zero_replacement_count,
        "random_stream_identifier": stream_identifier,
        "method_1_raw_challenge": list(method_1.raw_challenge.components()),
        "method_1_raw_reward": list(method_1.raw_reward.components()),
        "method_2_raw_challenge": list(method_2.raw_challenge.components()),
        "method_2_raw_reward": list(method_2.raw_reward.components()),
        "method_3_raw_challenge": list(method_3.raw_challenge.components()),
        "method_3_raw_reward": list(method_3.raw_reward.components()),
        "unified_raw_challenge": list(official_challenge.components()),
        "unified_raw_reward": list(official_reward.components()),
        "unified_integer_challenge": list(integer_challenge),
        "unified_integer_reward": list(integer_reward),
        "component_intervals_50": {
            "challenge": challenge_intervals,
            "reward": reward_intervals,
        },
        "component_intervals_90": {
            "challenge": {
                name: {"p05": entry["p05"], "p95": entry["p95"]}
                for name, entry in challenge_intervals.items()
            },
            "reward": {
                name: {"p05": entry["p05"], "p95": entry["p95"]}
                for name, entry in reward_intervals.items()
            },
        },
        "component_supplementary": {
            "challenge": _component_summaries(u_challenges, challenge_names),
            "reward": _component_summaries(u_rewards, reward_names),
        },
        "method_weight_summaries": {
            "omega_1": _summary(omega_1s),
            "omega_2": _summary(omega_2s),
            "omega_3": _summary(omega_3s),
        },
        "population_balance_summary": _summary(lambdas),
        "expert_influence_summary": _summary(expert_influences),
        "combined_disagreement_summary": _summary(disagreements),
        "challenge_disagreement": _summary(d_challenges),
        "reward_disagreement": _summary(d_rewards),
        "challenge_point_disagreement": d_c0,
        "reward_point_disagreement": d_r0,
        "combined_point_disagreement": d0,
        "conflict_classification": conflict,
        "central_expert_influence_at_d0": central_expert_influence(d0),
        "directional_probabilities": {
            "challenge": _directional_probabilities(u_challenges, "challenge"),
            "reward": _directional_probabilities(u_rewards, "reward"),
        },
        "largest_component_probabilities": {
            "challenge": _largest_component_probabilities(
                u_challenges, challenge_names
            ),
            "reward": _largest_component_probabilities(u_rewards, reward_names),
        },
        "rounded_profile_probabilities": {
            "challenge": _rounded_profile_probabilities(u_challenges),
            "reward": _rounded_profile_probabilities(u_rewards),
        },
        "sensitivity_profiles": sensitivity["profiles"],
        "governance_sensitive_components": sensitivity[
            "governance_sensitive_components"
        ],
        "bootstrap_replicates_requested": replicates,
    }

    return BHPCMResult(
        status=READY,
        official_raw_challenge=official_challenge,
        official_raw_reward=official_reward,
        integer_challenge=integer_challenge,
        integer_reward=integer_reward,
        diagnostics=diagnostics,
    )


def _draw_is_finite(
    z_u: _VEC4, challenge: Profile, reward: Profile, omega_e: float, lam: float
) -> bool:
    for value in (*z_u, *challenge.components(), *reward.components(), omega_e, lam):
        if not math.isfinite(value):
            return False
    return True


def _draw_invariants_hold(
    omega_e: float, lam: float, challenge: Profile, reward: Profile
) -> bool:
    if not (BHPCM_OMEGA_MIN <= omega_e <= BHPCM_OMEGA_MAX):
        return False
    if not (BHPCM_LAMBDA_MIN <= lam <= BHPCM_LAMBDA_MAX):
        return False
    for profile in (challenge, reward):
        if abs(profile.total() - 100.0) > SUM_TOLERANCE:
            return False
        if any(v <= 0 for v in profile.components()):
            return False
    return True


__all__ = [
    "BHPCMResult",
    "bhpcm_calculate",
    "central_expert_influence",
]
