"""
Epoch crash-resumption & atomic finalization tests — SBGC-197 (R4-02).

Uses ``TransactionTestCase`` (per the audit): claims, rollbacks, and the
claim -> calculate -> finalize phases must be exercised against real
transaction boundaries, which ``TestCase``'s wrapping transaction masks.

Covers: interrupted-run attempt allocation without unique-constraint
collisions, idempotent skip of already-succeeded Games, exhaustion of the
per-Game attempt budget, atomic rollback of snapshot promotion/demotion on a
finalization failure, and command-level resume of a partially completed epoch.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone
from games.models import Game, SourceType

from classifications.models import (
    CalculationAttempt,
    CalculationEpoch,
    ClassificationSnapshot,
)
from classifications.services import calculations as service_module
from classifications.services.calculations import (
    MAX_ATTEMPTS_PER_GAME_EPOCH,
    ClaimStatus,
    claim_game_calculation_attempt,
    execute_pure_calculation,
    finalize_successful_calculation,
    record_failed_calculation_attempt,
)
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
)


def _game(name: str, slug: str) -> Game:
    return Game.objects.create(
        name=name,
        slug=slug,
        source_type=SourceType.MANUAL,
    )


def _epoch(epoch_id: str = "resume-2026-09-06") -> CalculationEpoch:
    return CalculationEpoch.objects.create(
        epoch_id=epoch_id,
        cutoff_at=timezone.now(),
        master_version="STATISTICAL_MODEL_V1.0.0",
    )


def _claimed(epoch: CalculationEpoch, game_id: int) -> CalculationAttempt:
    """Claim the next attempt, asserting the claim actually happened."""
    status, attempt = claim_game_calculation_attempt(epoch, game_id)
    assert status is ClaimStatus.CLAIMED
    assert attempt is not None
    return attempt


def _submission(game, user, challenge=(45, 30, 25), reward=(40, 30, 30)):
    return create_submission(
        game=game,
        submitted_by=user,
        updated_by=user,
        challenge=ScoreDistribution(*challenge),
        reward=ScoreDistribution(*reward),
        notes="",
    )


class ClaimResumeTests(TransactionTestCase):
    """Phase-1 claim: allocation, skip, and exhaustion semantics."""

    def setUp(self):
        self.game = _game("Hades", "hades")
        self.epoch = _epoch("claim-resume")

    def test_interrupted_run_allocates_incremented_attempt_number(self):
        """Resuming an interrupted epoch allocates attempt 2, never collides."""
        attempt_1 = _claimed(self.epoch, self.game.pk)
        self.assertEqual(attempt_1.attempt_number, 1)
        self.assertEqual(attempt_1.status, CalculationAttempt.Status.RUNNING)

        record_failed_calculation_attempt(
            attempt_1,
            failure_category="engine_failure",
            error_summary="OOM simulated crash",
        )
        attempt_1.refresh_from_db()
        self.assertEqual(attempt_1.status, CalculationAttempt.Status.FAILED)

        # Second invocation resumes the same epoch without IntegrityError.
        attempt_2 = _claimed(self.epoch, self.game.pk)
        self.assertEqual(attempt_2.attempt_number, 2)
        self.assertNotEqual(attempt_1.pk, attempt_2.pk)
        self.assertEqual(
            CalculationAttempt.objects.filter(epoch=self.epoch, game=self.game).count(),
            2,
        )

    def test_attempt_budget_is_exhausted_after_max_attempts(self):
        """A Game whose budget is consumed returns EXHAUSTED, never attempt 5."""
        for attempt_number in range(1, MAX_ATTEMPTS_PER_GAME_EPOCH + 1):
            attempt = _claimed(self.epoch, self.game.pk)
            self.assertEqual(attempt.attempt_number, attempt_number)
            record_failed_calculation_attempt(
                attempt,
                failure_category="engine_failure",
                error_summary="boom",
            )

        status, attempt = claim_game_calculation_attempt(self.epoch, self.game.pk)
        self.assertEqual(status, ClaimStatus.EXHAUSTED)
        self.assertIsNone(attempt)

    def test_already_succeeded_game_is_skipped_on_resume(self):
        """A Game SUCCEEDED in a prior run of the same epoch is skipped."""
        attempt = _claimed(self.epoch, self.game.pk)
        pure = execute_pure_calculation(game=self.game, cutoff_at=timezone.now())
        finalize_successful_calculation(attempt, pure)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, CalculationAttempt.Status.SUCCEEDED)

        status, resumed = claim_game_calculation_attempt(self.epoch, self.game.pk)
        self.assertEqual(status, ClaimStatus.SKIPPED_ALREADY_SUCCEEDED)
        self.assertIsNone(resumed)


class FinalizationAtomicityTests(TransactionTestCase):
    """Phase-3 atomicity: promotion + attempt SUCCEEDED commit or roll back."""

    def test_finalization_failure_rolls_back_snapshot_and_demotion(self):
        game = _game("Atomic Rollback", "atomic-rollback")
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser)
        for index in range(10):
            _submission(game, User.objects.create_user(f"member-{index}"))

        # Epoch A produces the current published snapshot.
        epoch_a = _epoch("atomic-a")
        attempt_a = _claimed(epoch_a, game.pk)
        finalize_successful_calculation(
            attempt_a,
            execute_pure_calculation(game=game, cutoff_at=timezone.now()),
        )
        current_a = ClassificationSnapshot.objects.filter(
            game=game, is_current=True
        ).get()

        # Epoch B finalization fails at boundary persistence -> full rollback:
        # the new snapshot is gone, snapshot A is still current (demotion was
        # rolled back), and no second current snapshot exists.
        epoch_b = _epoch("atomic-b")
        attempt_b = _claimed(epoch_b, game.pk)
        pure_b = execute_pure_calculation(game=game, cutoff_at=timezone.now())
        self.assertEqual(pure_b.result.status, "READY")

        with mock.patch.object(
            service_module, "_persist_boundary", side_effect=RuntimeError("disk full")
        ):
            with self.assertRaises(RuntimeError):
                finalize_successful_calculation(attempt_b, pure_b)

        self.assertFalse(
            ClassificationSnapshot.objects.filter(game=game, epoch=epoch_b).exists()
        )
        self.assertEqual(
            ClassificationSnapshot.objects.filter(game=game, is_current=True).count(),
            1,
        )
        current_a.refresh_from_db()
        self.assertTrue(current_a.is_current)

        # The rolled-back attempt is still recordable as FAILED in isolation.
        attempt_b.refresh_from_db()
        self.assertEqual(attempt_b.status, CalculationAttempt.Status.RUNNING)
        record_failed_calculation_attempt(
            attempt_b,
            failure_category="engine_failure",
            error_summary="Simulated boundary crash",
        )
        attempt_b.refresh_from_db()
        self.assertEqual(attempt_b.status, CalculationAttempt.Status.FAILED)


class CommandResumptionTests(TransactionTestCase):
    """End-to-end: re-invoking the daily command resumes an interrupted epoch."""

    def test_command_resumes_partial_epoch_without_collision(self):
        game_a = _game("Resume A", "resume-a")
        game_b = _game("Resume B", "resume-b")
        game_c = _game("Resume C", "resume-c")
        epoch_id = "resume-command-epoch"

        # Simulate a prior interrupted run: game A failed attempt 1; game C
        # already SUCCEEDED attempt 1; game B never started.
        partial_epoch = _epoch(epoch_id)
        attempt_a = _claimed(partial_epoch, game_a.pk)
        record_failed_calculation_attempt(
            attempt_a,
            failure_category="engine_failure",
            error_summary="crashed mid-run",
        )
        attempt_c = _claimed(partial_epoch, game_c.pk)
        finalize_successful_calculation(
            attempt_c,
            execute_pure_calculation(game=game_c, cutoff_at=timezone.now()),
        )

        # Re-invoke the command: A resumes at attempt 2, B runs attempt 1, and
        # C is skipped — no IntegrityError and every game SUCCEEDED.
        call_command(
            "run_daily_classification",
            "--epoch-id",
            epoch_id,
            "--game-ids",
            f"{game_a.pk},{game_b.pk},{game_c.pk}",
            "--retry-delay",
            "0",
        )

        attempts_a = list(
            CalculationAttempt.objects.filter(
                epoch=partial_epoch, game=game_a
            ).order_by("attempt_number")
        )
        self.assertEqual([a.attempt_number for a in attempts_a], [1, 2])
        self.assertEqual(attempts_a[0].status, CalculationAttempt.Status.FAILED)
        self.assertEqual(attempts_a[1].status, CalculationAttempt.Status.SUCCEEDED)

        attempts_c = list(
            CalculationAttempt.objects.filter(
                epoch=partial_epoch, game=game_c
            ).order_by("attempt_number")
        )
        self.assertEqual([a.attempt_number for a in attempts_c], [1])
        self.assertEqual(attempts_c[0].status, CalculationAttempt.Status.SUCCEEDED)

        partial_epoch.refresh_from_db()
        self.assertEqual(partial_epoch.status, CalculationEpoch.Status.COMPLETED)
        self.assertEqual(partial_epoch.games_succeeded, 3)
        self.assertEqual(partial_epoch.games_failed, 0)
