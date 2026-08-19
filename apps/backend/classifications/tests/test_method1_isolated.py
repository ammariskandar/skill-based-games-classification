"""
Method 1 isolated tests — SBGC-66.

Expected values are derived independently from docs/statistical_model.md
Parts V-XIV, not from the implementation.  Private helpers are imported
directly for the precise scalar/flag tests; the public entry point is
exercised for status/anchor/high-N behaviour.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from classifications.calculations.method1 import (
    _sample_sd,
    _whole_submission_retain,
    median,
    method1_calculate,
    population_influence,
    sn_scale,
)
from classifications.calculations.results import (
    INSUFFICIENT_ANCHOR,
    NO_SUBMISSIONS,
    READY,
)
from classifications.tests.calculations_factories import (
    identical_submissions,
    population,
    scattered_submissions,
)


class PopulationInfluenceBoundaryTests(SimpleTestCase):
    # Values from statistical_model.md section 15.3.
    _EXPECTED = {
        0: 0.0,
        1: 0.0,
        5: 0.0,
        6: 0.005,
        25: 0.10,
        26: 0.11,
        50: 0.35,
        51: 0.3525,
        250: 0.85,
        251: 0.85,
        400: 0.85,
        401: 0.85025,
        1000: 1.0,
        1001: 1.0,
    }

    def test_frozen_boundary_values(self):
        for n, expected in self._EXPECTED.items():
            self.assertAlmostEqual(
                population_influence(n), expected, places=9, msg=f"N={n}"
            )


class SampleSDBesselTests(SimpleTestCase):
    def test_bessel_correction(self):
        # mean = 5, sum of squared deviations = 32, N = 8 -> 32 / 7.
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        self.assertAlmostEqual(_sample_sd(values), (32.0 / 7.0) ** 0.5, places=9)

    def test_single_value_undefined_reports_zero(self):
        self.assertEqual(_sample_sd([5.0]), 0.0)

    def test_constant_series_zero(self):
        self.assertEqual(_sample_sd([7.0, 7.0, 7.0, 7.0]), 0.0)


class RobustScaleTests(SimpleTestCase):
    def test_sn_hand_computed(self):
        # [1, 2, 3]: every observation's median pairwise distance is 1,
        # so Sn = 1.1926 * 1 = 1.1926 (statistical_model.md section 25).
        self.assertAlmostEqual(sn_scale([1.0, 2.0, 3.0]), 1.1926, places=9)

    def test_sn_constant_zero(self):
        self.assertEqual(sn_scale([4.0] * 9), 0.0)

    def test_median_hand_computed(self):
        self.assertEqual(median([9.0, 1.0, 5.0]), 5.0)
        self.assertEqual(median([1.0, 3.0, 4.0, 9.0]), 3.5)


class WholeSubmissionRuleTests(SimpleTestCase):
    def test_zero_flags_retains(self):
        flags = [[False, False, False] for _ in range(6)]
        self.assertEqual(_whole_submission_retain(flags), [True, True, True])

    def test_one_flag_retains(self):
        flags = [[False, False, False] for _ in range(6)]
        flags[0] = [True, False, False]
        self.assertEqual(_whole_submission_retain(flags), [True, True, True])

    def test_two_flags_rejects(self):
        # Submission 0 flagged in two dimensions -> rejected (2-of-6 rule).
        flags = [[False, False, False] for _ in range(6)]
        flags[0] = [True, False, False]
        flags[1] = [True, False, False]
        self.assertEqual(_whole_submission_retain(flags), [False, True, True])

    def test_six_flags_rejects(self):
        # Submission 0 flagged in all six dimensions -> rejected.
        flags = [[True, False, False] for _ in range(6)]
        self.assertEqual(_whole_submission_retain(flags), [False, True, True])


class Method1BoundaryStatusTests(SimpleTestCase):
    def test_n0(self):
        result = method1_calculate(population([]))
        self.assertEqual(result.status, NO_SUBMISSIONS)

    def test_n1_superuser_ready(self):
        result = method1_calculate(
            population(identical_submissions(1, first_roles={0: "superuser"}))
        )
        self.assertEqual(result.status, READY)
        self.assertEqual(result.diagnostics["anchor_type"], "SUPERUSER")

    def test_n1_community_insufficient_anchor(self):
        result = method1_calculate(population(identical_submissions(1)))
        self.assertEqual(result.status, INSUFFICIENT_ANCHOR)

    def test_n8_n9_boundary(self):
        # Detectors are inactive below N=9 but the anchor still qualifies.
        n8 = method1_calculate(
            population(identical_submissions(8, first_roles={0: "superuser"}))
        )
        n9 = method1_calculate(
            population(identical_submissions(9, first_roles={0: "superuser"}))
        )
        self.assertEqual(n8.status, READY)
        self.assertEqual(n9.status, READY)

    def test_n19_n20_boundary(self):
        # Method 1 is READY at both; Method 2/3 regime is not Method 1's concern.
        n19 = method1_calculate(
            population(identical_submissions(19, first_roles={0: "superuser"}))
        )
        n20 = method1_calculate(
            population(identical_submissions(20, first_roles={0: "superuser"}))
        )
        self.assertEqual(n19.status, READY)
        self.assertEqual(n20.status, READY)

    def test_n49_n50_community_fallback_boundary(self):
        n49 = method1_calculate(population(identical_submissions(49)))
        n50 = method1_calculate(population(identical_submissions(50)))
        self.assertEqual(n49.status, INSUFFICIENT_ANCHOR)
        self.assertEqual(n50.status, READY)
        self.assertEqual(n50.diagnostics["anchor_type"], "COMMUNITY_FALLBACK")

    def test_n51_community_fallback(self):
        result = method1_calculate(population(identical_submissions(51)))
        self.assertEqual(result.status, READY)
        self.assertEqual(result.diagnostics["anchor_type"], "COMMUNITY_FALLBACK")

    def test_n400_n401_protected_vs_evidence_anchor(self):
        n400 = method1_calculate(
            population(scattered_submissions(400, roles={0: "superuser"}))
        )
        n401 = method1_calculate(
            population(scattered_submissions(401, roles={0: "superuser"}))
        )
        self.assertEqual(n400.status, READY)
        self.assertEqual(n401.status, READY)
        self.assertIsNone(n400.diagnostics["anchor_reliability"])
        self.assertIsNotNone(n401.diagnostics["anchor_reliability"])


class AnchorHierarchyTests(SimpleTestCase):
    def test_one_moderator_four_cl_mixed(self):
        roles = {
            0: "moderator",
            1: "community_leader",
            2: "community_leader",
            3: "community_leader",
            4: "community_leader",
        }
        result = method1_calculate(
            population(identical_submissions(15, first_roles=roles))
        )
        self.assertEqual(result.diagnostics["anchor_type"], "MIXED")

    def test_one_moderator_five_cl_uses_cl_anchor(self):
        # Five CL capture the CL substitute before the mixed rule.
        roles = {0: "moderator", **{i: "community_leader" for i in range(1, 6)}}
        result = method1_calculate(
            population(identical_submissions(15, first_roles=roles))
        )
        self.assertEqual(result.diagnostics["anchor_type"], "COMMUNITY_LEADER")

    def test_two_moderators_beat_cl(self):
        roles = {
            0: "moderator",
            1: "moderator",
            **{i: "community_leader" for i in range(2, 7)},
        }
        result = method1_calculate(
            population(identical_submissions(15, first_roles=roles))
        )
        self.assertEqual(result.diagnostics["anchor_type"], "MODERATOR")

    def test_superuser_beats_everything(self):
        roles = {
            0: "superuser",
            1: "moderator",
            2: "moderator",
            3: "community_leader",
            4: "community_leader",
        }
        result = method1_calculate(
            population(identical_submissions(15, first_roles=roles))
        )
        self.assertEqual(result.diagnostics["anchor_type"], "SUPERUSER")


class HighNCoefficientTests(SimpleTestCase):
    def test_coefficients_nonnegative_and_normalized(self):
        # High-N (>=401) diagnostics store the FINAL coefficients, which the
        # spec (Part XII section 51) proves sum exactly to one.
        for n in (401, 500):
            result = method1_calculate(
                population(
                    scattered_submissions(
                        n,
                        roles={0: "superuser", 1: "moderator", 2: "moderator"},
                    )
                )
            )
            self.assertEqual(result.status, READY)
            coefficients = result.diagnostics["coefficients"]
            values = [
                v for k, v in coefficients.items() if k not in ("anchor_only", "rho_a")
            ]
            for value in values:
                self.assertGreaterEqual(value, -1e-9)
            self.assertAlmostEqual(sum(values), 1.0, places=9)

    def test_low_n_raw_profile_normalized(self):
        # Low-N normalization is proven by the raw profile summing to 100
        # (Part XI section 45).
        result = method1_calculate(
            population(
                scattered_submissions(
                    50,
                    roles={0: "superuser", 1: "moderator", 2: "moderator"},
                )
            )
        )
        self.assertEqual(result.status, READY)
        assert result.raw_challenge is not None
        assert result.raw_reward is not None
        self.assertAlmostEqual(result.raw_challenge.total(), 100.0, places=6)
        self.assertAlmostEqual(result.raw_reward.total(), 100.0, places=6)


class Method1DeterminismTests(SimpleTestCase):
    def test_deterministic_replay(self):
        subs = scattered_submissions(60, seed=77, roles={0: "superuser"})
        first = method1_calculate(population(subs))
        second = method1_calculate(population(subs))
        self.assertEqual(first.raw_challenge, second.raw_challenge)
        self.assertEqual(first.raw_reward, second.raw_reward)
