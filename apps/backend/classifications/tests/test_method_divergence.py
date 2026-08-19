"""
Method 2 vs Method 3 philosophical-divergence test — SBGC-66 (section 5).

A dense minority cluster is globally isolated (Method 2 rejects it) but
locally dense (Method 3 retains it).  This proves the two population methods
legitimately differ rather than being interchangeable.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from classifications.calculations.method2 import method2_calculate
from classifications.calculations.method3 import method3_calculate
from classifications.calculations.profiles import (
    Profile,
    SubmissionRecord,
    build_population_snapshot,
)
from classifications.calculations.results import READY


def _p(micro, macro, mystiko):
    return Profile(micro=micro, macro=macro, mystiko=mystiko)


class Method23DivergenceTests(SimpleTestCase):
    def _population(self, minority_size=3):
        majority = [
            SubmissionRecord(
                identifier=f"maj{i:02d}",
                challenge=_p(45.0, 30.0, 25.0),
                reward=_p(40.0, 30.0, 30.0),
                role="community",
            )
            for i in range(28 - minority_size)
        ]
        minority = [
            SubmissionRecord(
                identifier=f"min{i:02d}",
                challenge=_p(8.0, 12.0, 80.0),
                reward=_p(8.0, 12.0, 80.0),
                role="community",
            )
            for i in range(minority_size)
        ]
        return build_population_snapshot(majority + minority)

    def test_method3_retains_dense_minority_that_method2_rejects(self):
        pop = self._population(minority_size=3)
        m2 = method2_calculate(pop)
        m3 = method3_calculate(pop)

        self.assertEqual(m2.status, READY)
        self.assertEqual(m3.status, READY)
        # Method 2 (global isolation) rejects the isolated minority cluster.
        self.assertEqual(m2.rejected, 3)
        # Method 3 (local density) retains the dense minority cluster.
        self.assertEqual(m3.rejected, 0)

        # The survivor means therefore differ materially.
        self.assertEqual(m2.integer_challenge, (45, 30, 25))
        self.assertEqual(m3.integer_challenge, (41, 28, 31))
        self.assertNotEqual(m2.integer_challenge, m3.integer_challenge)

    def test_larger_minority_is_not_anomalous_to_either(self):
        pop = self._population(minority_size=8)
        m2 = method2_calculate(pop)
        m3 = method3_calculate(pop)
        # An 8-member cluster is no longer globally isolated.
        self.assertEqual(m2.rejected, 0)
        self.assertEqual(m3.rejected, 0)
