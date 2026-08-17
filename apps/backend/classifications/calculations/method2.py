"""
Method 2 — six independent one-dimensional Isolation Forests (Part XV).

512 trees per dimension, subsample size min(256, N), height limit
ceil(log2 psi), threshold 0.60 (strict), deterministic frozen seed 42.
Role-neutral; every surviving submission has equal weight one.
"""

from __future__ import annotations

import math
import random

from classifications.calculations.constants import (
    IFOREST_MIN_N,
    IFOREST_SEED,
    IFOREST_SUBSAMPLE_MAX,
    IFOREST_TAU,
    IFOREST_TREES,
)
from classifications.calculations.profiles import (
    PopulationSnapshot,
    Profile,
    analysis_values,
)
from classifications.calculations.reconciliation import largest_remainder_profile
from classifications.calculations.results import (
    INSUFFICIENT_SAMPLE_FOR_IFOREST,
    NO_SUBMISSIONS,
    NO_SURVIVING_SUBMISSIONS,
    READY,
    MethodResult,
)

# Precomputed c(n) values (Part XV.69) for every reachable n.
_C_TABLE: list[float] = [0.0, 0.0]
_HARMONIC = 0.0
for _n in range(2, IFOREST_SUBSAMPLE_MAX + 2):
    _HARMONIC += 1.0 / (_n - 1)
    _C_TABLE.append(2.0 * _HARMONIC - 2.0 * (_n - 1) / _n)


def expected_path_adjustment(n: int) -> float:
    """c(n) = 2H_{n-1} - 2(n-1)/n for n >= 2, else 0."""
    if n <= 1:
        return 0.0
    if n < len(_C_TABLE):
        return _C_TABLE[n]
    harmonic = sum(1.0 / j for j in range(1, n))
    return 2.0 * harmonic - 2.0 * (n - 1) / n


def method2_calculate(population: PopulationSnapshot) -> MethodResult:
    """Run Method 2 on a canonical input population."""
    n = population.raw_n
    submissions = population.submissions
    if n == 0:
        return MethodResult(
            method="method_2", status=NO_SUBMISSIONS, diagnostics={"raw_n": 0}
        )
    if n < IFOREST_MIN_N:
        return MethodResult(
            method="method_2",
            status=INSUFFICIENT_SAMPLE_FOR_IFOREST,
            diagnostics={"raw_n": n},
        )

    psi = min(IFOREST_SUBSAMPLE_MAX, n)
    height_limit = math.ceil(math.log2(psi))
    reference = expected_path_adjustment(psi)

    flags: list[list[bool]] = []
    score_matrix: list[list[float]] = []
    for dim_index in range(6):
        values = [analysis_values(submissions[i])[dim_index] for i in range(n)]
        scores = _dimension_scores(values, psi, height_limit, reference, dim_index)
        score_matrix.append(scores)
        flags.append([score > IFOREST_TAU for score in scores])

    retained = [sum(1 for dim in flags if dim[i]) <= 1 for i in range(n)]
    survivor_indices = [i for i in range(n) if retained[i]]

    if not survivor_indices:
        return MethodResult(
            method="method_2",
            status=NO_SURVIVING_SUBMISSIONS,
            diagnostics={"raw_n": n, "rejected": n, "survivors": 0},
        )

    raw_challenge = Profile(
        micro=sum(submissions[i].challenge.micro for i in survivor_indices)
        / len(survivor_indices),
        macro=sum(submissions[i].challenge.macro for i in survivor_indices)
        / len(survivor_indices),
        mystiko=sum(submissions[i].challenge.mystiko for i in survivor_indices)
        / len(survivor_indices),
    )
    raw_reward = Profile(
        micro=sum(submissions[i].reward.micro for i in survivor_indices)
        / len(survivor_indices),
        macro=sum(submissions[i].reward.macro for i in survivor_indices)
        / len(survivor_indices),
        mystiko=sum(submissions[i].reward.mystiko for i in survivor_indices)
        / len(survivor_indices),
    )

    return MethodResult(
        method="method_2",
        status=READY,
        raw_challenge=raw_challenge,
        raw_reward=raw_reward,
        integer_challenge=largest_remainder_profile(raw_challenge),
        integer_reward=largest_remainder_profile(raw_reward),
        survivors=len(survivor_indices),
        rejected=n - len(survivor_indices),
        diagnostics={
            "raw_n": n,
            "trees": IFOREST_TREES,
            "subsample_size": psi,
            "height_limit": height_limit,
            "threshold": IFOREST_TAU,
            "seed": IFOREST_SEED,
            "scalar_flag_counts": [sum(dim) for dim in flags],
        },
    )


