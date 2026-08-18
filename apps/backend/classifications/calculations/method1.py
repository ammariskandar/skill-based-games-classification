"""
Method 1 — role-aware anchored aggregation (Parts V-XIV).

Mean/sample-SD detector (1A), median/S_n detector (1B), detector-agreement
weights, anchor hierarchy, normalized role/anchor aggregation, and high-N
anchor-reliability redistribution.  Frozen constants only.
"""

from __future__ import annotations

import math
from statistics import mean

from classifications.calculations.constants import (
    METHOD1_ANCHOR_W_BOTH,
    METHOD1_ANCHOR_W_NEITHER,
    METHOD1_ANCHOR_W_ONE,
    METHOD1_COMMUNITY_FALLBACK_CAP,
    METHOD1_COMMUNITY_FALLBACK_CAP_HIGH,
    METHOD1_COMMUNITY_FALLBACK_MIN_N,
    METHOD1_DELTA,
    METHOD1_HIGH_N_ANCHOR,
    METHOD1_K_A_HIGH,
    METHOD1_K_A_HIGH_THRESHOLD,
    METHOD1_K_A_LOW,
    METHOD1_K_B,
    METHOD1_MIN_N,
    METHOD1_SN_FACTOR,
    ROLE_BASE_WEIGHTS,
    ROLE_COMMUNITY,
    ROLE_COMMUNITY_LEADER,
    ROLE_MODERATOR,
    ROLE_SUPERUSER,
)
from classifications.calculations.profiles import PopulationSnapshot, Profile
from classifications.calculations.reconciliation import largest_remainder_profile
from classifications.calculations.results import (
    INSUFFICIENT_ANCHOR,
    NO_SUBMISSIONS,
    READY,
    MethodResult,
)

_ORDINARY_ROLES = (ROLE_MODERATOR, ROLE_COMMUNITY_LEADER, ROLE_COMMUNITY)

_DIMENSIONS = (
    ("challenge", "micro"),
    ("challenge", "mystiko"),
    ("challenge", "macro"),
    ("reward", "micro"),
    ("reward", "mystiko"),
    ("reward", "macro"),
)


def population_influence(n: int) -> float:
    """Monotone population influence coefficient c(N) (Part V.15)."""
    if n <= 5:
        return 0.0
    if n <= 25:
        return 0.10 * ((n - 5) / 20)
    if n <= 50:
        return 0.10 + 0.25 * ((n - 25) / 25)
    if n <= 250:
        return 0.35 + 0.50 * ((n - 50) / 200)
    if n <= 400:
        return 0.85
    if n <= 1000:
        return 0.85 + 0.15 * ((n - 400) / 600)
    return 1.0


