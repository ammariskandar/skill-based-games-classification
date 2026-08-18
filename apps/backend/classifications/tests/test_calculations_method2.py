"""
Method 2 (Isolation Forest) tests — SBGC-65.
"""

from __future__ import annotations

import math

from django.test import SimpleTestCase

from classifications.calculations.method2 import (
    expected_path_adjustment,
    method2_calculate,
)
from classifications.calculations.profiles import analysis_values
from classifications.calculations.results import (
    INSUFFICIENT_SAMPLE_FOR_IFOREST,
    NO_SUBMISSIONS,
    READY,
)
from classifications.tests.calculations_factories import (
    identical_submissions,
    population,
    profile,
    scattered_submissions,
)


class ExpectedPathAdjustmentTests(SimpleTestCase):
    def test_small_n(self):
        self.assertEqual(expected_path_adjustment(0), 0.0)
        self.assertEqual(expected_path_adjustment(1), 0.0)
        self.assertGreater(expected_path_adjustment(2), 0.0)

    def test_harmonic_growth(self):
        self.assertGreater(expected_path_adjustment(100), expected_path_adjustment(10))


class Method2StatusTests(SimpleTestCase):
    def test_no_submissions(self):
        result = method2_calculate(population([]))
        self.assertEqual(result.status, NO_SUBMISSIONS)

    def test_insufficient_sample_below_20(self):
        result = method2_calculate(population(identical_submissions(19)))
        self.assertEqual(result.status, INSUFFICIENT_SAMPLE_FOR_IFOREST)
        self.assertIsNone(result.raw_challenge)

    def test_exact_minimum_20_runs(self):
        subs = identical_submissions(20)
        result = method2_calculate(population(subs))
        self.assertNotEqual(result.status, INSUFFICIENT_SAMPLE_FOR_IFOREST)

    def test_19_vs_20_boundary(self):
        self.assertEqual(
            method2_calculate(population(identical_submissions(19))).status,
            INSUFFICIENT_SAMPLE_FOR_IFOREST,
        )
        self.assertNotEqual(
            method2_calculate(population(identical_submissions(20))).status,
            INSUFFICIENT_SAMPLE_FOR_IFOREST,
        )


class Method2BehaviorTests(SimpleTestCase):
    def test_constant_data_all_scores_exactly_half(self):
        # Constant dimension: every tree terminates at the root -> 0.5.
        result = method2_calculate(population(identical_submissions(30)))
        self.assertEqual(result.status, READY)
        # Nothing is flagged at exactly 0.5 (threshold is strict > 0.60).
        self.assertEqual(result.rejected, 0)
        self.assertEqual(result.survivors, 30)
        self.assertEqual(result.diagnostics["scalar_flag_counts"], [0, 0, 0, 0, 0, 0])

    def test_identical_population_mean_recovered(self):
        challenge = profile(45.0, 30.0, 25.0)
        reward = profile(40.0, 30.0, 30.0)
        subs = identical_submissions(30, challenge=challenge, reward=reward)
        result = method2_calculate(population(subs))
        self.assertEqual(result.status, READY)
        assert result.raw_challenge is not None
        self.assertAlmostEqual(result.raw_challenge.micro, 45.0, places=6)
        self.assertAlmostEqual(result.raw_challenge.macro, 30.0, places=6)
        self.assertAlmostEqual(result.raw_challenge.mystiko, 25.0, places=6)

    def test_extreme_outlier_rejected_whole_submission(self):
        base = identical_submissions(
            29,
            challenge=profile(45.0, 30.0, 25.0),
            reward=profile(40.0, 30.0, 30.0),
        )
        from classifications.calculations.profiles import SubmissionRecord

        extreme = SubmissionRecord(
            identifier="extreme",
            challenge=profile(95.0, 3.0, 2.0),
            reward=profile(95.0, 3.0, 2.0),
            role="community",
        )
        result = method2_calculate(population(base + [extreme]))
        self.assertEqual(result.status, READY)
        assert result.rejected is not None
        self.assertGreaterEqual(result.rejected, 1)

    def test_deterministic_replay(self):
        subs = scattered_submissions(60, seed=3)
        first = method2_calculate(population(subs))
        second = method2_calculate(population(subs))
        self.assertEqual(first.raw_challenge, second.raw_challenge)
        self.assertEqual(first.raw_reward, second.raw_reward)
        self.assertEqual(first.rejected, second.rejected)

    def test_role_insensitivity(self):
        community_only = scattered_submissions(40, seed=3)
        role_shifted = [
            type(s)(
                identifier=s.identifier,
                challenge=s.challenge,
                reward=s.reward,
                role="superuser",
            )
            for s in community_only
        ]
        first = method2_calculate(population(community_only))
        second = method2_calculate(population(role_shifted))
        self.assertEqual(first.raw_challenge, second.raw_challenge)
        self.assertEqual(first.raw_reward, second.raw_reward)

    def test_row_order_invariance(self):
        import random

        subs = scattered_submissions(50, seed=8)
        rng = random.Random(2)
        shuffled = list(subs)
        rng.shuffle(shuffled)
        ordered = method2_calculate(population(subs))
        permuted = method2_calculate(population(shuffled))
        assert ordered.raw_challenge is not None
        assert permuted.raw_challenge is not None
        for a, b in zip(
            ordered.raw_challenge.components(),
            permuted.raw_challenge.components(),
            strict=False,
        ):
            self.assertAlmostEqual(a, b, places=9)

    def test_ready_output_totals_100(self):
        result = method2_calculate(population(scattered_submissions(45, seed=6)))
        self.assertEqual(result.status, READY)
        assert result.raw_challenge is not None
        assert result.raw_reward is not None
        assert result.integer_challenge is not None
        assert result.integer_reward is not None
        self.assertAlmostEqual(result.raw_challenge.total(), 100.0, places=6)
        self.assertAlmostEqual(result.raw_reward.total(), 100.0, places=6)
        self.assertEqual(sum(result.integer_challenge), 100)
        self.assertEqual(sum(result.integer_reward), 100)


