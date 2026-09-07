"""
Content-addressed skip for unchanged daily classifications — SBGC-198 (R4-03).

A calculation is a pure function of its frozen input population and the
normative algorithm versions: when the published current snapshot already
matches both, recomputation would produce an identical snapshot.  These tests
assert that the daily pipeline skips such Games (no attempt claim, no engine
call, no duplicate snapshot), recomputes when inputs or algorithm versions
change, and recomputes a stale retained fallback after a failed attempt.

``TransactionTestCase`` is used so the cross-epoch row states commit for real.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone
from games.models import Game, SourceType

from classifications.calculations.profiles import (
    Profile,
    SubmissionRecord,
    canonical_population_hash,
)
from classifications.models import (
    CalculationAttempt,
    CalculationEpoch,
    ClassificationSnapshot,
)
from classifications.services import calculations as service_module
from classifications.services.calculations import (
    ClaimStatus,
    check_and_claim_game_calculation,
    execute_pure_calculation,
    finalize_successful_calculation,
    should_skip_unchanged_game,
)
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
)

MASTER_VERSION = service_module.MASTER_VERSION


def _game(name: str, slug: str) -> Game:
    return Game.objects.create(
        name=name,
        slug=slug,
        source_type=SourceType.MANUAL,
    )


def _epoch(epoch_id: str) -> CalculationEpoch:
    return CalculationEpoch.objects.create(
        epoch_id=epoch_id,
        cutoff_at=timezone.now(),
        master_version=MASTER_VERSION,
    )


def _submission(game, user, challenge=(45, 30, 25), reward=(40, 30, 30)):
    return create_submission(
        game=game,
        submitted_by=user,
        updated_by=user,
        challenge=ScoreDistribution(*challenge),
        reward=ScoreDistribution(*reward),
        notes="",
    )


class ContentAddressedSkipTests(TransactionTestCase):
    """Service-level skip decision and command-level end-to-end behaviour."""

    def _publish_no_submissions(self, game: Game, epoch: CalculationEpoch):
        """Real engine domain outcome (NO_SUBMISSIONS) becomes the current."""
        population, received, invalid = service_module.freeze_population(
            game, timezone.now()
        )
        claim_status, attempt, _ = check_and_claim_game_calculation(
            epoch, game.pk, population.population_hash
        )
        assert claim_status is ClaimStatus.CLAIMED
        assert attempt is not None
        pure = execute_pure_calculation(
            game=game,
            cutoff_at=timezone.now(),
            frozen_population=(population, received, invalid),
        )
        finalize_successful_calculation(attempt, pure)
        return population

    def test_identical_population_and_versions_skips(self):
        game = _game("Skip Game", "skip-game")
        self._publish_no_submissions(game, _epoch("skip-d1"))

        frozen = service_module.freeze_population(game, timezone.now())
        is_unchanged, snapshot = should_skip_unchanged_game(
            game.pk, frozen[0].population_hash
        )
        self.assertTrue(is_unchanged)
        self.assertIsNotNone(snapshot)
        self.assertEqual(ClassificationSnapshot.objects.filter(game=game).count(), 1)

    def test_command_skips_without_engine_call_and_records_counter(self):
        game = _game("Command Skip", "command-skip")
        call_command(
            "run_daily_classification",
            "--epoch-id",
            "cmd-skip-d1",
            "--game-ids",
            str(game.pk),
            "--retry-delay",
            "0",
        )
        self.assertEqual(ClassificationSnapshot.objects.filter(game=game).count(), 1)

        # Second epoch with unchanged inputs: engine must not run and no
        # duplicate snapshot may be created.
        with mock.patch.object(
            service_module, "calculate_game", side_effect=RuntimeError("engine ran")
        ) as engine:
            call_command(
                "run_daily_classification",
                "--epoch-id",
                "cmd-skip-d2",
                "--game-ids",
                str(game.pk),
                "--retry-delay",
                "0",
            )
            engine.assert_not_called()

        epoch_d2 = CalculationEpoch.objects.get(epoch_id="cmd-skip-d2")
        self.assertEqual(epoch_d2.games_skipped_unchanged, 1)
        self.assertEqual(epoch_d2.games_succeeded, 0)
        self.assertEqual(epoch_d2.games_failed, 0)
        self.assertEqual(ClassificationSnapshot.objects.filter(game=game).count(), 1)

    def test_new_submission_forces_recalculation(self):
        game = _game("Changed Game", "changed-game")
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser)
        for index in range(10):
            _submission(game, User.objects.create_user(f"member-{index}"))

        first_epoch = _epoch("changed-d1")
        frozen_1 = service_module.freeze_population(game, timezone.now())
        claim, attempt, _ = check_and_claim_game_calculation(
            first_epoch, game.pk, frozen_1[0].population_hash
        )
        self.assertEqual(claim, ClaimStatus.CLAIMED)
        assert attempt is not None
        pure_1 = execute_pure_calculation(
            game=game,
            cutoff_at=timezone.now(),
            frozen_population=frozen_1,
        )
        finalize_successful_calculation(attempt, pure_1)
        first_snapshot = ClassificationSnapshot.objects.get(
            game=game, epoch=first_epoch
        )

        # A new submission changes the population hash -> must recompute.
        _submission(game, User.objects.create_user("member-extra"))
        frozen_2 = service_module.freeze_population(game, timezone.now())
        self.assertNotEqual(frozen_1[0].population_hash, frozen_2[0].population_hash)
        is_unchanged, _ = should_skip_unchanged_game(
            game.pk, frozen_2[0].population_hash
        )
        self.assertFalse(is_unchanged)

        second_epoch = _epoch("changed-d2")
        claim, attempt, _ = check_and_claim_game_calculation(
            second_epoch, game.pk, frozen_2[0].population_hash
        )
        self.assertEqual(claim, ClaimStatus.CLAIMED)
        assert attempt is not None
        pure_2 = execute_pure_calculation(
            game=game,
            cutoff_at=timezone.now(),
            frozen_population=frozen_2,
        )
        finalize_successful_calculation(attempt, pure_2)
        second_snapshot = ClassificationSnapshot.objects.get(
            game=game, epoch=second_epoch
        )
        self.assertNotEqual(
            first_snapshot.input_population_hash,
            second_snapshot.input_population_hash,
        )
        self.assertEqual(
            ClassificationSnapshot.objects.filter(game=game, is_current=True).count(),
            1,
        )
        second_snapshot.refresh_from_db()
        self.assertTrue(second_snapshot.is_current)

    def test_algorithm_version_bump_forces_recalculation(self):
        game = _game("Version Game", "version-game")
        self._publish_no_submissions(game, _epoch("version-d1"))
        frozen = service_module.freeze_population(game, timezone.now())

        # Simulate a snapshot published under an older normative version.
        current = ClassificationSnapshot.objects.get(game=game, is_current=True)
        current.master_version = "STATISTICAL_MODEL_V0.9.0-LEGACY"
        current.save(update_fields=["master_version"])

        is_unchanged, _ = should_skip_unchanged_game(game.pk, frozen[0].population_hash)
        self.assertFalse(is_unchanged)

        second_epoch = _epoch("version-d2")
        claim, attempt, _ = check_and_claim_game_calculation(
            second_epoch, game.pk, frozen[0].population_hash
        )
        self.assertEqual(claim, ClaimStatus.CLAIMED)
        assert attempt is not None
        pure = execute_pure_calculation(
            game=game,
            cutoff_at=timezone.now(),
            frozen_population=frozen,
        )
        finalize_successful_calculation(attempt, pure)
        fresh = ClassificationSnapshot.objects.get(game=game, is_current=True)
        self.assertEqual(fresh.master_version, MASTER_VERSION)

    def test_missing_or_stale_current_snapshot_forces_calculation(self):
        game = _game("Fallback Game", "fallback-game")
        frozen = service_module.freeze_population(game, timezone.now())

        # No snapshot at all -> compute.
        is_unchanged, snapshot = should_skip_unchanged_game(
            game.pk, frozen[0].population_hash
        )
        self.assertFalse(is_unchanged)
        self.assertIsNone(snapshot)

        # Publish, then mark the retained fallback stale (a newer epoch failed
        # to refresh) -> must recompute, never skip a stale result.
        self._publish_no_submissions(game, _epoch("fallback-d1"))
        current = ClassificationSnapshot.objects.get(game=game, is_current=True)
        current.is_stale = True
        current.save(update_fields=["is_stale"])
        is_unchanged, snapshot = should_skip_unchanged_game(
            game.pk, frozen[0].population_hash
        )
        self.assertFalse(is_unchanged)

    def test_population_hash_ordering_invariance(self):
        """Canonical hashing is independent of submission ordering."""
        records_a = [
            SubmissionRecord(
                identifier=f"submission-{index}",
                challenge=Profile(micro=50, macro=25, mystiko=25),
                reward=Profile(micro=40, macro=30, mystiko=30),
                role="community",
            )
            for index in range(3)
        ]
        records_b = list(reversed(records_a))
        self.assertEqual(
            canonical_population_hash(records_a),
            canonical_population_hash(records_b),
        )


class PriorFailedAttemptTests(TransactionTestCase):
    """A failed attempt with no persisted snapshot must still compute."""

    def test_failed_prior_attempt_without_snapshot_forces_calculation(self):
        game = _game("Prior Fail", "prior-fail")
        epoch = _epoch("prior-fail-d1")

        # Simulate an interrupted previous epoch: a FAILED attempt, no snapshot.
        status, attempt, _ = check_and_claim_game_calculation(
            epoch, game.pk, "some-hash"
        )
        self.assertEqual(status, ClaimStatus.CLAIMED)
        assert attempt is not None
        service_module.record_failed_calculation_attempt(
            attempt,
            failure_category="engine_failure",
            error_summary="crashed",
        )

        frozen = service_module.freeze_population(game, timezone.now())
        is_unchanged, snapshot = should_skip_unchanged_game(
            game.pk, frozen[0].population_hash
        )
        self.assertFalse(is_unchanged)
        self.assertIsNone(snapshot)

        # A fresh epoch computes normally.
        fresh_epoch = _epoch("prior-fail-d2")
        claim, attempt, _ = check_and_claim_game_calculation(
            fresh_epoch, game.pk, frozen[0].population_hash
        )
        self.assertEqual(claim, ClaimStatus.CLAIMED)
        assert attempt is not None
        pure = execute_pure_calculation(
            game=game,
            cutoff_at=timezone.now(),
            frozen_population=frozen,
        )
        finalize_successful_calculation(attempt, pure)
        self.assertTrue(
            ClassificationSnapshot.objects.filter(game=game, is_current=True).exists()
        )
        self.assertEqual(
            CalculationAttempt.objects.filter(
                epoch=epoch, game=game, status=CalculationAttempt.Status.FAILED
            ).count(),
            1,
        )
