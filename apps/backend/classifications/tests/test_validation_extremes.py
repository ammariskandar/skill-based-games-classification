"""
Source-submission validation tests — SBGC-66 (section 7).

Invalid source submissions must be removed before N is established; valid
extreme compositions (100/0/0, 0/100/0, 0/0/100) must NOT be confused with
invalid data.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from classifications.calculations.profiles import (
    SubmissionRecord,
    build_population_snapshot,
)
from classifications.tests.calculations_factories import (
    balanced,
    profile,
)


def _record(identifier, challenge, reward):
    return SubmissionRecord(
        identifier=identifier, challenge=challenge, reward=reward, role="community"
    )


class SourceValidationTests(SimpleTestCase):
    def _snapshot_with(self, extra):
        base = [
            _record("a", balanced(), balanced(40.0, 30.0, 30.0)),
            _record("b", balanced(), balanced(40.0, 30.0, 30.0)),
        ]
        return build_population_snapshot(base + extra)

    def test_missing_component_excluded(self):
        # non-numeric component -> invalid
        from classifications.calculations.profiles import Profile

        bad = _record("bad", Profile("x", 30.0, 20.0), balanced())  # type: ignore[arg-type]
        self.assertEqual(self._snapshot_with([bad]).raw_n, 2)

    def test_negative_component_excluded(self):
        bad = _record("bad", profile(-1.0, 50.0, 51.0), balanced())
        self.assertEqual(self._snapshot_with([bad]).raw_n, 2)

    def test_component_over_100_excluded(self):
        bad = _record("bad", profile(101.0, 0.0, -1.0), balanced())
        self.assertEqual(self._snapshot_with([bad]).raw_n, 2)

    def test_challenge_total_not_100_excluded(self):
        bad = _record("bad", profile(40.0, 30.0, 20.0), balanced())
        self.assertEqual(self._snapshot_with([bad]).raw_n, 2)

    def test_reward_total_not_100_excluded(self):
        bad = _record("bad", balanced(), profile(10.0, 20.0, 30.0))
        self.assertEqual(self._snapshot_with([bad]).raw_n, 2)


class ValidExtremesAcceptedTests(SimpleTestCase):
    def test_extreme_compositions_are_valid(self):
        records = [
            _record("micro", profile(100.0, 0.0, 0.0), balanced()),
            _record("macro", profile(0.0, 100.0, 0.0), balanced()),
            _record("mystiko", profile(0.0, 0.0, 100.0), balanced()),
        ]
        snapshot = build_population_snapshot(records)
        self.assertEqual(snapshot.raw_n, 3)

    def test_all_three_extremes_in_reward_too(self):
        records = [
            _record("micro", balanced(), profile(100.0, 0.0, 0.0)),
            _record("macro", balanced(), profile(0.0, 100.0, 0.0)),
            _record("mystiko", balanced(), profile(0.0, 0.0, 100.0)),
        ]
        snapshot = build_population_snapshot(records)
        self.assertEqual(snapshot.raw_n, 3)
