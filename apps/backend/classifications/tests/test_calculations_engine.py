"""
End-to-end engine regime tests — SBGC-65 (Part H).
"""

from __future__ import annotations

from django.test import SimpleTestCase

from classifications.calculations.engine import calculate_game
from classifications.calculations.results import (
    INSUFFICIENT_ANCHOR,
    NO_SUBMISSIONS,
    PROVISIONAL_READY,
    READY,
)
from classifications.tests.calculations_factories import (
    identical_submissions,
    population,
    scattered_submissions,
)


class EngineRegimeTests(SimpleTestCase):
    def test_zero_submissions(self):
        result = calculate_game(population([]))
        self.assertEqual(result.status, NO_SUBMISSIONS)
        self.assertEqual(result.raw_n, 0)
        self.assertIsNone(result.integer_challenge)

    def test_provisional_regime_with_anchor(self):
        pop = population(identical_submissions(10, first_roles={0: "superuser"}))
        result = calculate_game(pop)
        self.assertEqual(result.regime, "provisional")
        self.assertEqual(result.status, READY)
        assert result.method_1 is not None
        self.assertIsNotNone(result.method_1)
        self.assertEqual(result.method_1.status, READY)
        self.assertIsNone(result.method_2)
        self.assertIsNone(result.bhpcm)
        assert result.confidence is not None
        self.assertEqual(result.confidence.status, PROVISIONAL_READY)
        assert result.integer_challenge is not None
        assert result.integer_reward is not None
        self.assertEqual(sum(result.integer_challenge), 100)
        self.assertEqual(sum(result.integer_reward), 100)

    def test_provisional_regime_insufficient_anchor(self):
        pop = population(identical_submissions(12))
        result = calculate_game(pop)
        self.assertEqual(result.regime, "provisional")
        self.assertEqual(result.status, INSUFFICIENT_ANCHOR)
        self.assertIsNone(result.confidence)
        self.assertIsNone(result.integer_challenge)

    def test_unified_regime_ready(self):
        pop = population(scattered_submissions(21, seed=51, roles={0: "superuser"}))
        result = calculate_game(
            pop,
            game_identifier="g-engine",
            bootstrap_replicates=40,
            governance_draws=2,
        )
        self.assertEqual(result.regime, "unified")
        self.assertEqual(result.status, READY)
        assert result.method_1 is not None
        assert result.method_2 is not None
        assert result.method_3 is not None
        assert result.bhpcm is not None
        assert result.confidence is not None
        assert result.integer_challenge is not None
        assert result.integer_reward is not None
        self.assertEqual(result.method_1.status, READY)
        self.assertEqual(result.method_2.status, READY)
        self.assertEqual(result.method_3.status, READY)
        self.assertEqual(result.bhpcm.status, READY)
        self.assertIsNotNone(result.confidence)
        self.assertEqual(sum(result.integer_challenge), 100)
        self.assertEqual(sum(result.integer_reward), 100)

    def test_unified_regime_persists_method_outputs_even_when_not_ready(self):
        # All-community N=20: Method 1 lacks an anchor while M2/M3 are ready.
        pop = population(identical_submissions(20))
        result = calculate_game(
            pop,
            game_identifier="g-anchorless",
            bootstrap_replicates=40,
            governance_draws=2,
        )
        self.assertEqual(result.regime, "unified")
        assert result.method_1 is not None
        assert result.method_2 is not None
        assert result.method_3 is not None
        assert result.bhpcm is not None
        self.assertEqual(result.method_1.status, INSUFFICIENT_ANCHOR)
        self.assertEqual(result.method_2.status, READY)
        self.assertEqual(result.method_3.status, READY)
        self.assertEqual(result.bhpcm.status, "INSUFFICIENT_METHOD_1")
        self.assertIsNone(result.integer_challenge)

    def test_identical_provenance_reproducibility(self):
        pop = population(scattered_submissions(21, seed=52, roles={0: "superuser"}))
        first = calculate_game(
            pop,
            game_identifier="g-replay",
            bootstrap_replicates=40,
            governance_draws=2,
        )
        second = calculate_game(
            pop,
            game_identifier="g-replay",
            bootstrap_replicates=40,
            governance_draws=2,
        )
        self.assertEqual(first.integer_challenge, second.integer_challenge)
        self.assertEqual(first.integer_reward, second.integer_reward)
        assert first.confidence is not None
        assert second.confidence is not None
        assert first.confidence.level_raw is not None
        assert second.confidence.level_raw is not None
        self.assertEqual(first.confidence.level_raw, second.confidence.level_raw)