class Method2SortedBisectEquivalenceTests(SimpleTestCase):
    """Prove the sorted+bisect Isolation Forest is identical to the
    specification's linear-scan partition on identical RNG streams."""

    def _reference_scores(self, values, psi, height_limit, reference, dim_index):
        """Reference linear-scan implementation (as originally specified)."""
        import random as random_module

        from classifications.calculations.constants import IFOREST_SEED
        from classifications.calculations.method2 import expected_path_adjustment

        def build(values, rng, depth):
            if (
                depth >= height_limit
                or len(values) <= 1
                or all(v == values[0] for v in values)
            ):
                return ("leaf", depth, len(values))
            z_min = min(values)
            z_max = max(values)
            split = rng.uniform(z_min, z_max)
            if split == z_min:
                split = (z_min + z_max) / 2.0
            left = [v for v in values if v < split]
            right = [v for v in values if v >= split]
            return (
                "node",
                split,
                build(left, rng, depth + 1),
                build(right, rng, depth + 1),
            )

        def path(tree, value):
            node = tree
            while True:
                kind = node[0]
                if kind == "leaf":
                    return node[1] + expected_path_adjustment(node[2])
                _, split, left, right = node
                node = left if value < split else right

        rng = random_module.Random((IFOREST_SEED * 31) + dim_index)
        path_sums = [0.0] * len(values)
        for _ in range(512):
            tree = build(rng.sample(values, psi), rng, 0)
            for i, value in enumerate(values):
                path_sums[i] += path(tree, value)
        return [2.0 ** (-s / 512 / reference) for s in path_sums]

    def test_identical_scores_across_populations(self):
        from classifications.calculations.constants import (
            IFOREST_SUBSAMPLE_MAX,
        )
        from classifications.calculations.method2 import (
            _dimension_scores,
            expected_path_adjustment,
        )

        for seed in (101, 202, 303):
            subs = scattered_submissions(30, seed=seed)
            for dim_index in range(6):
                values = [analysis_values(sub)[dim_index] for sub in subs]
                psi = min(IFOREST_SUBSAMPLE_MAX, len(values))
                height_limit = int(math.ceil(math.log2(psi)))
                reference = expected_path_adjustment(psi)
                fast = _dimension_scores(
                    values, psi, height_limit, reference, dim_index
                )
                slow = self._reference_scores(
                    values, psi, height_limit, reference, dim_index
                )
                for a, b in zip(fast, slow, strict=False):
                    self.assertAlmostEqual(a, b, places=12)
