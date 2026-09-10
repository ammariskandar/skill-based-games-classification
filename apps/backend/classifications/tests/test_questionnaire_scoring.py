"""
Questionnaire scoring engine & Q15 compensation tests — SBGC-174.

Covers per-step flooring, Largest-Remainder normalization (including the
zero-total fallback and tie-break order), profile isolation, quality-tier
bounds, and the coupled proportional compensation algorithm.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from classifications.questionnaire.registry.v1.set_a import SET_A
from classifications.questionnaire.registry.v1.types import (
    ProfileTarget,
    QuestionNode,
    opt,
    question,
)
from classifications.questionnaire.scoring.compensation import (
    QUALITY_TIER_MAP,
    apply_proportional_compensation,
    resolve_quality_spec,
)
from classifications.questionnaire.scoring.engine import (
    compute_raw_profile,
    normalize_profile,
)
from classifications.questionnaire.scoring.types import (
    DimensionScore,
    QualityTier,
)

CHALLENGE = ProfileTarget.CHALLENGE
REWARD = ProfileTarget.REWARD


def _node(node_id: str, label: str, target: ProfileTarget, **modifiers) -> QuestionNode:
    return question(
        node_id, f"{node_id} question", [opt(label, **modifiers)], target=target
    )


def _option_id(node, suffix: str) -> str:
    for option in node.options:
        if option.id.endswith(suffix):
            return option.id
    raise AssertionError(f"option {suffix} not found on {node.id}")


class AccumulatorTests(SimpleTestCase):
    def test_intermediate_negative_flooring(self):
        nodes = [
            _node("Q3", "plus", CHALLENGE, micro=10),
            _node("Q4", "minus", CHALLENGE, micro=-30),
            _node("Q5", "plus", CHALLENGE, micro=20),
        ]
        answers = {node.id: node.options[0].id for node in nodes}
        result = compute_raw_profile(answers, nodes, CHALLENGE)
        # +10 → 0 (floored after -30) → 20, not 0.
        self.assertEqual(result, DimensionScore(micro=20, macro=0, mystiko=0))

    def test_profile_target_isolation(self):
        nodes = (*SET_A.part1_questions, *SET_A.part2_questions)
        q3 = next(n for n in SET_A.part1_questions if n.id == "Q3")
        q10 = next(n for n in SET_A.part2_questions if n.id == "Q10")
        answers = {
            "Q3": _option_id(q3, "huge"),  # micro +20 (Challenge)
            "Q10": _option_id(q10, "great_gameplay"),  # micro +90 (Reward)
        }
        challenge = compute_raw_profile(answers, nodes, CHALLENGE)
        reward = compute_raw_profile(answers, nodes, REWARD)
        self.assertEqual(challenge, DimensionScore(micro=20, macro=0, mystiko=0))
        self.assertEqual(reward, DimensionScore(micro=90, macro=0, mystiko=0))

    def test_unknown_question_and_option_are_ignored(self):
        nodes = [_node("Q3", "plus", CHALLENGE, micro=10)]
        answers = {"Q3": "Q3_bogus", "Q99": "Q99_whatever"}
        result = compute_raw_profile(answers, nodes, CHALLENGE)
        self.assertEqual(result, DimensionScore(micro=0, macro=0, mystiko=0))


class NormalizationTests(SimpleTestCase):
    def test_zero_total_fallback(self):
        self.assertEqual(
            normalize_profile(DimensionScore(0, 0, 0)),
            DimensionScore(micro=33, macro=33, mystiko=34),
        )

    def test_exact_ratios_normalize_without_remainder(self):
        self.assertEqual(
            normalize_profile(DimensionScore(50, 25, 25)),
            DimensionScore(micro=50, macro=25, mystiko=25),
        )

    def test_largest_remainder_tie_break_prefers_static_order(self):
        # All three fractions tie at 33.333...; the single remainder unit goes
        # to Micro (Micro ≻ Macro ≻ Mystiko).
        self.assertEqual(
            normalize_profile(DimensionScore(1, 1, 1)),
            DimensionScore(micro=34, macro=33, mystiko=33),
        )

    def test_remainder_goes_to_largest_fraction(self):
        # (10, 7, 3) → 50.0 / 35.0 / 15.0 exactly; no remainder.
        self.assertEqual(
            normalize_profile(DimensionScore(10, 7, 3)),
            DimensionScore(micro=50, macro=35, mystiko=15),
        )
        # (1, 2, 3) → 16.67 / 33.33 / 50.0 → floors 16/33/50, remainder 1 to
        # the largest fraction (micro .67 > macro .33).
        self.assertEqual(
            normalize_profile(DimensionScore(1, 2, 3)),
            DimensionScore(micro=17, macro=33, mystiko=50),
        )

    def test_normalization_always_sums_to_100(self):
        for raw in (
            DimensionScore(0, 1, 0),
            DimensionScore(99, 1, 0),
            DimensionScore(7, 7, 7),
            DimensionScore(1, 1, 1),
            DimensionScore(500, 1, 1),
        ):
            with self.subTest(raw=raw):
                normalized = normalize_profile(raw)
                self.assertEqual(normalized.total, 100)


class QualityTierTests(SimpleTestCase):
    def test_quality_tier_boundaries(self):
        self.assertEqual(resolve_quality_spec(1).permitted_delta, 90)
        self.assertEqual(resolve_quality_spec(3).permitted_delta, 90)
        self.assertEqual(resolve_quality_spec(4).permitted_delta, 30)
        self.assertEqual(resolve_quality_spec(5).permitted_delta, 30)
        self.assertEqual(resolve_quality_spec(6).permitted_delta, 10)
        self.assertEqual(resolve_quality_spec(7).permitted_delta, 10)
        self.assertEqual(resolve_quality_spec(8).permitted_delta, 5)
        self.assertEqual(resolve_quality_spec(9).permitted_delta, 5)
        self.assertEqual(resolve_quality_spec(10).permitted_delta, 1)

    def test_quality_tier_map_has_five_bands(self):
        self.assertEqual(len(QUALITY_TIER_MAP), 5)
        self.assertEqual(
            {spec.tier for spec in QUALITY_TIER_MAP.values()},
            set(QualityTier),
        )

    def test_invalid_rating_is_rejected(self):
        for rating in (0, 11, -1):
            with self.assertRaises(ValueError):
                resolve_quality_spec(rating)


class CompensationTests(SimpleTestCase):
    def test_proportional_reduction_symmetry(self):
        result = apply_proportional_compensation(
            DimensionScore(60, 20, 20),
            active_dimension="micro",
            target_value=70,
            rating=7,  # HIGH: ±10
        )
        self.assertEqual(result, DimensionScore(micro=70, macro=15, mystiko=15))

    def test_companion_zero_division_splits_evenly(self):
        result = apply_proportional_compensation(
            DimensionScore(100, 0, 0),
            active_dimension="micro",
            target_value=90,
            rating=7,
        )
        self.assertEqual(result, DimensionScore(micro=90, macro=5, mystiko=5))

    def test_boundary_containment_preserves_total(self):
        # (50, 48, 2) → micro +20 → companions shed 20 proportionally.
        # macro: -19.2, mystiko: -0.8 → floor (28, 1), residual 1 to macro.
        result = apply_proportional_compensation(
            DimensionScore(50, 48, 2),
            active_dimension="micro",
            target_value=70,
            rating=1,  # LOW: ±90
        )
        self.assertEqual(result, DimensionScore(micro=70, macro=29, mystiko=1))
        self.assertEqual(result.total, 100)

    def test_delta_zero_returns_baseline(self):
        baseline = DimensionScore(40, 30, 30)
        result = apply_proportional_compensation(baseline, "micro", 40, rating=10)
        self.assertEqual(result, baseline)

    def test_quality_window_clamps_the_target(self):
        # Perfect quality (±1) cannot move micro from 50 to 100.
        result = apply_proportional_compensation(
            DimensionScore(50, 25, 25),
            active_dimension="micro",
            target_value=100,
            rating=10,
        )
        self.assertEqual(result.micro, 51)

    def test_compensation_always_sums_to_100_and_stays_bounded(self):
        cases = [
            (DimensionScore(60, 20, 20), "micro", 70, 7),
            (DimensionScore(60, 20, 20), "micro", 10, 7),
            (DimensionScore(0, 0, 100), "mystiko", 10, 1),
            (DimensionScore(33, 33, 34), "macro", 100, 1),
            (DimensionScore(90, 5, 5), "micro", 0, 1),
            (DimensionScore(1, 1, 98), "mystiko", 98, 10),
        ]
        for base, dimension, target, rating in cases:
            with self.subTest(base=base, dimension=dimension, target=target):
                result = apply_proportional_compensation(
                    base, dimension, target, rating
                )
                self.assertEqual(result.total, 100)
                self.assertGreaterEqual(result.micro, 0)
                self.assertGreaterEqual(result.macro, 0)
                self.assertGreaterEqual(result.mystiko, 0)
                self.assertLessEqual(result.micro, 100)
                self.assertLessEqual(result.macro, 100)
                self.assertLessEqual(result.mystiko, 100)

    def test_unknown_dimension_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_proportional_compensation(
                DimensionScore(60, 20, 20), "unknown", 70, 7
            )
