"""
Confidence layers — SBGC-65 (Parts C and D).

``CONFIDENCE_BASE_V1`` (population saturation, bounded authoritative
support, coherence penalties), ``CONFIDENCE_RESILIENCE_V1`` (bounded
population resilience below 50), ``PROVISIONAL_CONFIDENCE_V1`` (Qn-style
Aitchison dispersion for 1 <= N < 20), and ``BOUNDARY_CONTINUITY_V1``
(static per-Game/per-version negative-cliff calibration with decay).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from classifications.calculations.composition import joint_ilr
from classifications.calculations.constants import (
    AUTHORITATIVE_ROLES,
    BOUNDARY_DECAY_TAU,
    BOUNDARY_MAX_SUBSETS,
    BOUNDARY_MIN_READY_LOO,
    BOUNDARY_READY_FRACTION,
    BOUNDARY_SAMPLER_VERSION,
    BOUNDARY_SEED,
    BOUNDARY_SUBSET_SIZE,
    CONFIDENCE_ALPHA,
    CONFIDENCE_BASE_VERSION,
    CONFIDENCE_D_0,
    CONFIDENCE_FINAL_VERSION,
    CONFIDENCE_GAMMA_D,
    CONFIDENCE_GAMMA_V,
    CONFIDENCE_N_0,
    CONFIDENCE_N_REF,
    CONFIDENCE_N_V,
    CONFIDENCE_RHO,
    CONFIDENCE_V_0,
    MASTER_VERSION,
    PROVISIONAL_CONFIDENCE_VERSION,
    PROVISIONAL_H_0,
    PROVISIONAL_MAX,
    PROVISIONAL_Q_HALF,
    PROVISIONAL_QN_FACTOR,
    PROVISIONAL_QN_FACTORS,
    PROVISIONAL_ROLE_UPLIFT,
    PROVISIONAL_S_DENOMINATOR,
    PROVISIONAL_S_EXPONENT,
    PROVISIONAL_S_MAX,
    RESILIENCE_APPLY_THRESHOLD,
    RESILIENCE_EXPONENT,
    RESILIENCE_MAX,
    RESILIENCE_N_SAT,
    ROLE_BASE_WEIGHTS,
)
from classifications.calculations.method1 import method1_calculate
from classifications.calculations.method2 import method2_calculate
from classifications.calculations.method3 import method3_calculate
from classifications.calculations.profiles import PopulationSnapshot, Profile
from classifications.calculations.results import (
    BOUNDARY_CALIBRATION_UNAVAILABLE,
    CALCULATION_ERROR,
    PROVISIONAL_READY,
    READY,
    ConfidenceResult,
    confidence_label,
)

_AUTHORITATIVE_WEIGHTS = {
    role: float(ROLE_BASE_WEIGHTS[role]) for role in AUTHORITATIVE_ROLES
}


@dataclass(frozen=True)
class ConfidenceBaseResult:
    """A complete ``CONFIDENCE_BASE_V1`` result."""

    status: str
    level_raw: float | None = None
    level_reported: float | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == READY


@dataclass(frozen=True)
class ResilienceResult:
    """A complete ``CONFIDENCE_RESILIENCE_V1`` result."""

    capacity: float
    applied: float
    level: float


@dataclass(frozen=True)
class BoundaryCalibrationData:
    """Static per-Game/per-version boundary calibration constant."""

    status: str
    delta: float
    calibration_population_hash: str = ""
    population_size: int = 0
    subset_count_attempted: int = 0
    subset_count_ready: int = 0
    sampler_version: str = BOUNDARY_SAMPLER_VERSION
    seed_or_stream: str = ""
    version: str = CONFIDENCE_FINAL_VERSION

    @property
    def is_calibrated(self) -> bool:
        return self.status == READY


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    size = len(ordered)
    if size % 2 == 1:
        return ordered[size // 2]
    return (ordered[size // 2 - 1] + ordered[size // 2]) / 2.0


def _kish_effective_n(weights: list[float]) -> float:
    if not weights:
        return 0.0
    total = sum(weights)
    return total * total / sum(w * w for w in weights)


def _weighted_center(
    vectors: list[tuple[float, ...]], weights: list[float]
) -> tuple[float, ...]:
    total = sum(weights)
    return tuple(
        sum(w * v[j] for w, v in zip(weights, vectors, strict=False)) / total
        for j in range(4)
    )


def _authoritative_members(population: PopulationSnapshot) -> list[int]:
    return [
        i
        for i, submission in enumerate(population.submissions)
        if submission.role in AUTHORITATIVE_ROLES
    ]


def _population_center(
    method_2_raw_challenge: Profile | None,
    method_2_raw_reward: Profile | None,
    method_3_raw_challenge: Profile | None,
    method_3_raw_reward: Profile | None,
) -> tuple[float, float, float, float] | None:
    """z_P = 1/2 z_2 + 1/2 z_3 (Part C.10); None when a method is missing."""
    if any(
        profile is None
        for profile in (
            method_2_raw_challenge,
            method_2_raw_reward,
            method_3_raw_challenge,
            method_3_raw_reward,
        )
    ):
        return None
    z2 = joint_ilr(method_2_raw_challenge, method_2_raw_reward)  # pyright: ignore[reportArgumentType]
    z3 = joint_ilr(method_3_raw_challenge, method_3_raw_reward)  # pyright: ignore[reportArgumentType]
    return (
        0.5 * z2[0] + 0.5 * z3[0],
        0.5 * z2[1] + 0.5 * z3[1],
        0.5 * z2[2] + 0.5 * z3[2],
        0.5 * z2[3] + 0.5 * z3[3],
    )


def _combined_deviation(
    a: tuple[float, ...], b: tuple[float, ...]
) -> tuple[float, float, float]:
    """(D_A,C, D_A,R, D_A) between two four-dimensional vectors."""
    d_c = math.hypot(a[0] - b[0], a[1] - b[1])
    d_r = math.hypot(a[2] - b[2], a[3] - b[3])
    d = math.sqrt((d_c * d_c + d_r * d_r) / 2.0)
    return (d_c, d_r, d)


def confidence_base_calculate(
    population: PopulationSnapshot,
    method_2_raw_challenge: Profile | None,
    method_2_raw_reward: Profile | None,
    method_3_raw_challenge: Profile | None,
    method_3_raw_reward: Profile | None,
) -> ConfidenceBaseResult:
    """Compute ``CONFIDENCE_BASE_V1`` (Part C)."""
    n = population.raw_n
    if n == 0:
        # Part C.17.3: N = 0 forces C0 = 0; no other term may override.
        return ConfidenceBaseResult(
            status=READY,
            level_raw=0.0,
            level_reported=0.0,
            diagnostics={"validated_population_size": 0},
        )

    authoritative_indices = _authoritative_members(population)
    weights = [
        _AUTHORITATIVE_WEIGHTS[population.submissions[i].role]
        for i in authoritative_indices
    ]
    n_a = len(authoritative_indices)
    n_eff = _kish_effective_n(weights)

    # Authoritative center (Part C.9).
    authoritative_center: tuple[float, ...] | None = None
    if n_a:
        vectors = [
            joint_ilr(
                population.submissions[i].challenge,
                population.submissions[i].reward,
            )
            for i in authoritative_indices
        ]
        authoritative_center = _weighted_center(vectors, weights)

    # Robust population center (Part C.10).
    z_p = _population_center(
        method_2_raw_challenge,
        method_2_raw_reward,
        method_3_raw_challenge,
        method_3_raw_reward,
    )
    if z_p is None:
        # Part C.17.4: missing population method -> non-ready, null level.
        return ConfidenceBaseResult(
            status="NOT_READY",
            diagnostics={
                "validated_population_size": n,
                "error": "population method output missing",
            },
        )

    if authoritative_center is None:
        d_c, d_r, d_a = 0.0, 0.0, 0.0
    else:
        d_c, d_r, d_a = _combined_deviation(authoritative_center, z_p)

    # Internal authoritative variance (Part C.12).
    v_a = 0.0
    if n_a >= 2 and authoritative_center is not None:
        total = sum(weights)
        numerator = 0.0
        for index, i in enumerate(authoritative_indices):
            z_i = joint_ilr(
                population.submissions[i].challenge,
                population.submissions[i].reward,
            )
            squared = sum((z_i[j] - authoritative_center[j]) ** 2 for j in range(4))
            numerator += weights[index] * squared
        v_a = numerator / (4.0 * total)

    # Evidence factors (Part C.3).
    e_n = math.log(20.0) * (n / CONFIDENCE_N_REF) ** CONFIDENCE_ALPHA
    e_a = 1.0 + CONFIDENCE_RHO * (1.0 - math.exp(-n_eff / CONFIDENCE_N_0))
    deviation_penalty = (
        CONFIDENCE_GAMMA_D * d_a * d_a / (CONFIDENCE_D_0**2 + v_a / max(n_eff, 1.0))
    )
    variance_penalty = (
        CONFIDENCE_GAMMA_V
        * (n_eff / (n_eff + CONFIDENCE_N_V))
        * v_a
        / (CONFIDENCE_V_0**2)
    )
    e_c = math.exp(-(deviation_penalty + variance_penalty))

    evidence = e_n * e_a * e_c
    level = 100.0 * (1.0 - math.exp(-evidence))
    if not math.isfinite(level):
        return ConfidenceBaseResult(
            status=CALCULATION_ERROR,
            diagnostics={
                "validated_population_size": n,
                "error": "non-finite confidence quantity",
            },
        )
    level = min(100.0, max(0.0, level))  # Part C.17.6 numerical safeguard.

    return ConfidenceBaseResult(
        status=READY,
        level_raw=level,
        level_reported=round(level, 1),
        diagnostics={
            "confidence_version": CONFIDENCE_BASE_VERSION,
            "validated_population_size": n,
            "authoritative_literal_count": n_a,
            "authoritative_effective_sample_size": n_eff,
            "authoritative_challenge_deviation": d_c,
            "authoritative_reward_deviation": d_r,
            "authoritative_combined_deviation": d_a,
            "authoritative_internal_variance": v_a,
            "population_evidence_factor": e_n,
            "authoritative_sample_support_factor": e_a,
            "coherence_factor": e_c,
            "deviation_penalty_exponent": deviation_penalty,
            "variance_penalty_exponent": variance_penalty,
            "role_counts": population.role_counts(),
            "role_weight_sums": {
                role: _AUTHORITATIVE_WEIGHTS[role]
                * population.role_counts().get(role, 0)
                for role in AUTHORITATIVE_ROLES
            },
            "zero_replacement_count": 0,
            "input_population_hash": population.population_hash,
        },
    )


def resilience_apply(c0: float, n: int) -> ResilienceResult:
    """Apply ``CONFIDENCE_RESILIENCE_V1`` (Part D1)."""
    capacity = RESILIENCE_MAX * min(
        1.0,
        (math.log(1.0 + n) / math.log(RESILIENCE_N_SAT + 1.0)) ** RESILIENCE_EXPONENT,
    )
    if c0 >= RESILIENCE_APPLY_THRESHOLD:
        return ResilienceResult(capacity=capacity, applied=0.0, level=c0)
    applied = capacity * (1.0 - c0 / RESILIENCE_APPLY_THRESHOLD)
    return ResilienceResult(
        capacity=capacity,
        applied=applied,
        level=c0 + applied,
    )


def boundary_decay(delta: float, n: int) -> float:
    """g(N) = exp(-(N-20)/100) for N >= 20 (Part D3.4)."""
    if n < BOUNDARY_SUBSET_SIZE:
        return 0.0
    return math.exp(-(n - BOUNDARY_SUBSET_SIZE) / BOUNDARY_DECAY_TAU)


# ---------------------------------------------------------------------------
# PROVISIONAL_CONFIDENCE_V1
# ---------------------------------------------------------------------------


def provisional_confidence_calculate(
    population: PopulationSnapshot,
    method_1_result=None,
) -> ConfidenceResult:
    """Compute ``PROVISIONAL_CONFIDENCE_V1`` (Part D2).

    Applies only when ``1 <= N < 20`` and Method 1 is READY.  ``method_1_result``
    may be a ``MethodResult``; when omitted the caller must have verified
    readiness already.
    """
    n = population.raw_n
    if not (1 <= n < 20):
        return ConfidenceResult(
            version=PROVISIONAL_CONFIDENCE_VERSION,
            status="NOT_APPLICABLE",
            diagnostics={"validated_population_size": n},
        )
    if method_1_result is not None and not method_1_result.is_ready:
        return ConfidenceResult(
            version=PROVISIONAL_CONFIDENCE_VERSION,
            status="NOT_READY",
            diagnostics={
                "validated_population_size": n,
                "method_1_status": method_1_result.status,
            },
        )

    # Qn-style Aitchison pairwise dispersion (Part D2.4).
    if n == 1:
        q_a = 0.0
    else:
        h = n // 2 + 1
        k = h * (h - 1) // 2
        distances: list[float] = []
        for i in range(n):
            z_i = joint_ilr(
                population.submissions[i].challenge,
                population.submissions[i].reward,
            )
            for j in range(i + 1, n):
                z_j = joint_ilr(
                    population.submissions[j].challenge,
                    population.submissions[j].reward,
                )
                d_c = math.hypot(z_i[0] - z_j[0], z_i[1] - z_j[1])
                d_r = math.hypot(z_i[2] - z_j[2], z_i[3] - z_j[3])
                distances.append(math.sqrt((d_c * d_c + d_r * d_r) / 2.0))
        ordered = sorted(distances)
        factor = PROVISIONAL_QN_FACTORS[n]
        q_a = PROVISIONAL_QN_FACTOR * factor * ordered[k - 1]

    # Whole-population agreement factor (Part D2.5).
    e_p = 2.0 ** (-((q_a / PROVISIONAL_Q_HALF) ** 2))

    # Saturating sample-support ceiling (Part D2.6).
    s_n = (
        PROVISIONAL_S_MAX
        * (1.0 - math.exp(-n / PROVISIONAL_S_EXPONENT))
        / PROVISIONAL_S_DENOMINATOR
    )

    # Authoritative role evidence (Part D2.7).
    authoritative_indices = _authoritative_members(population)
    h_a = sum(
        _AUTHORITATIVE_WEIGHTS[population.submissions[i].role]
        for i in authoritative_indices
    )
    e_r = 1.0 + float(PROVISIONAL_ROLE_UPLIFT) * (
        1.0 - math.exp(-h_a / PROVISIONAL_H_0)
    )

    weights = [
        _AUTHORITATIVE_WEIGHTS[population.submissions[i].role]
        for i in authoritative_indices
    ]
    n_eff = _kish_effective_n(weights)

    # Provisional population center (Part D2.9): equal-user ilr center.
    z_p_prov = _mean_vectors(
        [
            joint_ilr(
                population.submissions[i].challenge,
                population.submissions[i].reward,
            )
            for i in range(n)
        ]
    )

    d_a = 0.0
    v_a = 0.0
    if authoritative_indices:
        vectors = [
            joint_ilr(
                population.submissions[i].challenge,
                population.submissions[i].reward,
            )
            for i in authoritative_indices
        ]
        z_a = _weighted_center(vectors, weights)
        _, _, d_a = _combined_deviation(z_a, z_p_prov)
        if len(authoritative_indices) >= 2:
            total = sum(weights)
            numerator = sum(
                weights[index]
                * sum((vectors[index][j] - z_a[j]) ** 2 for j in range(4))
                for index in range(len(authoritative_indices))
            )
            v_a = numerator / (4.0 * total)

    # Authoritative coherence factor (Part D2.13).
    if authoritative_indices:
        e_c_prov = math.exp(
            -CONFIDENCE_GAMMA_D
            * d_a
            * d_a
            / (CONFIDENCE_D_0**2 + v_a / max(n_eff, 1.0))
            - CONFIDENCE_GAMMA_V
            * (n_eff / (n_eff + CONFIDENCE_N_V))
            * v_a
            / (CONFIDENCE_V_0**2)
        )
    else:
        e_c_prov = 1.0

    level = min(PROVISIONAL_MAX, s_n * e_r * e_p * e_c_prov)
    if not math.isfinite(level):
        return ConfidenceResult(
            version=PROVISIONAL_CONFIDENCE_VERSION,
            status=CALCULATION_ERROR,
            diagnostics={"validated_population_size": n},
        )
    level = min(PROVISIONAL_MAX, max(0.0, level))

    return ConfidenceResult(
        version=PROVISIONAL_CONFIDENCE_VERSION,
        status=PROVISIONAL_READY,
        level_raw=level,
        level_displayed=round(level, 1),
        label=confidence_label(level),
        diagnostics={
            "qn_style_aitchison_dispersion": q_a,
            "whole_population_agreement_factor": e_p,
            "sample_support_ceiling": s_n,
            "role_evidence_factor": e_r,
            "authoritative_coherence_factor": e_c_prov,
            "authoritative_combined_deviation": d_a,
            "authoritative_internal_variance": v_a,
            "authoritative_effective_sample_size": n_eff,
            "authoritative_role_mass": h_a,
            "validated_population_size": n,
            "finite_sample_factor": (
                PROVISIONAL_QN_FACTORS[n] if 2 <= n < 20 else None
            ),
        },
    )


def _mean_vectors(vectors: list[tuple[float, ...]]) -> tuple[float, ...]:
    count = len(vectors)
    return tuple(sum(v[j] for v in vectors) / count for j in range(4))


# ---------------------------------------------------------------------------
# BOUNDARY_CONTINUITY_V1
# ---------------------------------------------------------------------------


def _confidence_through_resilience_for_set(
    population: PopulationSnapshot,
) -> tuple[float, bool]:
    """C20 for a 20-submission set: base + resilience, no BHPCM bootstrap."""
    m2 = method2_calculate(population)
    m3 = method3_calculate(population)
    if not (m2.is_ready and m3.is_ready):
        return 0.0, False
    base = confidence_base_calculate(
        population,
        m2.raw_challenge,
        m2.raw_reward,
        m3.raw_challenge,
        m3.raw_reward,
    )
    if not base.is_ready or base.level_raw is None:
        return 0.0, False
    return resilience_apply(base.level_raw, population.raw_n).level, True


def _leave_one_out_provisional(
    population: PopulationSnapshot,
) -> tuple[list[float], int]:
    """Provisional confidences over the N=20 leave-one-out sets."""
    n = population.raw_n
    ready_values: list[float] = []
    for j in range(n):
        loo = PopulationSnapshot(
            submissions=tuple(population.submissions[i] for i in range(n) if i != j)
        )
        m1 = method1_calculate(loo)
        if not m1.is_ready:
            continue
        provisional = provisional_confidence_calculate(loo, m1)
        if (
            provisional.status == PROVISIONAL_READY
            and provisional.level_raw is not None
        ):
            ready_values.append(provisional.level_raw)
    return ready_values, n


def _calibrate_20_submission_set(
    population: PopulationSnapshot,
) -> tuple[bool, float]:
    """Delta_20 for one 20-submission calibration set (Parts D3.2/D3.3.3)."""
    c20, ready = _confidence_through_resilience_for_set(population)
    if not ready:
        return False, 0.0
    loo_values, _ = _leave_one_out_provisional(population)
    if len(loo_values) < BOUNDARY_MIN_READY_LOO:
        return False, 0.0
    c19_star = _median(loo_values)
    return True, max(0.0, c19_star - c20)


def boundary_calibrate(
    population: PopulationSnapshot,
    *,
    game_identifier: str,
) -> BoundaryCalibrationData:
    """Compute the static ``BOUNDARY_CONTINUITY_V1`` constant.

    Only called at the calibration moment: the Game either crossed from
    N < 20 to N >= 20 under the current version, or the version was deployed
    while the Game already had N > 20 (Part D3.3).
    """
    n = population.raw_n
    seed_or_stream = (
        f"BOUNDARY_SUBSAMPLE_V1:{MASTER_VERSION}:{game_identifier}:"
        f"{population.population_hash}:{BOUNDARY_SEED}"
    )

    if n == BOUNDARY_SUBSET_SIZE:
        ready, delta = _calibrate_20_submission_set(population)
        status = READY if ready else BOUNDARY_CALIBRATION_UNAVAILABLE
        return BoundaryCalibrationData(
            status=status,
            delta=delta if ready else 0.0,
            calibration_population_hash=population.population_hash,
            population_size=n,
            subset_count_attempted=1,
            subset_count_ready=1 if ready else 0,
            sampler_version=BOUNDARY_SAMPLER_VERSION,
            seed_or_stream=seed_or_stream,
        )

    # N > 20: subset-based calibration (Part D3.3.3).
    total_subsets = math.comb(n, BOUNDARY_SUBSET_SIZE)
    if total_subsets <= BOUNDARY_MAX_SUBSETS:
        subset_iterators = list(combinations(range(n), BOUNDARY_SUBSET_SIZE))
    else:
        rng = random.Random(seed_or_stream)
        chosen: set[tuple[int, ...]] = set()
        drawn: list[tuple[int, ...]] = []
        while len(drawn) < BOUNDARY_MAX_SUBSETS:
            candidate = tuple(sorted(rng.sample(range(n), BOUNDARY_SUBSET_SIZE)))
            if candidate not in chosen:
                chosen.add(candidate)
                drawn.append(candidate)
        subset_iterators = drawn

    attempted = len(subset_iterators)
    ready_count = 0
    deltas: list[float] = []
    for indices in subset_iterators:
        subset = PopulationSnapshot(
            submissions=tuple(population.submissions[i] for i in indices)
        )
        ready, delta = _calibrate_20_submission_set(subset)
        if ready:
            ready_count += 1
            deltas.append(delta)

    threshold = max(1, math.ceil(BOUNDARY_READY_FRACTION * attempted))
    if ready_count < threshold:
        return BoundaryCalibrationData(
            status=BOUNDARY_CALIBRATION_UNAVAILABLE,
            delta=0.0,
            calibration_population_hash=population.population_hash,
            population_size=n,
            subset_count_attempted=attempted,
            subset_count_ready=ready_count,
            sampler_version=BOUNDARY_SAMPLER_VERSION,
            seed_or_stream=seed_or_stream,
        )

    delta_star = _median(deltas)
    return BoundaryCalibrationData(
        status=READY,
        delta=delta_star,
        calibration_population_hash=population.population_hash,
        population_size=n,
        subset_count_attempted=attempted,
        subset_count_ready=ready_count,
        sampler_version=BOUNDARY_SAMPLER_VERSION,
        seed_or_stream=seed_or_stream,
    )


def boundary_final_confidence(c_res: float, delta: float, n: int) -> dict[str, float]:
    """C_final = min(100, C_res + delta * g(N)) (Part D3.5)."""
    decay = boundary_decay(delta, n)
    applied = delta * decay
    return {
        "boundary_decay_factor": decay,
        "boundary_adjustment_applied": applied,
        "confidence_final_unrounded": min(100.0, c_res + applied),
    }


__all__ = [
    "BOUNDARY_CALIBRATION_UNAVAILABLE",
    "BoundaryCalibrationData",
    "ConfidenceBaseResult",
    "ResilienceResult",
    "boundary_calibrate",
    "boundary_decay",
    "boundary_final_confidence",
    "confidence_base_calculate",
    "provisional_confidence_calculate",
    "resilience_apply",
]
