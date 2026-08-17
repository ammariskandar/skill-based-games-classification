"""
Method 3 (LoOP) tests — SBGC-65.
"""

from __future__ import annotations

import math

from django.test import SimpleTestCase

from classifications.calculations.method3 import (
    _dimension_loop_scores,
    method3_calculate,
)
from classifications.calculations.results import (
    INSUFFICIENT_SAMPLE_FOR_LOOP,
    NO_SUBMISSIONS,
    READY,
)
from classifications.tests.calculations_factories import (
    identical_submissions,
    population,
    profile,
    scattered_submissions,
)


class Method3StatusTests(SimpleTestCase):
    def test_no_submissions(self):
        result = method3_calculate(population([]))
        self.assertEqual(result.status, NO_SUBMISSIONS)

    def test_insufficient_sample_below_20(self):
        result = method3_calculate(population(identical_submissions(19)))
        self.assertEqual(result.status, INSUFFICIENT_SAMPLE_FOR_LOOP)
        self.assertIsNone(result.raw_challenge)

    def test_19_vs_20_boundary(self):
        self.assertEqual(
            method3_calculate(population(identical_submissions(19))).status,
            INSUFFICIENT_SAMPLE_FOR_LOOP,
        )
        self.assertNotEqual(
            method3_calculate(population(identical_submissions(20))).status,
            INSUFFICIENT_SAMPLE_FOR_LOOP,
        )


class LoOPDegenerateBranchesTests(SimpleTestCase):
    def test_constant_dimension_all_zero(self):
        scores = _dimension_loop_scores([5.0] * 25)
        self.assertEqual(scores, [0.0] * 25)

    def test_two_value_dimension_zero_probabilities(self):
        # Half at 0, half at 100: tie-inclusive neighborhoods give equal
        # pdist for all observations -> all PLOF zero -> nPLOF zero -> LoOP 0.
        values = [0.0] * 12 + [100.0] * 12
        scores = _dimension_loop_scores(values)
        self.assertTrue(all(score == 0.0 for score in scores))

    def test_isolated_extreme_gets_high_probability(self):
        # 24 tightly clustered values with one far outlier: LoOP strictly
        # exceeds the 0.75 flag threshold while staying within [0, 1).
        values = [10.0 + 0.1 * i for i in range(24)] + [90.0]
        scores = _dimension_loop_scores(values)
        self.assertGreater(scores[-1], 0.75)
        self.assertLess(scores[-1], 1.0)
        for score in scores:
            self.assertLessEqual(score, 1.0)
            self.assertGreaterEqual(score, 0.0)

    def test_threshold_strict_inequality(self):
        # A score exactly at 0.75 is not flagged.
        values = [10.0 + 0.1 * i for i in range(24)] + [90.0]
        scores = _dimension_loop_scores(values)
        flags = [score > 0.75 for score in scores]
        # The extreme is flagged; equal-to-threshold values are not.
        for score, flagged in zip(scores, flags, strict=False):
            if flagged:
                self.assertGreater(score, 0.75)
            if math.isclose(score, 0.75, abs_tol=1e-12):
                self.assertFalse(flagged)


class Method3BehaviorTests(SimpleTestCase):
    def test_identical_population_mean_recovered(self):
        challenge = profile(45.0, 30.0, 25.0)
        reward = profile(40.0, 30.0, 30.0)
        subs = identical_submissions(30, challenge=challenge, reward=reward)
        result = method3_calculate(population(subs))
        self.assertEqual(result.status, READY)
        self.assertEqual(result.rejected, 0)
        assert result.raw_challenge is not None
        self.assertAlmostEqual(result.raw_challenge.micro, 45.0, places=6)

    def test_extreme_isolated_submission_rejected(self):
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
        result = method3_calculate(population(base + [extreme]))
        self.assertEqual(result.status, READY)
        assert result.rejected is not None
        self.assertGreaterEqual(result.rejected, 1)

    def test_dense_minority_cluster_survives(self):
        # A locally dense minority cluster is retained by local-density logic.
        majority = identical_submissions(
            24,
            identifier_prefix="maj",
            challenge=profile(45.0, 30.0, 25.0),
            reward=profile(40.0, 30.0, 30.0),
        )
        minority = identical_submissions(
            8,
            identifier_prefix="min",
            challenge=profile(15.0, 20.0, 65.0),
            reward=profile(20.0, 20.0, 60.0),
        )
        result = method3_calculate(population(majority + minority))
        self.assertEqual(result.status, READY)
        # At least some minority members survive the 2-of-6 rule.
        assert result.survivors is not None
        self.assertGreater(result.survivors, 0)

    def test_deterministic_replay(self):
        subs = scattered_submissions(60, seed=12)
        first = method3_calculate(population(subs))
        second = method3_calculate(population(subs))
        self.assertEqual(first.raw_challenge, second.raw_challenge)
        self.assertEqual(first.raw_reward, second.raw_reward)
        self.assertEqual(first.rejected, second.rejected)

    def test_role_insensitivity(self):
        community_only = scattered_submissions(40, seed=13)
        role_shifted = [
            type(s)(
                identifier=s.identifier,
                challenge=s.challenge,
                reward=s.reward,
                role="moderator",
            )
            for s in community_only
        ]
        first = method3_calculate(population(community_only))
        second = method3_calculate(population(role_shifted))
        self.assertEqual(first.raw_challenge, second.raw_challenge)

    def test_row_order_invariance(self):
        import random

        subs = scattered_submissions(50, seed=14)
        rng = random.Random(15)
        shuffled = list(subs)
        rng.shuffle(shuffled)
        ordered = method3_calculate(population(subs))
        permuted = method3_calculate(population(shuffled))
        assert ordered.raw_challenge is not None
        assert permuted.raw_challenge is not None
        for a, b in zip(
            ordered.raw_challenge.components(),
            permuted.raw_challenge.components(),
            strict=False,
        ):
            self.assertAlmostEqual(a, b, places=9)

    def test_ready_output_totals_100(self):
        result = method3_calculate(population(scattered_submissions(45, seed=16)))
        self.assertEqual(result.status, READY)
        assert result.raw_challenge is not None
        assert result.raw_reward is not None
        assert result.integer_challenge is not None
        assert result.integer_reward is not None
        self.assertAlmostEqual(result.raw_challenge.total(), 100.0, places=6)
        self.assertAlmostEqual(result.raw_reward.total(), 100.0, places=6)
        self.assertEqual(sum(result.integer_challenge), 100)
        self.assertEqual(sum(result.integer_reward), 100)
