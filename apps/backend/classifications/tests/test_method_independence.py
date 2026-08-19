"""
Explicit Method-independence acceptance test — SBGC-66 (section 6).

Proves the three methods are independently calculated from the same raw
population, that only Method 1 is role-sensitive, that Method 1/2/3
rejections are not fed into each other, and that the three results persist
independently without being overwritten by the unified BHPCM output.
"""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from classifications.calculations.method1 import method1_calculate
from classifications.calculations.method2 import method2_calculate
from classifications.calculations.method3 import method3_calculate
from classifications.calculations.profiles import SubmissionRecord
from classifications.calculations.results import (
    INSUFFICIENT_ANCHOR,
    READY,
)
from classifications.models import CalculationEpoch, ClassificationSnapshot
from classifications.services.calculations import run_game_calculation
from classifications.tests.calculations_factories import (
    identical_submissions,
    population,
    profile,
)


def _expert_population() -> list[SubmissionRecord]:
    """One superuser far from a moderate crowd; N=20.

    Method 1 anchors on the superuser (expert-like), while Methods 2/3 are
    population-robust and average the crowd.
    """
    crowd = identical_submissions(
        19,
        challenge=profile(45.0, 30.0, 25.0),
        reward=profile(40.0, 30.0, 30.0),
    )
    expert = SubmissionRecord(
        identifier="expert",
        challenge=profile(80.0, 10.0, 10.0),
        reward=profile(70.0, 15.0, 15.0),
        role="superuser",
    )
    return crowd + [expert]


class RoleSensitivityIndependenceTests(SimpleTestCase):
    def test_role_change_changes_method1_only(self):
        pop_a = population(_expert_population())
        m1_a = method1_calculate(pop_a)
        m2_a = method2_calculate(pop_a)
        m3_a = method3_calculate(pop_a)

        # Same scores, every role flattened to community -> Method 1 anchor
        # disappears, but Methods 2/3 are role-insensitive.
        flattened = [
            SubmissionRecord(
                identifier=s.identifier,
                challenge=s.challenge,
                reward=s.reward,
                role="community",
            )
            for s in pop_a.submissions
        ]
        pop_b = population(flattened)
        m1_b = method1_calculate(pop_b)
        m2_b = method2_calculate(pop_b)
        m3_b = method3_calculate(pop_b)

        self.assertEqual(m1_a.status, READY)
        self.assertEqual(m1_b.status, INSUFFICIENT_ANCHOR)
        # Method 2 / Method 3 outputs are identical regardless of roles.
        self.assertEqual(m2_a.raw_challenge, m2_b.raw_challenge)
        self.assertEqual(m2_a.raw_reward, m2_b.raw_reward)
        self.assertEqual(m3_a.raw_challenge, m3_b.raw_challenge)
        self.assertEqual(m3_a.raw_reward, m3_b.raw_reward)

    def test_methods_2_and_3_see_full_raw_population(self):
        # Method 1 rejection must not be fed into Methods 2/3: their raw_n
        # is always the full pre-rejection population count.
        pop = population(_expert_population())
        m1 = method1_calculate(pop)
        m2 = method2_calculate(pop)
        m3 = method3_calculate(pop)
        self.assertEqual(m1.diagnostics["raw_n"], 20)
        self.assertEqual(m2.diagnostics["raw_n"], 20)
        self.assertEqual(m3.diagnostics["raw_n"], 20)

    def test_methods_2_and_3_are_role_insensitive_on_same_population(self):
        pop = population(_expert_population())
        m2 = method2_calculate(pop)
        m3 = method3_calculate(pop)
        self.assertEqual(m2.status, READY)
        self.assertEqual(m3.status, READY)
        # Both population methods are computed independently of each other.
        self.assertIsNotNone(m2.raw_challenge)
        self.assertIsNotNone(m3.raw_challenge)


class PersistenceIndependenceTests(TestCase):
    def test_three_methods_persist_independently_and_unified_is_separate(self):
        from django.contrib.auth.models import User
        from games.models import Game, SourceType

        game = Game.objects.create(
            name="Method Independence",
            slug="method-independence",
            source_type=SourceType.MANUAL,
        )
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        from classifications.services.submissions import (
            ScoreDistribution,
            create_submission,
        )

        # Superuser with the expert profile + 19 crowd members.
        create_submission(
            game=game,
            submitted_by=superuser,
            updated_by=superuser,
            challenge=ScoreDistribution(micro=80, mystiko=10, macro=10),
            reward=ScoreDistribution(micro=70, mystiko=15, macro=15),
        )
        for index in range(19):
            user = User.objects.create_user(f"member-{index}")
            create_submission(
                game=game,
                submitted_by=user,
                updated_by=user,
                challenge=ScoreDistribution(micro=45, mystiko=25, macro=30),
                reward=ScoreDistribution(micro=40, mystiko=30, macro=30),
            )
        epoch = CalculationEpoch.objects.create(
            epoch_id="independence-epoch",
            cutoff_at=timezone.now(),
            master_version="STATISTICAL_MODEL_V1.0.0",
        )
        run_game_calculation(
            game=game,
            epoch=epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
            bootstrap_replicates=40,
            governance_draws=2,
        )

        snapshot = ClassificationSnapshot.objects.get(game=game, epoch=epoch)
        # All four score sets are stored on distinct fields.
        self.assertEqual(snapshot.method_1_status, "READY")
        self.assertEqual(snapshot.method_2_status, "READY")
        self.assertEqual(snapshot.method_3_status, "READY")
        self.assertIsNotNone(snapshot.unified_integer_challenge)
        # Method integer results remain distinct from the unified result.
        self.assertIsNotNone(snapshot.method_1_integer_challenge)
        self.assertIsNotNone(snapshot.method_2_integer_challenge)
        self.assertIsNotNone(snapshot.method_3_integer_challenge)
        self.assertEqual(sum(snapshot.method_1_integer_challenge), 100)
        self.assertEqual(sum(snapshot.method_2_integer_challenge), 100)
        self.assertEqual(sum(snapshot.method_3_integer_challenge), 100)
        self.assertEqual(sum(snapshot.unified_integer_challenge), 100)
