"""
Confidence-layer tests — Parts C and D — SBGC-65.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from classifications.calculations.confidence import (
    BoundaryCalibrationData,
    boundary_calibrate,
    boundary_decay,
    boundary_final_confidence,
    confidence_base_calculate,
    provisional_confidence_calculate,
    resilience_apply,
)
from classifications.calculations.method1 import method1_calculate
from classifications.calculations.method2 import method2_calculate
from classifications.calculations.method3 import method3_calculate
from classifications.calculations.results import (
    BOUNDARY_CALIBRATION_UNAVAILABLE,
    PROVISIONAL_READY,
    READY,
)
from classifications.tests.calculations_factories import (
    identical_submissions,
    population,
    profile,
    scattered_submissions,
)


def _base(pop):
    m2 = method2_calculate(pop)
    m3 = method3_calculate(pop)
    return confidence_base_calculate(
        pop,
        m2.raw_challenge,
        m2.raw_reward,
        m3.raw_challenge,
        m3.raw_reward,
    )


class ConfidenceBaseTests(SimpleTestCase):
    def test_population_reference_500_neutral_is_95(self):
        # C.23.1: N=500, no authoritative respondents -> exactly 95.
        pop = population(identical_submissions(500))
        result = _base(pop)
        self.assertEqual(result.status, READY)
        assert result.level_raw is not None
        self.assertAlmostEqual(result.level_raw, 95.0, delta=0.1)

    def test_no_authority_reduces_to_population_only(self):
        pop = population(identical_submissions(100))
        result = _base(pop)
        self.assertEqual(result.diagnostics["authoritative_literal_count"], 0)
        self.assertEqual(result.diagnostics["authoritative_effective_sample_size"], 0)
        expected = 100.0 * (
            1.0
            - __import__("math").exp(
                -__import__("math").log(20.0) * (100 / 500) ** 0.60
            )
        )
        assert result.level_raw is not None
        self.assertAlmostEqual(result.level_raw, expected, places=6)

    def test_one_authority_effective_n_one_and_zero_variance(self):
        pop = population(identical_submissions(60, first_roles={0: "superuser"}))
        result = _base(pop)
        self.assertEqual(result.diagnostics["authoritative_literal_count"], 1)
        self.assertAlmostEqual(
            result.diagnostics["authoritative_effective_sample_size"],
            1.0,
            places=9,
        )
        self.assertEqual(result.diagnostics["authoritative_internal_variance"], 0.0)

    def test_equal_weight_effective_n_is_literal_count(self):
        roles = {i: "moderator" for i in range(4)}
        pop = population(identical_submissions(60, first_roles=roles))
        result = _base(pop)
        self.assertAlmostEqual(
            result.diagnostics["authoritative_effective_sample_size"],
            4.0,
            places=9,
        )

    def test_unequal_weights_effective_n_below_literal(self):
        roles = {0: "superuser", 1: "moderator", 2: "community_leader"}
        pop = population(identical_submissions(60, first_roles=roles))
        result = _base(pop)
        self.assertLess(result.diagnostics["authoritative_effective_sample_size"], 3.0)

    def test_weight_rescale_invariance(self):
        # C.22.7: proportional weight rescaling must not change the level.
        # The frozen weights are fixed; verify the Kish formula property.
        from classifications.calculations.confidence import _kish_effective_n

        self.assertAlmostEqual(
            _kish_effective_n([1.0, 0.95, 0.65]),
            _kish_effective_n([2.0, 1.9, 1.3]),
            places=9,
        )

    def test_perfect_alignment_zero_deviation(self):
        pop = population(identical_submissions(60, first_roles={0: "superuser"}))
        result = _base(pop)
        self.assertAlmostEqual(
            result.diagnostics["authoritative_combined_deviation"], 0.0, places=9
        )

    def test_authoritative_disagreement_lowers_confidence(self):
        from classifications.calculations.profiles import SubmissionRecord

        common = profile(45.0, 30.0, 25.0)
        reward = profile(40.0, 30.0, 30.0)
        aligned_su = SubmissionRecord(
            identifier="authority",
            challenge=common,
            reward=reward,
            role="superuser",
        )
        far_su = SubmissionRecord(
            identifier="authority",
            challenge=profile(5.0, 5.0, 90.0),
            reward=profile(5.0, 5.0, 90.0),
            role="superuser",
        )
        crowd = identical_submissions(59, challenge=common, reward=reward)
        aligned = _base(population(crowd + [aligned_su]))
        conflicted = _base(population(crowd + [far_su]))
        self.assertGreater(
            conflicted.diagnostics["authoritative_combined_deviation"],
            aligned.diagnostics["authoritative_combined_deviation"],
        )
        assert conflicted.level_raw is not None
        assert aligned.level_raw is not None
        self.assertLess(conflicted.level_raw, aligned.level_raw)

    def test_zero_population_is_zero(self):
        result = _base(population([]))
        self.assertEqual(result.status, READY)
        assert result.level_raw is not None
        self.assertEqual(result.level_raw, 0.0)

    def test_missing_population_method_not_ready(self):
        pop = population(identical_submissions(30))
        result = confidence_base_calculate(pop, None, None, None, None)
        self.assertEqual(result.status, "NOT_READY")
        self.assertIsNone(result.level_raw)

    def test_range_invariant(self):
        for n in (1, 5, 50, 400, 1000):
            pop = population(
                scattered_submissions(n, roles={0: "superuser"} if n > 0 else None)
            )
            result = _base(pop)
            if result.status == READY:
                assert result.level_raw is not None
                self.assertGreaterEqual(result.level_raw, 0.0)
                self.assertLessEqual(result.level_raw, 100.0)


class ResilienceTests(SimpleTestCase):
    def test_at_or_above_50_unchanged(self):
        result = resilience_apply(55.0, 500)
        self.assertEqual(result.level, 55.0)
        self.assertEqual(result.applied, 0.0)

    def test_below_50_gets_bounded_uplift(self):
        result = resilience_apply(10.0, 401)
        self.assertGreater(result.level, 10.0)
        self.assertLess(result.level, 50.0)

    def test_zero_base_at_maximum_capacity_is_25(self):
        result = resilience_apply(0.0, 401)
        self.assertAlmostEqual(result.level, 25.0, places=6)
        self.assertAlmostEqual(result.capacity, 25.0, places=6)

    def test_small_population_tiny_capacity(self):
        result = resilience_apply(0.0, 1)
        self.assertLess(result.capacity, 0.05)
        self.assertGreaterEqual(result.capacity, 0.0)

    def test_never_reaches_50_when_below(self):
        for n in (1, 5, 10, 50, 250, 400, 401, 1000):
            result = resilience_apply(49.0, n)
            self.assertLess(result.level, 50.0)


class ProvisionalConfidenceTests(SimpleTestCase):
    def test_not_applicable_at_20(self):
        pop = population(identical_submissions(20, first_roles={0: "superuser"}))
        result = provisional_confidence_calculate(pop)
        self.assertEqual(result.status, "NOT_APPLICABLE")

    def test_provisional_ready_below_20_with_anchor(self):
        pop = population(identical_submissions(19, first_roles={0: "superuser"}))
        result = provisional_confidence_calculate(pop, method1_calculate(pop))
        self.assertEqual(result.status, PROVISIONAL_READY)
        self.assertIsNotNone(result.level_raw)

    def test_provisional_never_reaches_50(self):
        pop = population(identical_submissions(19, first_roles={0: "superuser"}))
        result = provisional_confidence_calculate(pop, method1_calculate(pop))
        assert result.level_raw is not None
        self.assertLess(result.level_raw, 50.0)

    def test_single_submission_zero_dispersion(self):
        pop = population(identical_submissions(1, first_roles={0: "superuser"}))
        result = provisional_confidence_calculate(pop, method1_calculate(pop))
        self.assertEqual(result.status, PROVISIONAL_READY)
        self.assertEqual(result.diagnostics["qn_style_aitchison_dispersion"], 0.0)
        self.assertEqual(result.diagnostics["whole_population_agreement_factor"], 1.0)

    def test_dispersion_lowers_agreement_factor(self):
        identical = population(identical_submissions(19, first_roles={0: "superuser"}))
        flat = provisional_confidence_calculate(identical, method1_calculate(identical))
        self.assertEqual(flat.diagnostics["qn_style_aitchison_dispersion"], 0.0)
        self.assertEqual(flat.diagnostics["whole_population_agreement_factor"], 1.0)
        dispersed = population(
            scattered_submissions(19, seed=41, roles={0: "superuser"})
        )
        result = provisional_confidence_calculate(
            dispersed, method1_calculate(dispersed)
        )
        self.assertGreater(result.diagnostics["qn_style_aitchison_dispersion"], 0.0)
        self.assertLess(result.diagnostics["whole_population_agreement_factor"], 1.0)
        assert result.level_raw is not None
        assert flat.level_raw is not None
        self.assertLess(result.level_raw, flat.level_raw)

    def test_mixed_authority_role_mass_raises_uplift(self):
        roles = {0: "superuser", 1: "moderator"}
        pop = population(identical_submissions(19, first_roles=roles))
        result = provisional_confidence_calculate(pop, method1_calculate(pop))
        self.assertGreater(result.diagnostics["role_evidence_factor"], 1.0)

    def test_zero_dispersion_support_table_at_19(self):
        # S(19) frozen near 45 (spec table).
        pop = population(identical_submissions(19, first_roles={0: "superuser"}))
        result = provisional_confidence_calculate(pop, method1_calculate(pop))
        self.assertAlmostEqual(
            result.diagnostics["sample_support_ceiling"], 45.0, delta=0.2
        )


class BoundaryContinuityTests(SimpleTestCase):
    def test_decay_curve(self):
        self.assertAlmostEqual(boundary_decay(1.0, 20), 1.0, places=9)
        self.assertAlmostEqual(boundary_decay(1.0, 50), 0.741, delta=0.01)
        self.assertAlmostEqual(boundary_decay(1.0, 100), 0.449, delta=0.01)
        self.assertAlmostEqual(boundary_decay(1.0, 250), 0.100, delta=0.01)
        self.assertAlmostEqual(boundary_decay(1.0, 500), 0.008, delta=0.01)

    def test_calibration_delta_never_negative(self):
        pop = population(scattered_submissions(30, seed=31, roles={0: "superuser"}))
        calibration = boundary_calibrate(pop, game_identifier="g-test")
        self.assertGreaterEqual(calibration.delta, 0.0)

    def test_calibration_at_exact_20(self):
        pop = population(identical_submissions(20, first_roles={0: "superuser"}))
        calibration = boundary_calibrate(pop, game_identifier="g-20")
        # Perfect agreement: C19 LOO values and C20 are both high; delta >= 0.
        self.assertGreaterEqual(calibration.delta, 0.0)
        self.assertEqual(calibration.subset_count_attempted, 1)

    def test_final_confidence_capped_at_100(self):
        result = boundary_final_confidence(99.0, 25.0, 20)
        self.assertLessEqual(result["confidence_final_unrounded"], 100.0)

    def test_deterministic_boundary_sampling(self):
        pop = population(scattered_submissions(30, seed=33, roles={0: "superuser"}))
        first = boundary_calibrate(pop, game_identifier="g-samp")
        second = boundary_calibrate(pop, game_identifier="g-samp")
        self.assertEqual(first.delta, second.delta)
        self.assertEqual(first.seed_or_stream, second.seed_or_stream)

    def test_static_calibration_data_fields(self):
        data = BoundaryCalibrationData(status=READY, delta=1.5, population_size=30)
        self.assertTrue(data.is_calibrated)
        unavailable = BoundaryCalibrationData(
            status=BOUNDARY_CALIBRATION_UNAVAILABLE, delta=0.0
        )
        self.assertFalse(unavailable.is_calibrated)
