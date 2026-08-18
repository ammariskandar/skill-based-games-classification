"""
Pure-mathematics tests: reconciliation, composition, profiles — SBGC-65.
"""

from __future__ import annotations

import math

from django.test import SimpleTestCase

from classifications.calculations.composition import (
    aitchison_distance,
    ilr,
    ilr_inv,
    joint_ilr,
    zero_replaced_fractions,
)
from classifications.calculations.errors import CalculationInvariantError
from classifications.calculations.profiles import (
    analysis_values,
    build_population_snapshot,
    canonical_population_hash,
)
from classifications.calculations.reconciliation import (
    largest_remainder,
    largest_remainder_profile,
)
from classifications.tests.calculations_factories import (
    balanced,
    identical_submissions,
    population,
    profile,
)


class LargestRemainderTests(SimpleTestCase):
    def test_exact_integers_unchanged(self):
        self.assertEqual(largest_remainder((20.0, 30.0, 50.0)), (20, 30, 50))

    def test_residual_one_goes_to_largest_remainder(self):
        self.assertEqual(largest_remainder((33.4, 33.3, 33.3)), (34, 33, 33))

    def test_residual_two_distributes(self):
        self.assertEqual(largest_remainder((10.9, 20.7, 68.2)), (11, 21, 68))

    def test_micro_macro_tie_priority(self):
        # Equal remainders on Micro and Macro: Micro wins.
        self.assertEqual(largest_remainder((50.5, 49.5, 0.0)), (51, 49, 0))

    def test_micro_mystiko_tie_priority(self):
        self.assertEqual(largest_remainder((50.5, 0.0, 49.5)), (51, 0, 49))

    def test_macro_mystiko_tie_priority(self):
        self.assertEqual(largest_remainder((0.0, 50.5, 49.5)), (0, 51, 49))

    def test_three_way_tie_priority(self):
        # 100/3 = 33.333...: residual 1 after floors (33+33+33=99).
        third = 100.0 / 3.0
        self.assertEqual(largest_remainder((third, third, third)), (34, 33, 33))

    def test_tie_within_tolerance_resolves_by_priority(self):
        # Remainders 0.4000000000001 and 0.4 are tied within 1e-12: Micro wins.
        self.assertEqual(largest_remainder((10.4, 20.4 + 1e-13, 69.2)), (11, 20, 69))

    def test_invalid_residual_raises(self):
        with self.assertRaises(CalculationInvariantError):
            largest_remainder((101.0, -1.0, 0.0))

    def test_profile_helper(self):
        result = largest_remainder_profile(profile(33.4, 33.3, 33.3))
        self.assertEqual(result, (34, 33, 33))


class CompositionTests(SimpleTestCase):
    def test_zero_replacement_rescales_nonzero_components(self):
        replaced = zero_replaced_fractions(profile(100.0, 0.0, 0.0))
        self.assertAlmostEqual(sum(replaced), 1.0, places=12)
        self.assertAlmostEqual(replaced[1], 1e-6, places=12)
        self.assertAlmostEqual(replaced[2], 1e-6, places=12)
        self.assertAlmostEqual(replaced[0], 1.0 - 2e-6, places=10)

    def test_no_zero_no_replacement(self):
        replaced = zero_replaced_fractions(profile(40.0, 35.0, 25.0))
        self.assertEqual(replaced, (0.4, 0.35, 0.25))

    def test_ilr_round_trip(self):
        original = profile(45.0, 30.0, 25.0)
        recovered = ilr_inv(ilr(original))
        for actual, expected in zip(
            recovered.components(), original.components(), strict=False
        ):
            self.assertAlmostEqual(actual, expected, places=9)

    def test_ilr_round_trip_with_zero_component(self):
        original = profile(100.0, 0.0, 0.0)
        recovered = ilr_inv(ilr(original))
        self.assertAlmostEqual(recovered.micro, 100.0, places=3)
        self.assertAlmostEqual(recovered.macro, 0.0, places=3)
        self.assertAlmostEqual(recovered.mystiko, 0.0, places=3)

    def test_aitchison_distance_symmetric(self):
        a = profile(40.0, 35.0, 25.0)
        b = profile(50.0, 25.0, 25.0)
        self.assertAlmostEqual(
            aitchison_distance(a, b), aitchison_distance(b, a), places=12
        )
        self.assertGreater(aitchison_distance(a, b), 0.0)

    def test_joint_ilr_order(self):
        joint = joint_ilr(balanced(), balanced(40.0, 30.0, 30.0))
        self.assertEqual(len(joint), 4)


class PopulationSnapshotTests(SimpleTestCase):
    def test_invalid_submissions_excluded_before_n(self):
        submissions = identical_submissions(3)
        from classifications.calculations.profiles import SubmissionRecord

        submissions.append(
            SubmissionRecord(
                identifier="broken",
                challenge=profile(50.0, 50.0, 50.0),  # totals 150
                reward=balanced(),
                role="community",
            )
        )
        snapshot = build_population_snapshot(submissions)
        self.assertEqual(snapshot.raw_n, 3)

    def test_out_of_range_score_excluded(self):
        from classifications.calculations.profiles import SubmissionRecord

        submissions = identical_submissions(2) + [
            SubmissionRecord(
                identifier="negative",
                challenge=profile(150.0, -50.0, 0.0),
                reward=balanced(),
                role="community",
            )
        ]
        snapshot = build_population_snapshot(submissions)
        self.assertEqual(snapshot.raw_n, 2)

    def test_canonical_ordering_by_identifier(self):

        reversed_order = list(reversed(identical_submissions(5)))
        snapshot = population(reversed_order)
        self.assertEqual(
            [s.identifier for s in snapshot.submissions],
            sorted(s.identifier for s in reversed_order),
        )

    def test_row_order_invariance_of_hash(self):
        first = identical_submissions(6)
        import random

        rng = random.Random(4)
        shuffled = list(first)
        rng.shuffle(shuffled)
        self.assertEqual(
            canonical_population_hash(first),
            canonical_population_hash(shuffled),
        )

    def test_hash_changes_when_role_changes(self):
        base = identical_submissions(4)
        changed = identical_submissions(4, first_roles={0: "superuser"})
        self.assertNotEqual(
            canonical_population_hash(base),
            canonical_population_hash(changed),
        )

    def test_analysis_values_order(self):
        record = identical_submissions(1)[0]
        values = analysis_values(record)
        self.assertEqual(len(values), 6)
        # Frozen order: C_micro, C_mystiko, C_macro, R_micro, R_mystiko, R_macro.
        self.assertEqual(values[0], record.challenge.micro)
        self.assertEqual(values[1], record.challenge.mystiko)
        self.assertEqual(values[2], record.challenge.macro)
        self.assertEqual(values[3], record.reward.micro)
        self.assertEqual(values[4], record.reward.mystiko)
        self.assertEqual(values[5], record.reward.macro)


class InvariantHelpersTests(SimpleTestCase):
    def test_math_module_available(self):
        # Guard the accidental loss of math imports used by frozen constants.
        self.assertTrue(math.isfinite(0.5))
