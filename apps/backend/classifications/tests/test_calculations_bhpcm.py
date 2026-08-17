"""
BHPCM_V1 conformance tests — Part B.29 acceptance suite — SBGC-65.

Reduced bootstrap/governance counts are injected only where the property
under test does not depend on the frozen production counts.  One controlled
acceptance path proves the frozen production settings execute.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from classifications.calculations.bhpcm import (
    bhpcm_calculate,
    central_expert_influence,
)
from classifications.calculations.method1 import method1_calculate
from classifications.calculations.method2 import method2_calculate
from classifications.calculations.method3 import method3_calculate
from classifications.calculations.results import READY
from classifications.tests.calculations_factories import (
    identical_submissions,
    population,
    profile,
    scattered_submissions,
)

REDUCED_REPLICATES = 60
REDUCED_DRAWS = 2


def _methods(pop):
    return (
        method1_calculate(pop),
        method2_calculate(pop),
        method3_calculate(pop),
    )


class CentralExpertInfluenceTests(SimpleTestCase):
    def test_zero_disagreement(self):
        self.assertAlmostEqual(central_expert_influence(0.0), 0.50, places=9)

    def test_half_life(self):
        self.assertAlmostEqual(central_expert_influence(0.25), 0.40, places=9)

    def test_large_disagreement_approaches_minimum(self):
        self.assertAlmostEqual(central_expert_influence(100.0), 0.30, places=9)

    def test_monotone_decreasing(self):
        previous = central_expert_influence(0.0)
        for d in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 10.0):
            current = central_expert_influence(d)
            self.assertLess(current, previous)
            self.assertGreaterEqual(current, 0.30)
            previous = current


class BHPCMAcceptanceTests(SimpleTestCase):
    def _ready_bhpcm(self, pop):
        result = bhpcm_calculate(
            pop,
            _methods(pop),
            bootstrap_replicates=REDUCED_REPLICATES,
            governance_draws=REDUCED_DRAWS,
        )
        self.assertEqual(result.status, READY)
        return result

    def test_equal_methods_identity_invariant(self):
        # B.29.1: three identical method outputs -> unified equals them.
        challenge = profile(45.0, 30.0, 25.0)
        reward = profile(40.0, 30.0, 30.0)
        subs = identical_submissions(
            30,
            first_roles={0: "superuser"},
            challenge=challenge,
            reward=reward,
        )
        pop = population(subs)
        result = self._ready_bhpcm(pop)
        assert result.official_raw_challenge is not None
        assert result.official_raw_reward is not None
        self.assertAlmostEqual(result.official_raw_challenge.micro, 45.0, places=6)
        self.assertAlmostEqual(result.official_raw_challenge.macro, 30.0, places=6)
        self.assertAlmostEqual(result.official_raw_challenge.mystiko, 25.0, places=6)
        self.assertAlmostEqual(result.official_raw_reward.micro, 40.0, places=6)

    def test_method_weight_invariants(self):
        result = self._ready_bhpcm(
            population(scattered_submissions(40, roles={0: "superuser"}))
        )
        summaries = result.diagnostics["method_weight_summaries"]
        for name in ("omega_1", "omega_2", "omega_3"):
            for stat in ("mean", "median", "p05", "p95"):
                self.assertGreaterEqual(summaries[name][stat], 0.0)
                self.assertLessEqual(summaries[name][stat], 1.0)
        # omega_1 (expert) bounded in [0.30, 0.50].
        self.assertGreaterEqual(summaries["omega_1"]["p05"], 0.30)
        self.assertLessEqual(summaries["omega_1"]["p95"], 0.50)
        # lambda bounded in [0.35, 0.65].
        balance = result.diagnostics["population_balance_summary"]
        self.assertGreaterEqual(balance["p05"], 0.35)
        self.assertLessEqual(balance["p95"], 0.65)

    def test_posterior_normalization(self):
        result = self._ready_bhpcm(
            population(scattered_submissions(45, roles={0: "superuser"}))
        )
        assert result.official_raw_challenge is not None
        assert result.official_raw_reward is not None
        assert result.integer_challenge is not None
        assert result.integer_reward is not None
        self.assertAlmostEqual(result.official_raw_challenge.total(), 100.0, places=6)
        self.assertAlmostEqual(result.official_raw_reward.total(), 100.0, places=6)
        self.assertEqual(sum(result.integer_challenge), 100)
        self.assertEqual(sum(result.integer_reward), 100)

    def test_credible_intervals_recorded(self):
        result = self._ready_bhpcm(
            population(scattered_submissions(40, roles={0: "superuser"}))
        )
        intervals = result.diagnostics["component_intervals_90"]
        for profile_key in ("challenge", "reward"):
            for entry in intervals[profile_key].values():
                self.assertLessEqual(entry["p05"], entry["p95"])
                self.assertGreaterEqual(entry["p05"], 0.0)
                self.assertLessEqual(entry["p95"], 100.0)

    def test_rounded_triplet_probabilities_sum_to_one(self):
        result = self._ready_bhpcm(
            population(scattered_submissions(40, roles={0: "superuser"}))
        )
        for profile_key in ("challenge", "reward"):
            triplets = result.diagnostics["rounded_profile_probabilities"][profile_key][
                "reported_triplets"
            ]
            self.assertGreaterEqual(len(triplets), 1)
            self.assertAlmostEqual(
                sum(t["probability"] for t in triplets), 1.0, delta=0.05
            )

    def test_conflict_classification_low_for_aligned_perspectives(self):
        # Identical submissions produce identical method outputs -> D0 = 0.
        subs = identical_submissions(30, first_roles={0: "superuser"})
        result = self._ready_bhpcm(population(subs))
        self.assertEqual(result.diagnostics["conflict_classification"], "Low conflict")
        self.assertAlmostEqual(
            result.diagnostics["combined_point_disagreement"], 0.0, places=6
        )

    def test_sensitivity_profiles_recorded(self):
        result = self._ready_bhpcm(
            population(scattered_submissions(40, roles={0: "superuser"}))
        )
        profiles = result.diagnostics["sensitivity_profiles"]
        self.assertIn("omega_0.30", profiles)
        self.assertIn("omega_0.40", profiles)
        self.assertIn("omega_0.50", profiles)
        for weight in ("omega_0.30", "omega_0.50"):
            entry = profiles[weight]
            self.assertEqual(sum(entry["integer_challenge"]), 100)
            self.assertEqual(sum(entry["integer_reward"]), 100)

    def test_deterministic_replay(self):
        subs = scattered_submissions(40, seed=21, roles={0: "superuser"})
        pop = population(subs)
        first = bhpcm_calculate(
            pop,
            _methods(pop),
            bootstrap_replicates=REDUCED_REPLICATES,
            governance_draws=REDUCED_DRAWS,
        )
        second = bhpcm_calculate(
            pop,
            _methods(pop),
            bootstrap_replicates=REDUCED_REPLICATES,
            governance_draws=REDUCED_DRAWS,
        )
        self.assertEqual(first.official_raw_challenge, second.official_raw_challenge)
        self.assertEqual(first.official_raw_reward, second.official_raw_reward)
        self.assertEqual(first.integer_challenge, second.integer_challenge)

    def test_zero_replacement_recorded(self):
        # Method outputs containing a zero component exercise zero replacement.
        challenge = profile(100.0, 0.0, 0.0)
        reward = profile(100.0, 0.0, 0.0)
        subs = identical_submissions(
            30, first_roles={0: "superuser"}, challenge=challenge, reward=reward
        )
        pop = population(subs)
        result = bhpcm_calculate(
            pop,
            _methods(pop),
            bootstrap_replicates=REDUCED_REPLICATES,
            governance_draws=REDUCED_DRAWS,
        )
        if result.status == READY:
            self.assertGreaterEqual(result.diagnostics["zero_replacement_count"], 1)
        # A zero-replacement population still yields finite official outputs.
        self.assertIsNotNone(result.official_raw_challenge)


class BHPCMFrozenProductionSettingsTests(SimpleTestCase):
    def test_production_settings_execute(self):
        """One controlled acceptance path at the frozen production settings."""
        subs = identical_submissions(20, first_roles={0: "superuser", 1: "moderator"})
        pop = population(subs)
        result = bhpcm_calculate(pop, _methods(pop))
        self.assertEqual(result.status, READY)
        self.assertEqual(result.diagnostics["bootstrap_target_count"], 500)
        self.assertEqual(result.diagnostics["governance_draws_per_bootstrap"], 20)
        self.assertEqual(
            result.diagnostics["posterior_draw_count"],
            result.diagnostics["bootstrap_valid_count"] * 20,
        )
        assert result.integer_challenge is not None
        assert result.integer_reward is not None
        self.assertEqual(sum(result.integer_challenge), 100)
        self.assertEqual(sum(result.integer_reward), 100)
