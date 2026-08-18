"""
Method 1 tests — role-aware anchored aggregation — SBGC-65.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from classifications.calculations.method1 import (
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
    profile,
    scattered_submissions,
)


class PopulationInfluenceTests(SimpleTestCase):
    def test_monotone_frozen_curve(self):
        self.assertEqual(population_influence(5), 0.0)
        self.assertAlmostEqual(population_influence(25), 0.10, places=9)
        self.assertAlmostEqual(population_influence(50), 0.35, places=9)
        self.assertAlmostEqual(population_influence(250), 0.85, places=9)
        self.assertEqual(population_influence(400), 0.85)
        self.assertAlmostEqual(population_influence(1000), 1.0, places=9)
        self.assertEqual(population_influence(1001), 1.0)

    def test_non_negative_everywhere(self):
        for n in range(0, 1200, 7):
            self.assertGreaterEqual(population_influence(n), 0.0)
            self.assertLessEqual(population_influence(n), 1.0)


class RobustStatisticsTests(SimpleTestCase):
    def test_median_odd(self):
        self.assertEqual(median([1.0, 3.0, 2.0]), 2.0)

    def test_median_even(self):
        self.assertEqual(median([1.0, 2.0, 3.0, 4.0]), 2.5)

    def test_sn_zero_for_constant_data(self):
        self.assertEqual(sn_scale([7.0] * 12), 0.0)

    def test_sn_positive_for_spread_data(self):
        values = [float(v) for v in range(20)]
        self.assertGreater(sn_scale(values), 0.0)


class Method1StatusTests(SimpleTestCase):
    def test_no_submissions(self):
        result = method1_calculate(population([]))
        self.assertEqual(result.status, NO_SUBMISSIONS)
        self.assertEqual(result.diagnostics["raw_n"], 0)

    def test_insufficient_anchor_below_50_all_community(self):
        result = method1_calculate(population(identical_submissions(12)))
        self.assertEqual(result.status, INSUFFICIENT_ANCHOR)

    def test_all_community_at_50_uses_community_fallback(self):
        result = method1_calculate(population(identical_submissions(50)))
        self.assertEqual(result.status, READY)
        self.assertEqual(result.diagnostics["anchor_type"], "COMMUNITY_FALLBACK")

    def test_all_community_below_50_without_anchor(self):
        # 49 community, no privileged anchor: fallback requires N >= 50.
        result = method1_calculate(population(identical_submissions(49)))
        self.assertEqual(result.status, INSUFFICIENT_ANCHOR)

    def test_single_superuser_anchor(self):
        subs = identical_submissions(12, first_roles={0: "superuser"})
        result = method1_calculate(population(subs))
        self.assertEqual(result.status, READY)
        self.assertEqual(result.diagnostics["anchor_type"], "SUPERUSER")

    def test_two_moderators_anchor(self):
        subs = identical_submissions(12, first_roles={0: "moderator", 1: "moderator"})
        result = method1_calculate(population(subs))
        self.assertEqual(result.status, READY)
        self.assertEqual(result.diagnostics["anchor_type"], "MODERATOR")

    def test_five_community_leaders_anchor(self):
        roles = {i: "community_leader" for i in range(5)}
        result = method1_calculate(
            population(identical_submissions(15, first_roles=roles))
        )
        self.assertEqual(result.status, READY)
        self.assertEqual(result.diagnostics["anchor_type"], "COMMUNITY_LEADER")

    def test_one_moderator_three_cl_mixed_anchor(self):
        roles = {
            0: "moderator",
            1: "community_leader",
            2: "community_leader",
            3: "community_leader",
        }
        result = method1_calculate(
            population(identical_submissions(15, first_roles=roles))
        )
        self.assertEqual(result.status, READY)
        self.assertEqual(result.diagnostics["anchor_type"], "MIXED")

    def test_anchor_hierarchy_superuser_beats_moderators(self):
        roles = {0: "superuser", 1: "moderator", 2: "moderator"}
        result = method1_calculate(
            population(identical_submissions(15, first_roles=roles))
        )
        self.assertEqual(result.diagnostics["anchor_type"], "SUPERUSER")


class Method1ReadyInvariantsTests(SimpleTestCase):
    def _ready(self, subs):
        result = method1_calculate(population(subs))
        self.assertEqual(result.status, READY)
        return result

    def test_ready_profiles_total_100(self):
        result = self._ready(scattered_submissions(40, roles={0: "superuser"}))
        assert result.raw_challenge is not None
        assert result.raw_reward is not None
        assert result.integer_challenge is not None
        assert result.integer_reward is not None
        for raw in (result.raw_challenge, result.raw_reward):
            self.assertAlmostEqual(raw.total(), 100.0, places=6)
        for integers in (result.integer_challenge, result.integer_reward):
            self.assertEqual(sum(integers), 100)
            for value in integers:
                self.assertGreaterEqual(value, 0)

    def test_identical_population_matches_common_profile(self):
        challenge = profile(45.0, 30.0, 25.0)
        reward = profile(40.0, 30.0, 30.0)
        subs = identical_submissions(
            30,
            first_roles={0: "superuser"},
            challenge=challenge,
            reward=reward,
        )
        result = self._ready(subs)
        assert result.raw_challenge is not None
        assert result.raw_reward is not None
        for raw, base in (
            (result.raw_challenge, challenge),
            (result.raw_reward, reward),
        ):
            self.assertAlmostEqual(raw.micro, base.micro, places=6)
            self.assertAlmostEqual(raw.macro, base.macro, places=6)
            self.assertAlmostEqual(raw.mystiko, base.mystiko, places=6)

    def test_zero_sd_flags_nothing_but_floor_respected(self):
        # Constant data: SD = 0 -> threshold = delta floor = 5.
        subs = identical_submissions(30, first_roles={0: "superuser"})
        result = self._ready(subs)
        self.assertEqual(result.diagnostics["method_1a_rejected"], 0)
        self.assertEqual(result.diagnostics["method_1b_rejected"], 0)

    def test_single_extreme_above_floor_is_rejected(self):
        base = identical_submissions(
            29,
            first_roles={0: "superuser"},
            challenge=profile(45.0, 30.0, 25.0),
            reward=profile(40.0, 30.0, 30.0),
        )
        from classifications.calculations.profiles import SubmissionRecord

        extreme = SubmissionRecord(
            identifier="extreme",
            challenge=profile(80.0, 10.0, 10.0),
            reward=profile(80.0, 10.0, 10.0),
            role="community",
        )
        result = self._ready(base + [extreme])
        self.assertGreaterEqual(
            result.diagnostics["method_1a_rejected"]
            + result.diagnostics["method_1b_rejected"],
            1,
        )

    def test_high_n_anchor_reliability_recorded(self):
        result = self._ready(scattered_submissions(401, roles={0: "superuser"}))
        self.assertIsNotNone(result.diagnostics["anchor_reliability"])

    def test_high_n_protected_anchor_no_reliability_field(self):
        result = self._ready(scattered_submissions(399, roles={0: "superuser"}))
        self.assertIsNone(result.diagnostics["anchor_reliability"])

    def test_deterministic_replay(self):
        subs = scattered_submissions(60, seed=11, roles={0: "superuser"})
        first = method1_calculate(population(subs))
        second = method1_calculate(population(subs))
        self.assertEqual(first.raw_challenge, second.raw_challenge)
        self.assertEqual(first.raw_reward, second.raw_reward)

    def test_row_order_invariance(self):
        import random

        subs = scattered_submissions(60, seed=5, roles={0: "superuser"})
        rng = random.Random(9)
        shuffled = list(subs)
        rng.shuffle(shuffled)
        ordered = method1_calculate(population(subs))
        permuted = method1_calculate(population(shuffled))
        assert ordered.raw_challenge is not None
        assert permuted.raw_challenge is not None
        assert ordered.raw_reward is not None
        assert permuted.raw_reward is not None
        for a, b in zip(
            ordered.raw_challenge.components(),
            permuted.raw_challenge.components(),
            strict=False,
        ):
            self.assertAlmostEqual(a, b, places=9)
        for a, b in zip(
            ordered.raw_reward.components(),
            permuted.raw_reward.components(),
            strict=False,
        ):
            self.assertAlmostEqual(a, b, places=9)
