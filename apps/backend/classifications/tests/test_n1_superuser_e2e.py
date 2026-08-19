"""
True end-to-end N=1 Superuser classification workflow — SBGC-66 (section 11).

Exercises the real submission service, persistence, calculation service,
and read contract without fabricating a derived snapshot.  The superuser is
``thenamesammaris``; no real password is committed (test-only credential).
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from games.models import Game, SourceType

from classifications.models import CalculationEpoch, ClassificationSnapshot
from classifications.roles import EditorialRole
from classifications.services.calculations import (
    freeze_population,
    get_published_classification,
    run_game_calculation,
)
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
)


class N1SuperuserEndToEndTests(TestCase):
    def setUp(self):
        self.game = Game.objects.create(
            name="SBGC 66 N1 Classification Test",
            slug="sbgc-66-n1-classification-test",
            source_type=SourceType.MANUAL,
        )
        self.superuser = User.objects.create_superuser(
            "thenamesammaris",
            email="thenamesammaris@example.com",
            password="test-only-password",
        )

    def test_full_n1_superuser_workflow(self):
        submission = create_submission(
            game=self.game,
            submitted_by=self.superuser,
            updated_by=self.superuser,
            challenge=ScoreDistribution(micro=50, mystiko=20, macro=30),
            reward=ScoreDistribution(micro=20, mystiko=50, macro=30),
            notes="",
        )

        # -- source submission persisted exactly ---------------------------
        self.assertEqual(submission.submitted_by.username, "thenamesammaris")
        self.assertEqual(submission.submitted_role, EditorialRole.SUPERUSER)
        challenge = submission.challenge_profile
        reward = submission.reward_profile
        self.assertEqual(challenge.micro_score, 50)
        self.assertEqual(challenge.macro_score, 30)
        self.assertEqual(challenge.mystiko_score, 20)
        self.assertEqual(reward.micro_score, 20)
        self.assertEqual(reward.macro_score, 30)
        self.assertEqual(reward.mystiko_score, 50)

        # -- N = 1 ----------------------------------------------------------
        population, received, invalid = freeze_population(self.game, timezone.now())
        self.assertEqual(population.raw_n, 1)
        self.assertEqual(received, 1)
        self.assertEqual(invalid, 0)
        self.assertEqual(population.submissions[0].role, "superuser")

        # -- canonical calculation path ------------------------------------
        epoch = CalculationEpoch.objects.create(
            epoch_id="n1-superuser-epoch",
            cutoff_at=timezone.now(),
            master_version="STATISTICAL_MODEL_V1.0.0",
        )
        attempt = run_game_calculation(
            game=self.game,
            epoch=epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
        )
        self.assertEqual(attempt.status, "succeeded")

        snapshot = ClassificationSnapshot.objects.get(game=self.game, epoch=epoch)
        self.assertEqual(snapshot.regime, "provisional")
        self.assertEqual(snapshot.status, "READY")
        self.assertEqual(snapshot.method_1_status, "READY")
        # Methods 2/3 and BHPCM are not applicable in the provisional regime.
        self.assertEqual(snapshot.method_2_status, "")
        self.assertEqual(snapshot.method_3_status, "")
        self.assertEqual(snapshot.bhpcm_version, "BHPCM_V1")
        # Method 1's N=1 result is the source submission itself.
        self.assertEqual(snapshot.method_1_integer_challenge, [50, 30, 20])
        self.assertEqual(snapshot.method_1_integer_reward, [20, 30, 50])
        self.assertEqual(snapshot.unified_integer_challenge, [50, 30, 20])
        self.assertEqual(snapshot.unified_integer_reward, [20, 30, 50])
        self.assertIsNotNone(snapshot.confidence_final)
        self.assertEqual(snapshot.confidence_label, "Low")
        self.assertTrue(snapshot.is_current)

        # -- provisional confidence < 50 -----------------------------------
        confidence = float(snapshot.confidence_final)
        self.assertLess(confidence, 50.0)
        self.assertGreater(confidence, 0.0)
        self.assertAlmostEqual(confidence, 5.98, delta=0.2)

        # -- read contract returns identical values ------------------------
        published = get_published_classification(self.game)
        self.assertTrue(published.available)
        self.assertEqual(published.status, "READY")
        self.assertEqual(published.regime, "provisional")
        self.assertEqual(published.validated_submission_count, 1)
        assert published.unified is not None
        assert published.method_1 is not None
        self.assertEqual(published.unified["challenge"], [50, 30, 20])
        self.assertEqual(published.unified["reward"], [20, 30, 50])
        self.assertEqual(published.method_1["integer_challenge"], [50, 30, 20])
        self.assertEqual(published.method_1["integer_reward"], [20, 30, 50])
        self.assertIsNone(published.method_2)
        self.assertIsNone(published.method_3)
        self.assertEqual(published.confidence, confidence)
        self.assertEqual(published.confidence_label, "Low")
