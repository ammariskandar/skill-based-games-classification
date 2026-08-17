"""
PostgreSQL derived-calculation persistence verification — SBGC-65.

Verifies the SBGC-65 migration 0006 models/constraints on an isolated
PostgreSQL instance: the partial-unique single-current-snapshot index,
atomic promotion/demotion, failed-promotion rollback, and the
BoundaryCalibration / CalculationAttempt uniqueness constraints.

Requires POSTGRES_TEST_DATABASE_URL and
``--settings=config.settings.postgresql_test``.
"""

from __future__ import annotations

from config.pg_testing import PostgreSQLTestCase
from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from games.models import Game, SourceType

from classifications.models import (
    BoundaryCalibration,
    CalculationAttempt,
    CalculationEpoch,
    ClassificationSnapshot,
)
from classifications.services.calculations import run_game_calculation
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
)


def _game(name: str) -> Game:
    return Game.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        source_type=SourceType.MANUAL,
    )


def _epoch(epoch_id: str) -> CalculationEpoch:
    return CalculationEpoch.objects.create(
        epoch_id=epoch_id,
        cutoff_at=timezone.now(),
        master_version="STATISTICAL_MODEL_V1.0.0",
    )


def _snapshot(game, epoch, status="READY") -> ClassificationSnapshot:
    return ClassificationSnapshot.objects.create(
        game=game,
        epoch=epoch,
        regime="unified",
        status=status,
        input_population_hash="hash",
        validated_count=20,
        cutoff_at=timezone.now(),
    )


class MigrationAppliedTests(PostgreSQLTestCase):
    def test_snapshot_table_exists(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass('classifications_classificationsnapshot')"
            )
            self.assertIsNotNone(cursor.fetchone()[0])

    def test_partial_unique_current_index_exists(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'classifications_classificationsnapshot'
                  AND indexname = 'classification_snapshot_single_current_uniq'
                """
            )
            self.assertEqual(len(cursor.fetchall()), 1)


class SingleCurrentConstraintTests(PostgreSQLTestCase):
    def test_at_most_one_current_per_game(self):
        game = _game("single-current")
        epoch = _epoch("epoch-a")
        first = _snapshot(game, epoch)
        first.is_current = True
        first.save(update_fields=["is_current"])
        with self.assertRaises(IntegrityError):
            second = _snapshot(game, epoch, status="NO_SUBMISSIONS")
            second.is_current = True
            second.save(update_fields=["is_current"])

    def test_multiple_non_current_snapshots_allowed(self):
        game = _game("multi-history")
        epoch = _epoch("epoch-b")
        _snapshot(game, epoch, status="READY")
        _snapshot(game, epoch, status="READY")
        self.assertEqual(ClassificationSnapshot.objects.filter(game=game).count(), 2)


class PromotionSemanticsTests(PostgreSQLTestCase):
    def test_service_promotes_new_and_demotes_old(self):
        game = _game("promote")
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        create_submission(
            game=game,
            submitted_by=superuser,
            updated_by=superuser,
            challenge=ScoreDistribution(45, 30, 25),
            reward=ScoreDistribution(40, 30, 30),
        )
        for index in range(10):
            user = User.objects.create_user(f"member-{index}")
            create_submission(
                game=game,
                submitted_by=user,
                updated_by=user,
                challenge=ScoreDistribution(45, 30, 25),
                reward=ScoreDistribution(40, 30, 30),
            )
        first_epoch = _epoch("epoch-1")
        run_game_calculation(
            game=game, epoch=first_epoch, attempt_number=1, cutoff_at=timezone.now()
        )
        first = ClassificationSnapshot.objects.get(game=game, epoch=first_epoch)
        self.assertTrue(first.is_current)

        second_epoch = _epoch("epoch-2")
        run_game_calculation(
            game=game, epoch=second_epoch, attempt_number=1, cutoff_at=timezone.now()
        )
        second = ClassificationSnapshot.objects.get(game=game, epoch=second_epoch)
        self.assertTrue(second.is_current)
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(first.is_stale)
        self.assertEqual(
            ClassificationSnapshot.objects.filter(game=game, is_current=True).count(),
            1,
        )

    def test_failed_promotion_rolls_back_prior_current(self):
        game = _game("rollback-promotion")
        epoch = _epoch("epoch-c")
        first = _snapshot(game, epoch)
        first.is_current = True
        first.save(update_fields=["is_current"])

        # A promotion that raises after demoting must leave the prior current.
        try:
            with transaction.atomic():
                ClassificationSnapshot.objects.select_for_update().filter(
                    game=game, is_current=True
                ).update(is_current=False, is_stale=True)
                raise RuntimeError("simulated failure after demote")
        except RuntimeError:
            pass

        first.refresh_from_db()
        self.assertTrue(first.is_current)
        self.assertFalse(first.is_stale)


class ConstraintTests(PostgreSQLTestCase):
    def test_boundary_calibration_unique_per_game_version(self):
        game = _game("boundary-unique")
        BoundaryCalibration.objects.create(
            game=game, master_version="STATISTICAL_MODEL_V1.0.0", delta=1.5
        )
        with self.assertRaises(IntegrityError):
            BoundaryCalibration.objects.create(
                game=game, master_version="STATISTICAL_MODEL_V1.0.0", delta=2.0
            )

    def test_calculation_attempt_unique_per_game_epoch_number(self):
        game = _game("attempt-unique")
        epoch = _epoch("epoch-d")
        CalculationAttempt.objects.create(
            game=game,
            epoch=epoch,
            attempt_number=1,
            status=CalculationAttempt.Status.SUCCEEDED,
        )
        with self.assertRaises(IntegrityError):
            CalculationAttempt.objects.create(
                game=game,
                epoch=epoch,
                attempt_number=1,
                status=CalculationAttempt.Status.SUCCEEDED,
            )

    def test_epoch_protect_from_snapshot_delete(self):
        game = _game("epoch-protect")
        epoch = _epoch("epoch-e")
        _snapshot(game, epoch)
        with self.assertRaises(IntegrityError):
            epoch.delete()
