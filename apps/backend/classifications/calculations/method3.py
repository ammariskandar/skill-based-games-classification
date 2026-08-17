"""
Method 3 — six independent one-dimensional LoOP analyses (Parts XVI-XVIII).

Role-neutral.  Tie-inclusive k-neighborhoods, probabilistic distances with
lambda = 3, PLOF/nPLOF/erf normalization, the degenerate-density branches,
the strict > 0.75 flag, the universal 2-of-6 whole-submission rule, and the
survivor arithmetic mean.  Deterministic; no randomized component.
"""

from __future__ import annotations

import math

from classifications.calculations.constants import (
    LOOP_K,
    LOOP_LAMBDA,
    LOOP_MIN_N,
    LOOP_TAU,
)
from classifications.calculations.errors import CalculationInvariantError
from classifications.calculations.profiles import (
    PopulationSnapshot,
    Profile,
    analysis_values,
)
from classifications.calculations.reconciliation import largest_remainder_profile
from classifications.calculations.results import (
    CALCULATION_ERROR,
    INSUFFICIENT_SAMPLE_FOR_LOOP,
    NO_SUBMISSIONS,
    NO_SURVIVING_SUBMISSIONS,
    READY,
    MethodResult,
)

_SQRT2 = math.sqrt(2.0)


def _erf(z: float) -> float:
    return math.erf(z)


def _dimension_loop_scores(values: list[float]) -> list[float]:
    """LoOP scores for one dimension under the frozen degenerate rules.

    Returns a list parallel to ``values``.  Raises
    ``CalculationInvariantError`` only for the undefined-branch condition of
    section 92; all explicitly defined degenerate branches resolve here.
    """
    n = len(values)
    if all(v == values[0] for v in values):
        # Entire dimension constant (Part XVII.88).
        return [0.0] * n

    distances: list[list[float]] = [
        [abs(values[i] - values[j]) for j in range(n) if j != i] for i in range(n)
    ]

    # Tie-inclusive k-neighborhoods (Part XVI.81).
    neighborhoods: list[list[int]] = []
    for i in range(n):
        ordered = sorted(distances[i])
        r_ik = ordered[LOOP_K - 1]
        neighborhood = [
            j for j in range(n) if j != i and abs(values[i] - values[j]) <= r_ik
        ]
        neighborhoods.append(neighborhood)

    # Local standard distances and probabilistic distances (Parts XVI.82-83).
    sigmas: list[float] = []
    for i in range(n):
        total = sum(abs(values[i] - values[j]) ** 2 for j in neighborhoods[i])
        sigmas.append(math.sqrt(total / len(neighborhoods[i])))
    pdists = [LOOP_LAMBDA * sigma for sigma in sigmas]

    # Neighbor reference distances (Part XVI.84).
    neighbor_means: list[float] = []
    for i in range(n):
        neighbor_means.append(
            sum(pdists[j] for j in neighborhoods[i]) / len(neighborhoods[i])
        )

    # PLOF with degenerate branches (Parts XVI.85, XVII.89-90).
    plof: list[float | None] = [None] * n
    direct_one: list[bool] = [False] * n
    finite_indices: list[int] = []
    for i in range(n):
        if pdists[i] == 0.0 and neighbor_means[i] == 0.0:
            plof[i] = 0.0
        elif pdists[i] > 0.0 and neighbor_means[i] == 0.0:
            # Maximally separated from a zero-spread reference set.
            direct_one[i] = True
            plof[i] = None  # excluded from the finite set
        else:
            # neighbor_means[i] > 0 (regular non-degenerate branch).
            plof[i] = pdists[i] / neighbor_means[i] - 1.0

    for i in range(n):
        if plof[i] is not None:
            finite_indices.append(i)

    # nPLOF and LoOP (Parts XVI.86-87, XVII.91).
    finite_values: list[float] = []
    for i in finite_indices:
        value = plof[i]
        if value is None:
            continue
        finite_values.append(value)

    if finite_values:
        mean_square = sum(v * v for v in finite_values) / len(finite_values)
        nplof = LOOP_LAMBDA * math.sqrt(mean_square)
    else:
        nplof = 0.0

    scores: list[float] = []
    for i in range(n):
        if direct_one[i]:
            scores.append(1.0)
            continue
        value = plof[i]
        if value is None:
            # Undefined branch not covered by the explicit degenerate rules.
            raise CalculationInvariantError(
                "Method 3 produced a non-finite quantity outside the defined branches"
            )
        if nplof == 0.0:
            scores.append(0.0)
            continue
        argument = value / (nplof * _SQRT2)
        if not math.isfinite(argument):
            raise CalculationInvariantError(
                "Method 3 produced a non-finite quantity outside the defined branches"
            )
        scores.append(max(0.0, _erf(argument)))

    for score in scores:
        if not math.isfinite(score):
            raise CalculationInvariantError(
                "Method 3 produced a non-finite quantity outside the defined branches"
            )
    return scores


def method3_calculate(population: PopulationSnapshot) -> MethodResult:
    """Run Method 3 on a canonical input population."""
    n = population.raw_n
    submissions = population.submissions
    if n == 0:
        return MethodResult(
            method="method_3", status=NO_SUBMISSIONS, diagnostics={"raw_n": 0}
        )
    if n < LOOP_MIN_N:
        return MethodResult(
            method="method_3",
            status=INSUFFICIENT_SAMPLE_FOR_LOOP,
            diagnostics={"raw_n": n},
        )

    flags: list[list[bool]] = []
    try:
        for dim_index in range(6):
            values = [analysis_values(submissions[i])[dim_index] for i in range(n)]
            scores = _dimension_loop_scores(values)
            flags.append([score > LOOP_TAU for score in scores])
    except CalculationInvariantError as exc:
        return MethodResult(
            method="method_3",
            status=CALCULATION_ERROR,
            diagnostics={"raw_n": n, "error": str(exc)},
        )

    retained = [sum(1 for dim in flags if dim[i]) <= 1 for i in range(n)]
    survivor_indices = [i for i in range(n) if retained[i]]

    if not survivor_indices:
        return MethodResult(
            method="method_3",
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
        method="method_3",
        status=READY,
        raw_challenge=raw_challenge,
        raw_reward=raw_reward,
        integer_challenge=largest_remainder_profile(raw_challenge),
        integer_reward=largest_remainder_profile(raw_reward),
        survivors=len(survivor_indices),
        rejected=n - len(survivor_indices),
        diagnostics={
            "raw_n": n,
            "k": LOOP_K,
            "lambda": LOOP_LAMBDA,
            "threshold": LOOP_TAU,
            "scalar_flag_counts": [sum(dim) for dim in flags],
        },
    )


__all__ = ["method3_calculate"]