def _dimension_scores(
    values: list[float], psi: int, height_limit: int, reference: float, dim_index: int
) -> list[float]:
    """Anomaly scores for one dimension under the frozen randomization schedule."""
    n = len(values)
    if all(v == values[0] for v in values):
        # Constant dimension (Part XV.72): every tree terminates at its root,
        # every observation scores exactly 0.5, nothing is flagged.
        return [0.5] * n

    rng = random.Random((IFOREST_SEED * 31) + dim_index)
    path_sums = [0.0] * n
    for _ in range(IFOREST_TREES):
        # Sorting the subsample is order-irrelevant to the tree (splits are
        # chosen from min/max and partitions by value), so this produces the
        # identical tree while enabling O(psi log psi) construction below.
        sample = sorted(rng.sample(values, psi))
        tree = _build_tree(
            sample, 0, len(sample), rng, depth=0, height_limit=height_limit
        )
        for i, value in enumerate(values):
            path_sums[i] += _path_length(tree, value)
    return [2.0 ** (-path_sum / IFOREST_TREES / reference) for path_sum in path_sums]


def _build_tree(
    sorted_values: list[float],
    lo: int,
    hi: int,
    rng: random.Random,
    depth: int,
    height_limit: int,
):
    """One 1-D isolation tree over ``sorted_values[lo:hi]``.

    The frozen randomization schedule is consumed in exactly the same
    depth-first order as the specification's recursive partition: one
    ``rng.uniform(z_min, z_max)`` per internal node.  ``bisect_left`` is the
    identity-equivalent of the ``value < split`` partition, so the resulting
    tree (split values, leaf sizes, nesting) is byte-for-byte identical to a
    linear-scan implementation while avoiding repeated list slicing.
    """
    count = hi - lo
    if (
        depth >= height_limit
        or count <= 1
        or sorted_values[lo] == sorted_values[hi - 1]
    ):
        return ("leaf", depth, count)

    z_min = sorted_values[lo]
    z_max = sorted_values[hi - 1]
    split = rng.uniform(z_min, z_max)
    if split == z_min:
        # Both children must be non-empty (Part XV.68); this guards the
        # measure-zero uniform edge without changing the distribution.
        split = (z_min + z_max) / 2.0
    mid = _bisect_left(sorted_values, split, lo, hi)
    return (
        "node",
        split,
        _build_tree(sorted_values, lo, mid, rng, depth + 1, height_limit),
        _build_tree(sorted_values, mid, hi, rng, depth + 1, height_limit),
    )


def _bisect_left(values: list[float], target: float, lo: int, hi: int) -> int:
    """Inlined ``bisect_left`` for the local import surface."""
    while lo < hi:
        mid = (lo + hi) // 2
        if values[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _path_length(tree, value: float) -> float:
    """h(x) = e + c(n_e) for one observation through one tree."""
    node = tree
    while True:
        kind = node[0]
        if kind == "leaf":
            _, depth, count = node
            return depth + expected_path_adjustment(count)
        _, split, left, right = node
        node = left if value < split else right


__all__ = ["expected_path_adjustment", "method2_calculate"]