def median(values: list[float]) -> float:
    """Standard sample median (Part VII.24)."""
    ordered = sorted(values)
    size = len(ordered)
    if size % 2 == 1:
        return ordered[size // 2]
    return (ordered[size // 2 - 1] + ordered[size // 2]) / 2.0


def sn_scale(values: list[float]) -> float:
    """Robust S_n scale = 1.1926 * median_i median_j |x_i - x_j| (Part VII.25)."""
    n = len(values)
    inner = []
    for i in range(n):
        inner.append(median([abs(values[i] - values[j]) for j in range(n)]))
    return METHOD1_SN_FACTOR * median(inner)


def _sample_sd(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mu = mean(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / (n - 1))


def _whole_submission_retain(flags: list[list[bool]]) -> list[bool]:
    """Universal 2-of-6 rule: retain when at most one dimension is flagged."""
    n = len(flags[0]) if flags else 0
    return [sum(1 for dim in flags if dim[i]) <= 1 for i in range(n)]


def method1_calculate(population: PopulationSnapshot) -> MethodResult:
    """Run Method 1 on a canonical input population."""
    n = population.raw_n
    submissions = population.submissions
    if n == 0:
        return MethodResult(
            method="method_1", status=NO_SUBMISSIONS, diagnostics={"raw_n": 0}
        )

    counts = population.role_counts()

    anchor = _select_anchor(n, counts, submissions)
    if anchor is None:
        return MethodResult(
            method="method_1",
            status=INSUFFICIENT_ANCHOR,
            diagnostics={
                "raw_n": n,
                "role_counts": dict(counts),
                "anchor_type": "NONE",
            },
        )
    anchor_indices, anchor_type, c_eff = anchor

    # -- Detectors (single-pass, from the original population) ----------------
    flags_a, flags_b = _detector_flags(submissions, n)
    retained_a = _whole_submission_retain(flags_a)
    retained_b = _whole_submission_retain(flags_b)
    agreement = [(retained_a[i] + retained_b[i]) / 2.0 for i in range(n)]

    anchor_set = set(anchor_indices)

    # -- Anchor profile -------------------------------------------------------
    high_n = n >= METHOD1_HIGH_N_ANCHOR
    rho_a: float | None = None
    if high_n:
        anchor_weights = []
        for i in anchor_indices:
            if retained_a[i] and retained_b[i]:
                anchor_weights.append(METHOD1_ANCHOR_W_BOTH)
            elif retained_a[i] or retained_b[i]:
                anchor_weights.append(METHOD1_ANCHOR_W_ONE)
            else:
                anchor_weights.append(METHOD1_ANCHOR_W_NEITHER)
        rho_a = sum(anchor_weights) / len(anchor_weights)
        anchor_challenge = _weighted_profile(
            [submissions[i].challenge for i in anchor_indices], anchor_weights
        )
        anchor_reward = _weighted_profile(
            [submissions[i].reward for i in anchor_indices], anchor_weights
        )
    else:
        anchor_challenge = _equal_mean_profile(
            [submissions[i].challenge for i in anchor_indices]
        )
        anchor_reward = _equal_mean_profile(
            [submissions[i].reward for i in anchor_indices]
        )

    # -- Ordinary role groups -------------------------------------------------
    participating: dict[str, tuple[Profile, Profile]] = {}
    for role in _ORDINARY_ROLES:
        members = [
            i for i in range(n) if submissions[i].role == role and i not in anchor_set
        ]
        total_weight = sum(agreement[i] for i in members)
        if total_weight <= 0:
            continue
        role_challenge = _agreement_weighted_profile(
            [submissions[i].challenge for i in members],
            [agreement[i] for i in members],
        )
        role_reward = _agreement_weighted_profile(
            [submissions[i].reward for i in members],
            [agreement[i] for i in members],
        )
        participating[role] = (role_challenge, role_reward)

    group_count = 1 + len(participating)
    q_g = {role: float(ROLE_BASE_WEIGHTS[role]) * c_eff for role in participating}

    # -- Normalized aggregation ------------------------------------------------
    if high_n and rho_a is not None:
        raw_challenge, raw_reward, coefficients = _high_n_aggregate(
            anchor_challenge, anchor_reward, participating, q_g, group_count, rho_a
        )
    else:
        raw_challenge, raw_reward, coefficients = _low_n_aggregate(
            anchor_challenge, anchor_reward, participating, q_g, group_count
        )

    integer_challenge = largest_remainder_profile(raw_challenge)
    integer_reward = largest_remainder_profile(raw_reward)

    diagnostics = {
        "raw_n": n,
        "role_counts": dict(counts),
        "population_influence": population_influence(n),
        "effective_population_influence": c_eff,
        "anchor_type": anchor_type,
        "anchor_membership": len(anchor_indices),
        "anchor_reliability": rho_a,
        "method_1a_retained": sum(retained_a),
        "method_1a_rejected": n - sum(retained_a),
        "method_1b_retained": sum(retained_b),
        "method_1b_rejected": n - sum(retained_b),
        "participating_roles": list(participating.keys()),
        "q_g": q_g,
        "group_count": group_count,
        "coefficients": coefficients,
        "anchor_only": len(participating) == 0,
    }

    return MethodResult(
        method="method_1",
        status=READY,
        raw_challenge=raw_challenge,
        raw_reward=raw_reward,
        integer_challenge=integer_challenge,
        integer_reward=integer_reward,
        survivors=n,
        rejected=0,
        diagnostics=diagnostics,
    )


def _select_anchor(
    n: int, counts: dict[str, int], submissions
) -> tuple[list[int], str, float] | None:
    """Resolve the anchor hierarchy (Parts IX/X).

    Returns ``(anchor_indices, anchor_type, c_eff)`` or ``None`` when the
    result is ``INSUFFICIENT_ANCHOR``.
    """
    c = population_influence(n)
    n_su = counts.get(ROLE_SUPERUSER, 0)
    n_mod = counts.get(ROLE_MODERATOR, 0)
    n_cl = counts.get(ROLE_COMMUNITY_LEADER, 0)
    n_com = counts.get(ROLE_COMMUNITY, 0)

    def indices_for(*roles: str) -> list[int]:
        return [i for i in range(n) if submissions[i].role in roles]

    if n_su >= 1:
        return indices_for(ROLE_SUPERUSER), "SUPERUSER", c
    if n_mod >= 2:
        return indices_for(ROLE_MODERATOR), "MODERATOR", c
    if n_mod <= 1 and n_cl >= 5:
        return indices_for(ROLE_COMMUNITY_LEADER), "COMMUNITY_LEADER", c
    if n_mod == 1 and 3 <= n_cl <= 4:
        return (
            indices_for(ROLE_MODERATOR, ROLE_COMMUNITY_LEADER),
            "MIXED",
            c,
        )

    # No privileged anchor -> Community fallback rules (Part IX.37).
    if n < METHOD1_COMMUNITY_FALLBACK_MIN_N or n_com == 0:
        return None
    cap = (
        METHOD1_COMMUNITY_FALLBACK_CAP
        if n <= 400
        else METHOD1_COMMUNITY_FALLBACK_CAP_HIGH
    )
    return (
        indices_for(ROLE_COMMUNITY),
        "COMMUNITY_FALLBACK",
        min(c, float(cap)),
    )


def _detector_flags(submissions, n: int) -> tuple[list[list[bool]], list[list[bool]]]:
    flags_a: list[list[bool]] = []
    flags_b: list[list[bool]] = []
    for profile_name, dimension in _DIMENSIONS:
        values = [
            getattr(
                submissions[i].challenge
                if profile_name == "challenge"
                else submissions[i].reward,
                dimension,
            )
            for i in range(n)
        ]
        if n < METHOD1_MIN_N:
            flags_a.append([False] * n)
            flags_b.append([False] * n)
            continue

        mu = mean(values)
        sd = _sample_sd(values)
        multiplier = (
            METHOD1_K_A_LOW if n < METHOD1_K_A_HIGH_THRESHOLD else METHOD1_K_A_HIGH
        )
        threshold_a = max(multiplier * sd, METHOD1_DELTA)
        flags_a.append([abs(v - mu) > threshold_a for v in values])

        med = median(values)
        robust = sn_scale(values)
        threshold_b = max(METHOD1_K_B * robust, METHOD1_DELTA)
        flags_b.append([abs(v - med) > threshold_b for v in values])
    return flags_a, flags_b


def _equal_mean_profile(profiles: list[Profile]) -> Profile:
    count = len(profiles)
    return Profile(
        micro=sum(p.micro for p in profiles) / count,
        macro=sum(p.macro for p in profiles) / count,
        mystiko=sum(p.mystiko for p in profiles) / count,
    )


def _weighted_profile(profiles: list[Profile], weights: list[float]) -> Profile:
    total = sum(weights)
    return Profile(
        micro=sum(w * p.micro for w, p in zip(weights, profiles, strict=False)) / total,
        macro=sum(w * p.macro for w, p in zip(weights, profiles, strict=False)) / total,
        mystiko=sum(w * p.mystiko for w, p in zip(weights, profiles, strict=False))
        / total,
    )


def _agreement_weighted_profile(
    profiles: list[Profile], weights: list[float]
) -> Profile:
    return _weighted_profile(profiles, weights)


def _blend(role_profile: Profile, anchor: Profile, q: float) -> Profile:
    return Profile(
        micro=q * role_profile.micro + (1 - q) * anchor.micro,
        macro=q * role_profile.macro + (1 - q) * anchor.macro,
        mystiko=q * role_profile.mystiko + (1 - q) * anchor.mystiko,
    )


def _low_n_aggregate(
    anchor_c: Profile,
    anchor_r: Profile,
    participating: dict[str, tuple[Profile, Profile]],
    q_g: dict[str, float],
    group_count: int,
) -> tuple[Profile, Profile, dict]:
    total_c = [anchor_c.micro, anchor_c.macro, anchor_c.mystiko]
    total_r = [anchor_r.micro, anchor_r.macro, anchor_r.mystiko]
    coefficients = {"anchor": 1.0 / group_count}
    for role, (role_c, role_r) in participating.items():
        q = q_g[role]
        block_c = _blend(role_c, anchor_c, q)
        block_r = _blend(role_r, anchor_r, q)
        total_c[0] += block_c.micro
        total_c[1] += block_c.macro
        total_c[2] += block_c.mystiko
        total_r[0] += block_r.micro
        total_r[1] += block_r.macro
        total_r[2] += block_r.mystiko
        coefficients[role] = q / group_count
    raw_c = Profile(
        micro=total_c[0] / group_count,
        macro=total_c[1] / group_count,
        mystiko=total_c[2] / group_count,
    )
    raw_r = Profile(
        micro=total_r[0] / group_count,
        macro=total_r[1] / group_count,
        mystiko=total_r[2] / group_count,
    )
    return raw_c, raw_r, coefficients


def _high_n_aggregate(
    anchor_c: Profile,
    anchor_r: Profile,
    participating: dict[str, tuple[Profile, Profile]],
    q_g: dict[str, float],
    group_count: int,
    rho_a: float,
) -> tuple[Profile, Profile, dict]:
    if not participating:
        # Anchor-only high-N case (Part XII.52): F = A.
        return anchor_c, anchor_r, {"anchor": 1.0, "anchor_only": True, "rho_a": rho_a}

    beta_g = {role: q / group_count for role, q in q_g.items()}
    beta_a = 1.0 - sum(beta_g.values())
    q_total = sum(q_g.values())
    lost = (1.0 - rho_a) * beta_a
    tilde_beta_a = rho_a * beta_a

    sum_c = [
        tilde_beta_a * anchor_c.micro,
        tilde_beta_a * anchor_c.macro,
        tilde_beta_a * anchor_c.mystiko,
    ]
    sum_r = [
        tilde_beta_a * anchor_r.micro,
        tilde_beta_a * anchor_r.macro,
        tilde_beta_a * anchor_r.mystiko,
    ]
    coefficients = {"anchor": tilde_beta_a}
    for role, (role_c, role_r) in participating.items():
        p_g = q_g[role] / q_total
        tilde = beta_g[role] + lost * p_g
        sum_c[0] += tilde * role_c.micro
        sum_c[1] += tilde * role_c.macro
        sum_c[2] += tilde * role_c.mystiko
        sum_r[0] += tilde * role_r.micro
        sum_r[1] += tilde * role_r.macro
        sum_r[2] += tilde * role_r.mystiko
        coefficients[role] = tilde

    raw_c = Profile(sum_c[0], sum_c[1], sum_c[2])
    raw_r = Profile(sum_r[0], sum_r[1], sum_r[2])
    coefficients["rho_a"] = rho_a
    return raw_c, raw_r, coefficients


__all__ = [
    "median",
    "method1_calculate",
    "population_influence",
    "sn_scale",
]
