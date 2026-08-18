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

import threading

from config.pg_testing import PostgreSQLTestCase
from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
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


class ConcurrentPromotionTests(TransactionTestCase):
    """True two-connection/thread promotion race on PostgreSQL.

    ``TransactionTestCase`` does not wrap tests in a transaction, so each
    thread uses its own database connection and can see the other thread's
    committed rows.  The partial-unique single-current index is the
    last-resort guarantee: regardless of interleaving, the final state must
    contain exactly one current snapshot.
    """

    def test_concurrent_promotion_leaves_exactly_one_current(self):
        from django.db import connection as django_connection

        if django_connection.vendor != "postgresql":
            self.skipTest("PostgreSQL only")

        game = _game("concurrent-promotion")
        epoch = _epoch("concurrent-epoch")
        initial = _snapshot(game, epoch)
        initial.is_current = True
        initial.save(update_fields=["is_current"])
        snap_a = _snapshot(game, epoch)
        snap_b = _snapshot(game, epoch)

        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def promote(snapshot_id: int, label: str) -> None:
            try:
                barrier.wait(timeout=10)
                django_connection.close()  # fresh thread-local connection
                try:
                    with transaction.atomic():
                        ClassificationSnapshot.objects.select_for_update().filter(
                            game=game, is_current=True
                        ).update(is_current=False, is_stale=True)
                        snap = ClassificationSnapshot.objects.get(pk=snapshot_id)
                        snap.is_current = True
                        snap.became_current_at = timezone.now()
                        snap.save(update_fields=["is_current", "became_current_at"])
                    outcomes.append(f"{label}-ok")
                except IntegrityError:
                    outcomes.append(f"{label}-integrity")
            finally:
                django_connection.close()

        thread_a = threading.Thread(target=promote, args=(snap_a.pk, "a"))
        thread_b = threading.Thread(target=promote, args=(snap_b.pk, "b"))
        thread_a.start()
        thread_b.start()
        thread_a.join(timeout=30)
        thread_b.join(timeout=30)

        self.assertFalse(thread_a.is_alive())
        self.assertFalse(thread_b.is_alive())
        self.assertEqual(
            ClassificationSnapshot.objects.filter(game=game, is_current=True).count(),
            1,
        )
        # Exactly one current winner; the loser either serialized behind it
        # (promoting it away) or was rejected by the unique index.
        self.assertGreaterEqual(len(outcomes), 1)
