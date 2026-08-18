"""
Derived-classification persistence and engine tests — SBGC-65.

Database-backed tests for snapshot persistence, atomic current promotion,
previous-success fallback, retry-only-failures coordination, the notifier
scaffold, input hashing, and the published read contract.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from games.models import Game, SourceType

from classifications.models import (
    BoundaryCalibration,
    CalculationAttempt,
    CalculationEpoch,
    ClassificationSnapshot,
)
from classifications.services.calculations import (
    MAX_ATTEMPTS_PER_GAME_EPOCH,
    freeze_population,
    get_published_classification,
    run_game_calculation,
)
from classifications.services.notifications import (
    CalculationFailureNotice,
    CalculationFailureNotifier,
)
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
)


def _game(name: str = "Test Game") -> Game:
    return Game.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        source_type=SourceType.MANUAL,
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


class FreezePopulationTests(TestCase):
    def test_freeze_counts_and_hash(self):
        game = _game()
        first = User.objects.create_user("alpha")
        second = User.objects.create_user("bravo")
        _submission(game, first)
        _submission(game, second)
        population, received, invalid = freeze_population(game, timezone.now())
        self.assertEqual(received, 2)
        self.assertEqual(invalid, 0)
        self.assertEqual(population.raw_n, 2)
        self.assertTrue(population.population_hash)

    def test_edits_after_cutoff_belong_to_next_epoch(self):
        import time as time_module

        game = _game()
        user = User.objects.create_user("alpha")
        submission = _submission(game, user)
        cutoff = timezone.now()
        time_module.sleep(0.02)
        # Edit after the cutoff: the effective state moves to the next epoch.
        from classifications.services.submissions import update_submission

        update_submission(
            submission,
            updated_by=user,
            challenge=ScoreDistribution(20, 30, 50),
        )
        population, received, invalid = freeze_population(game, cutoff)
        self.assertEqual(received, 0)
        self.assertEqual(population.raw_n, 0)

        # After the cutoff the edited state is the current effective state.
        later, later_received, _ = freeze_population(game, timezone.now())
        self.assertEqual(later_received, 1)
        self.assertEqual(later.raw_n, 1)

    def test_input_hash_deterministic(self):
        game = _game()
        for name in ("a", "b", "c"):
            _submission(game, User.objects.create_user(name))
        first, _, _ = freeze_population(game, timezone.now())
        second, _, _ = freeze_population(game, timezone.now())
        self.assertEqual(first.population_hash, second.population_hash)


class RunGameCalculationTests(TestCase):
    def _epoch(self, epoch_id: str = "2026-08-17") -> CalculationEpoch:
        return CalculationEpoch.objects.create(
            epoch_id=epoch_id,
            cutoff_at=timezone.now(),
            master_version="STATISTICAL_MODEL_V1.0.0",
        )

    def test_domain_outcome_no_submissions_snapshot(self):
        game = _game()
        epoch = self._epoch()
        attempt = run_game_calculation(
            game=game,
            epoch=epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
        )
        self.assertEqual(attempt.status, CalculationAttempt.Status.SUCCEEDED)
        snapshot = ClassificationSnapshot.objects.get(game=game, epoch=epoch)
        self.assertEqual(snapshot.status, "NO_SUBMISSIONS")
        self.assertTrue(snapshot.is_current)
        published = get_published_classification(game)
        self.assertFalse(published.available)
        self.assertEqual(published.status, "NO_SUBMISSIONS")

    def test_provisional_regime_ready_snapshot(self):
        game = _game()
        epoch = self._epoch()
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser)
        for index in range(10):
            user = User.objects.create_user(f"member-{index}")
            _submission(game, user)
        attempt = run_game_calculation(
            game=game,
            epoch=epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
        )
        self.assertEqual(attempt.status, CalculationAttempt.Status.SUCCEEDED)
        snapshot = ClassificationSnapshot.objects.get(game=game, epoch=epoch)
        self.assertEqual(snapshot.status, "READY")
        self.assertEqual(snapshot.regime, "provisional")
        self.assertTrue(snapshot.is_current)
        self.assertEqual(snapshot.method_1_status, "READY")
        self.assertIsNotNone(snapshot.confidence_final)
        self.assertEqual(snapshot.confidence_label, "Low")
        published = get_published_classification(game)
        self.assertTrue(published.available)
        self.assertEqual(published.validated_submission_count, 11)
        self.assertEqual(published.confidence, snapshot.confidence_final)

    def test_unified_regime_ready_snapshot_distinct_method_results(self):
        game = _game()
        epoch = self._epoch()
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser, challenge=(60, 20, 20), reward=(50, 25, 25))
        for index in range(19):
            user = User.objects.create_user(f"member-{index}")
            _submission(game, user)
        attempt = run_game_calculation(
            game=game,
            epoch=epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
            bootstrap_replicates=40,
            governance_draws=2,
        )
        self.assertEqual(attempt.status, CalculationAttempt.Status.SUCCEEDED)
        snapshot = ClassificationSnapshot.objects.get(game=game, epoch=epoch)
        self.assertEqual(snapshot.status, "READY")
        self.assertEqual(snapshot.regime, "unified")
        self.assertTrue(snapshot.is_current)
        # All four score sets persist separately.
        for prefix in ("method_1", "method_2", "method_3"):
            self.assertEqual(getattr(snapshot, f"{prefix}_status"), "READY")
            self.assertEqual(sum(getattr(snapshot, f"{prefix}_integer_challenge")), 100)
        self.assertEqual(sum(snapshot.unified_integer_challenge), 100)
        self.assertEqual(sum(snapshot.unified_integer_reward), 100)
        self.assertEqual(sum(snapshot.method_1_integer_challenge), 100)
        self.assertEqual(snapshot.bhpcm_version, "BHPCM_V1")
        self.assertIn("bhpcm", snapshot.provenance)
        self.assertIsNotNone(snapshot.confidence_final)

    def test_ready_to_no_submissions_replaces_current(self):
        """A legitimate NO_SUBMISSIONS outcome replaces a stale READY score."""
        game = _game()
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser)
        for index in range(10):
            _submission(game, User.objects.create_user(f"member-{index}"))

        first_epoch = self._epoch("epoch-1")
        run_game_calculation(
            game=game,
            epoch=first_epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
        )
        self.assertTrue(get_published_classification(game).available)

        from classifications.models import EditorialClassification

        EditorialClassification.objects.filter(game=game).delete()
        second_epoch = self._epoch("epoch-2")
        run_game_calculation(
            game=game,
            epoch=second_epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
        )
        current = ClassificationSnapshot.objects.filter(
            game=game, is_current=True
        ).get()
        self.assertEqual(current.status, "NO_SUBMISSIONS")
        self.assertFalse(current.is_stale)
        published = get_published_classification(game)
        self.assertFalse(published.available)
        self.assertEqual(published.status, "NO_SUBMISSIONS")
        # The old READY remains historical, never current.
        old = ClassificationSnapshot.objects.get(game=game, epoch=first_epoch)
        self.assertFalse(old.is_current)
        self.assertTrue(old.is_stale)

    def test_ready_to_insufficient_anchor_replaces_current(self):
        """A legitimate INSUFFICIENT_ANCHOR outcome replaces a stale READY."""
        game = _game()
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser)
        for index in range(10):
            _submission(game, User.objects.create_user(f"member-{index}"))

        first_epoch = self._epoch("epoch-1")
        run_game_calculation(
            game=game,
            epoch=first_epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
        )
        self.assertTrue(get_published_classification(game).available)

        # Remove the superuser (anchor) and fall below the anchor threshold.
        from classifications.models import EditorialClassification

        EditorialClassification.objects.filter(game=game).delete()
        ordinary = User.objects.create_user("ordinary")
        _submission(game, ordinary)
        _submission(game, User.objects.create_user("ordinary-2"))
        second_epoch = self._epoch("epoch-2")
        run_game_calculation(
            game=game,
            epoch=second_epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
        )
        current = ClassificationSnapshot.objects.filter(
            game=game, is_current=True
        ).get()
        self.assertEqual(current.status, "INSUFFICIENT_ANCHOR")
        published = get_published_classification(game)
        self.assertFalse(published.available)
        self.assertEqual(published.status, "INSUFFICIENT_ANCHOR")

    def test_engine_failure_retains_stale_fallback(self):
        """Only an engine failure retains the prior current snapshot as stale."""
        game = _game()
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser)
        for index in range(10):
            _submission(game, User.objects.create_user(f"member-{index}"))

        first_epoch = self._epoch("epoch-1")
        run_game_calculation(
            game=game,
            epoch=first_epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
        )
        self.assertTrue(get_published_classification(game).available)

        import classifications.services.calculations as service_module

        original = service_module.calculate_game

        def broken(population, **kwargs):
            raise RuntimeError("simulated engine failure")

        service_module.calculate_game = broken
        second_epoch = self._epoch("epoch-2")
        try:
            with self.assertRaises(RuntimeError):
                run_game_calculation(
                    game=game,
                    epoch=second_epoch,
                    attempt_number=1,
                    cutoff_at=timezone.now(),
                )
        finally:
            service_module.calculate_game = original

        current = ClassificationSnapshot.objects.filter(
            game=game, is_current=True
        ).get()
        self.assertEqual(current.status, "READY")
        self.assertTrue(current.is_stale)
        published = get_published_classification(game)
        self.assertTrue(published.available)
        self.assertEqual(published.status, "READY")
        self.assertEqual(published.calculated_at, current.calculated_at)

    def test_single_current_constraint(self):
        game = _game()
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser)
        for index in range(10):
            _submission(game, User.objects.create_user(f"member-{index}"))
        epochs = []
        for day in range(2):
            epoch = self._epoch(f"epoch-{day}")
            epochs.append(epoch)
            run_game_calculation(
                game=game,
                epoch=epoch,
                attempt_number=1,
                cutoff_at=timezone.now(),
            )
        self.assertEqual(
            ClassificationSnapshot.objects.filter(game=game, is_current=True).count(),
            1,
        )
        # The second READY is current; the first is demoted historical.
        current = ClassificationSnapshot.objects.filter(
            game=game, is_current=True
        ).get()
        self.assertEqual(current.epoch_id, epochs[1].pk)  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
        first = ClassificationSnapshot.objects.get(game=game, epoch=epochs[0])
        self.assertFalse(first.is_current)
        self.assertTrue(first.is_stale)

    def test_engine_failure_records_attempt_and_raises(self):
        game = _game()
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser)
        for index in range(19):
            _submission(game, User.objects.create_user(f"member-{index}"))
        epoch = self._epoch()

        import classifications.services.calculations as service_module

        original = service_module.calculate_game

        def broken(population, **kwargs):
            raise RuntimeError("simulated engine failure")

        service_module.calculate_game = broken
        try:
            with self.assertRaises(RuntimeError):
                run_game_calculation(
                    game=game,
                    epoch=epoch,
                    attempt_number=1,
                    cutoff_at=timezone.now(),
                    bootstrap_replicates=8,
                    governance_draws=1,
                )
        finally:
            service_module.calculate_game = original

        attempt = CalculationAttempt.objects.get(game=game, epoch=epoch)
        self.assertEqual(attempt.status, CalculationAttempt.Status.FAILED)
        self.assertEqual(attempt.failure_category, "engine_failure")
        self.assertFalse(ClassificationSnapshot.objects.filter(game=game).exists())

    def test_calculation_error_follows_failure_retry_not_domain_publication(self):
        """CALCULATION_ERROR is an engine failure, never a current domain state."""
        game = _game()
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser)
        for index in range(19):
            _submission(game, User.objects.create_user(f"member-{index}"))
        epoch = self._epoch()

        import classifications.services.calculations as service_module
        from classifications.calculations.engine import GameCalculationResult
        from classifications.calculations.results import CALCULATION_ERROR

        original = service_module.calculate_game

        def error_result(population, **kwargs):
            return GameCalculationResult(
                regime="unified", status=CALCULATION_ERROR, raw_n=population.raw_n
            )

        service_module.calculate_game = error_result
        try:
            with self.assertRaises(RuntimeError):
                run_game_calculation(
                    game=game,
                    epoch=epoch,
                    attempt_number=1,
                    cutoff_at=timezone.now(),
                    bootstrap_replicates=8,
                    governance_draws=1,
                )
        finally:
            service_module.calculate_game = original

        attempt = CalculationAttempt.objects.get(game=game, epoch=epoch)
        self.assertEqual(attempt.status, CalculationAttempt.Status.FAILED)
        self.assertEqual(attempt.failure_category, "engine_failure")
        self.assertFalse(ClassificationSnapshot.objects.filter(game=game).exists())

    def test_notifier_invoked_only_after_final_attempt(self):
        game = _game()
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser)
        for index in range(19):
            _submission(game, User.objects.create_user(f"member-{index}"))

        class RecordingNotifier(CalculationFailureNotifier):
            def __init__(self):
                self.notices: list[CalculationFailureNotice] = []

            def notify(self, notice):
                self.notices.append(notice)

        notifier = RecordingNotifier()
        epoch = self._epoch()

        import classifications.services.calculations as service_module

        original = service_module.calculate_game

        def broken(population, **kwargs):
            raise RuntimeError("simulated engine failure")

        service_module.calculate_game = broken
        try:
            for attempt_number in range(1, MAX_ATTEMPTS_PER_GAME_EPOCH + 1):
                with self.assertRaises(RuntimeError):
                    run_game_calculation(
                        game=game,
                        epoch=epoch,
                        attempt_number=attempt_number,
                        cutoff_at=timezone.now(),
                        bootstrap_replicates=8,
                        governance_draws=1,
                        notifier=notifier,
                    )
        finally:
            service_module.calculate_game = original

        self.assertEqual(len(notifier.notices), 1)
        notice = notifier.notices[0]
        self.assertEqual(notice.game_id, game.pk)
        self.assertEqual(notice.attempt_count, MAX_ATTEMPTS_PER_GAME_EPOCH)
        self.assertEqual(notice.epoch_id, epoch.epoch_id)
        self.assertIn("simulated engine failure", notice.error_summary)

    def test_boundary_calibration_persisted_once(self):
        game = _game()
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        _submission(game, superuser, challenge=(60, 20, 20), reward=(50, 25, 25))
        for index in range(20):
            _submission(game, User.objects.create_user(f"member-{index}"))
        first_epoch = self._epoch("epoch-a")
        run_game_calculation(
            game=game,
            epoch=first_epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
            bootstrap_replicates=40,
            governance_draws=2,
        )
        self.assertTrue(BoundaryCalibration.objects.filter(game=game).exists())
        second_epoch = self._epoch("epoch-b")
        run_game_calculation(
            game=game,
            epoch=second_epoch,
            attempt_number=1,
            cutoff_at=timezone.now(),
            bootstrap_replicates=40,
            governance_draws=2,
        )
        self.assertEqual(BoundaryCalibration.objects.filter(game=game).count(), 1)
