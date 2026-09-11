"""Aesthetic consensus & tiebreaker tests — SBGC-227 (spec §5.1)."""

from __future__ import annotations

import random

from django.test import SimpleTestCase

from classifications.services.aesthetic_consensus import (
    AestheticPair,
    agreement_bonus,
    disagreement_penalty,
    resolve_aesthetic_consensus,
)

S = "SENSORY"
F = "FANTASY"
N = "NARRATIVE"
C = "CHALLENGE"


def _tie(a: tuple[str, str], b: tuple[str, str], base: float = 100.0):
    return resolve_aesthetic_consensus(
        [a, b], base_confidence=base, rng=random.Random(0)
    )


class TiebreakerPenaltyMatrixTests(SimpleTestCase):
    def test_total_disagreement_applies_ten_percent(self):
        result = _tie((S, C), (F, N))
        self.assertTrue(result.is_tie)
        self.assertEqual(result.penalty, 10)
        self.assertEqual(result.confidence, 90)

    def test_inverted_order_applies_five_percent(self):
        result = _tie((F, S), (N, F))
        self.assertTrue(result.is_tie)
        self.assertEqual(result.penalty, 5)
        self.assertEqual(result.confidence, 95)

    def test_secondary_agreement_applies_one_percent(self):
        result = _tie((N, C), (F, C))
        self.assertTrue(result.is_tie)
        self.assertEqual(result.penalty, 1)
        self.assertEqual(result.confidence, 99)

    def test_primary_agreement_applies_zero_percent(self):
        result = _tie((F, S), (F, N))
        self.assertTrue(result.is_tie)
        self.assertEqual(result.penalty, 0)
        self.assertEqual(result.confidence, 100)

    def test_exact_swap_is_a_partial_disagreement(self):
        self.assertEqual(
            disagreement_penalty(AestheticPair(F, S), AestheticPair(S, F)), 5
        )

    def test_penalty_is_clamped_at_zero_floor(self):
        self.assertEqual(_tie((S, C), (F, N), base=10.0).confidence, 0)
        self.assertEqual(_tie((S, C), (F, N), base=4.0).confidence, 0)

    def test_tie_winner_is_one_of_the_tied_leaders(self):
        result = _tie((S, C), (F, N))
        self.assertIn((result.primary, result.secondary), {(S, C), (F, N)})
        self.assertEqual(len(result.tied_pairs), 2)


class AgreementBonusTests(SimpleTestCase):
    def test_no_bonus_below_ten_surplus(self):
        # 3 agree vs 1 disagree → surplus 2 → no bonus.
        votes = [(F, S), (F, S), (F, S), (N, C)]
        result = resolve_aesthetic_consensus(votes, base_confidence=80.0)
        self.assertFalse(result.is_tie)
        self.assertEqual((result.primary, result.secondary), (F, S))
        self.assertEqual(result.bonus, 0)
        self.assertEqual(result.confidence, 80)

    def test_one_percent_per_full_ten_surplus(self):
        self.assertEqual(agreement_bonus(6, 7), 0)  # surplus 5
        self.assertEqual(agreement_bonus(7, 10), 0)  # surplus 4
        self.assertEqual(agreement_bonus(10, 10), 1)  # surplus 10
        self.assertEqual(agreement_bonus(15, 20), 1)  # surplus 10
        self.assertEqual(agreement_bonus(25, 25), 2)  # surplus 25

    def test_bonus_is_capped_at_one_hundred(self):
        votes = [(F, S)] * 15
        result = resolve_aesthetic_consensus(votes, base_confidence=99.0)
        self.assertEqual(result.bonus, 1)
        self.assertEqual(result.confidence, 100)

    def test_uncontested_winner_uses_plurality(self):
        votes = [(S, C), (S, C), (F, N)]
        result = resolve_aesthetic_consensus(votes)
        self.assertEqual((result.primary, result.secondary), (S, C))
        self.assertEqual(result.winner_votes, 2)


class ConsensusEdgeCaseTests(SimpleTestCase):
    def test_no_votes_leaves_aesthetic_unresolved(self):
        result = resolve_aesthetic_consensus([], base_confidence=42.0)
        self.assertIsNone(result.primary)
        self.assertEqual(result.confidence, 42)

    def test_invalid_votes_are_ignored(self):
        result = resolve_aesthetic_consensus(
            [("NOPE", "SENSORY"), ("SENSORY",)], base_confidence=50.0
        )
        self.assertIsNone(result.primary)
        self.assertEqual(result.confidence, 50)
