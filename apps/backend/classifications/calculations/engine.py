"""
End-to-end derived-classification engine — SBGC-65 (Part H).

Branches on the raw validated population size:

- N = 0            -> NO_SUBMISSIONS, no scores;
- 1 <= N < 20      -> Method 1 + PROVISIONAL_CONFIDENCE_V1 (provisional regime);
- N >= 20          -> Methods 1/2/3 + BHPCM_V1 + CONFIDENCE_V2 (unified regime).

Pure domain logic: no Django imports, no persistence.  The persistence
service maps :class:`GameCalculationResult` onto versioned snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from classifications.calculations.bhpcm import BHPCMResult, bhpcm_calculate
from classifications.calculations.confidence import (
    BoundaryCalibrationData,
    ConfidenceBaseResult,
    ResilienceResult,
    boundary_calibrate,
    boundary_final_confidence,
    confidence_base_calculate,
    provisional_confidence_calculate,
    resilience_apply,
)
from classifications.calculations.constants import (
    BHPCM_VERSION,
    CONFIDENCE_BASE_VERSION,
    CONFIDENCE_FINAL_VERSION,
    CONFIDENCE_RESILIENCE_VERSION,
    METHODS_VERSION,
    PROVISIONAL_CONFIDENCE_VERSION,
)
from classifications.calculations.method1 import method1_calculate
from classifications.calculations.method2 import method2_calculate
from classifications.calculations.method3 import method3_calculate
from classifications.calculations.profiles import PopulationSnapshot, Profile
from classifications.calculations.results import (
    CALCULATION_ERROR,
    NO_SUBMISSIONS,
    READY,
    REGIME_PROVISIONAL,
    REGIME_UNIFIED,
    ConfidenceResult,
    MethodResult,
    confidence_label,
)


@dataclass(frozen=True)
class GameCalculationResult:
    """Everything one Game/epoch calculation produced.

    ``integer_challenge`` / ``integer_reward`` are the product-facing
    display profiles in (micro, macro, mystiko) order.  All non-READY
    outcomes have null display profiles.
    """

    regime: str
    status: str
    raw_n: int
    method_1: MethodResult | None = None
    method_2: MethodResult | None = None
    method_3: MethodResult | None = None
    bhpcm: BHPCMResult | None = None
    confidence_base: ConfidenceBaseResult | None = None
    resilience: ResilienceResult | None = None
    boundary_calibration: BoundaryCalibrationData | None = None
    boundary_final: dict[str, float] | None = None
    confidence: ConfidenceResult | None = None
    integer_challenge: tuple[int, int, int] | None = None
    integer_reward: tuple[int, int, int] | None = None
    raw_challenge: Profile | None = None
    raw_reward: Profile | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == READY


def calculate_game(
    population: PopulationSnapshot,
    *,
    game_identifier: str = "",
    stored_boundary: BoundaryCalibrationData | None = None,
    bootstrap_replicates: int | None = None,
    governance_draws: int | None = None,
) -> GameCalculationResult:
    """Run the complete frozen calculation contract for one Game."""
    n = population.raw_n

    if n == 0:
        return GameCalculationResult(
            regime=REGIME_UNIFIED,
            status=NO_SUBMISSIONS,
            raw_n=0,
            diagnostics={"input_population_hash": population.population_hash},
        )

    if n < 20:
        return _provisional_regime(population)

    return _unified_regime(
        population,
        game_identifier=game_identifier,
        stored_boundary=stored_boundary,
        bootstrap_replicates=bootstrap_replicates,
        governance_draws=governance_draws,
    )


def _provisional_regime(population: PopulationSnapshot) -> GameCalculationResult:
    n = population.raw_n
    method_1 = method1_calculate(population)
    if not method_1.is_ready:
        return GameCalculationResult(
            regime=REGIME_PROVISIONAL,
            status=method_1.status,
            raw_n=n,
            method_1=method_1,
            diagnostics={"input_population_hash": population.population_hash},
        )

    confidence = provisional_confidence_calculate(population, method_1)
    assert method_1.integer_challenge is not None
    assert method_1.integer_reward is not None
    assert method_1.raw_challenge is not None
    assert method_1.raw_reward is not None
    return GameCalculationResult(
        regime=REGIME_PROVISIONAL,
        status=READY,
        raw_n=n,
        method_1=method_1,
        confidence=confidence,
        integer_challenge=method_1.integer_challenge,
        integer_reward=method_1.integer_reward,
        raw_challenge=method_1.raw_challenge,
        raw_reward=method_1.raw_reward,
        diagnostics={"input_population_hash": population.population_hash},
    )


def _unified_regime(
    population: PopulationSnapshot,
    *,
    game_identifier: str,
    stored_boundary: BoundaryCalibrationData | None,
    bootstrap_replicates: int | None,
    governance_draws: int | None,
) -> GameCalculationResult:
    n = population.raw_n
    method_1 = method1_calculate(population)
    method_2 = method2_calculate(population)
    method_3 = method3_calculate(population)

    bhpcm = bhpcm_calculate(
        population,
        (method_1, method_2, method_3),
        bootstrap_replicates=bootstrap_replicates,
        governance_draws=governance_draws,
    )

    base = GameCalculationResult(
        regime=REGIME_UNIFIED,
        status=bhpcm.status,
        raw_n=n,
        method_1=method_1,
        method_2=method_2,
        method_3=method_3,
        bhpcm=bhpcm,
        diagnostics={"input_population_hash": population.population_hash},
    )
    if not bhpcm.is_ready:
        return base

    assert bhpcm.official_raw_challenge is not None
    assert bhpcm.official_raw_reward is not None
    assert method_2.raw_challenge is not None and method_2.raw_reward is not None
    assert method_3.raw_challenge is not None and method_3.raw_reward is not None

    base_result = confidence_base_calculate(
        population,
        method_2.raw_challenge,
        method_2.raw_reward,
        method_3.raw_challenge,
        method_3.raw_reward,
    )
    if base_result.status == CALCULATION_ERROR or base_result.level_raw is None:
        return GameCalculationResult(
            regime=REGIME_UNIFIED,
            status=CALCULATION_ERROR,
            raw_n=n,
            method_1=method_1,
            method_2=method_2,
            method_3=method_3,
            bhpcm=bhpcm,
            confidence_base=base_result,
            diagnostics={"input_population_hash": population.population_hash},
        )

    resilience = resilience_apply(base_result.level_raw, n)

    # Boundary continuity: calibrate only at the calibration moment.
    boundary = stored_boundary
    if boundary is None:
        boundary = boundary_calibrate(population, game_identifier=game_identifier)

    boundary_final = boundary_final_confidence(resilience.level, boundary.delta, n)
    final_level = boundary_final["confidence_final_unrounded"]

    confidence = ConfidenceResult(
        version=CONFIDENCE_FINAL_VERSION,
        status=READY,
        level_raw=final_level,
        level_displayed=round(final_level, 1),
        label=confidence_label(final_level),
        diagnostics={
            "confidence_base": base_result.level_raw,
            "confidence_base_version": CONFIDENCE_BASE_VERSION,
            "population_resilience_capacity": resilience.capacity,
            "population_resilience_applied": resilience.applied,
            "confidence_after_resilience": resilience.level,
            "confidence_resilience_version": CONFIDENCE_RESILIENCE_VERSION,
            "boundary_calibration_status": boundary.status,
            "boundary_delta": boundary.delta,
            "boundary_decay_factor": boundary_final["boundary_decay_factor"],
            "boundary_adjustment_applied": boundary_final[
                "boundary_adjustment_applied"
            ],
            "confidence_final_unrounded": final_level,
            "confidence_final_displayed": round(final_level, 1),
        },
    )

    return GameCalculationResult(
        regime=REGIME_UNIFIED,
        status=READY,
        raw_n=n,
        method_1=method_1,
        method_2=method_2,
        method_3=method_3,
        bhpcm=bhpcm,
        confidence_base=base_result,
        resilience=resilience,
        boundary_calibration=boundary,
        boundary_final=boundary_final,
        confidence=confidence,
        integer_challenge=bhpcm.integer_challenge,
        integer_reward=bhpcm.integer_reward,
        raw_challenge=bhpcm.official_raw_challenge,
        raw_reward=bhpcm.official_raw_reward,
        diagnostics={
            "input_population_hash": population.population_hash,
            "methods_version": METHODS_VERSION,
            "bhpcm_version": BHPCM_VERSION,
            "confidence_base_version": CONFIDENCE_BASE_VERSION,
            "confidence_resilience_version": CONFIDENCE_RESILIENCE_VERSION,
            "provisional_confidence_version": PROVISIONAL_CONFIDENCE_VERSION,
            "confidence_final_version": CONFIDENCE_FINAL_VERSION,
        },
    )


__all__ = [
    "GameCalculationResult",
    "calculate_game",
]
