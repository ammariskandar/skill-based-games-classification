"""
Recalculation and status-logic tests — SBGC-66 (sections 9 and 10).
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from games.models import Game, SourceType

from classifications.models import CalculationEpoch, ClassificationSnapshot
from classifications.services.calculations import (
    freeze_population,
    get_published_classification,
    run_game_calculation,
)
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
)


def _game(name: str) -> Game:
    return Game.objects.create(
        name=name, slug=name.lower().replace(" ", "-"), source_type=SourceType.MANUAL
    )


class RecalculationTests(TestCase):
    def _provisional_population(self, game, superuser, community_count):
        create_submission(
            game=game,
            submitted_by=superuser,
            updated_by=superuser,
            challenge=ScoreDistribution(micro=50, mystiko=20, macro=30),
            reward=ScoreDistribution(micro=20, mystiko=50, macro=30),
        )
        for index in range(community_count):
            user = User.objects.create_user(f"member-{index}")
            create_submission(
                game=game,
                submitted_by=user,
                updated_by=user,
                challenge=ScoreDistribution(micro=45, mystiko=25, macro=30),
                reward=ScoreDistribution(micro=40, mystiko=30, macro=30),
            )

    def test_new_submission_changes_hash_and_replaces_current(self):
        game = _game("recalc")
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        self._provisional_population(game, superuser, 10)

        cutoff_a = timezone.now()
        population_a, _, _ = freeze_population(game, cutoff_a)
        hash_a = population_a.population_hash
        epoch_a = CalculationEpoch.objects.create(
            epoch_id="epoch-a", cutoff_at=cutoff_a, master_version="V"
        )
        run_game_calculation(
            game=game, epoch=epoch_a, attempt_number=1, cutoff_at=cutoff_a
        )
        snapshot_a = ClassificationSnapshot.objects.get(game=game, epoch=epoch_a)
        self.assertTrue(snapshot_a.is_current)

        # Add a new valid submission -> the population changes.
        extra = User.objects.create_user("new-member")
        create_submission(
            game=game,
            submitted_by=extra,
            updated_by=extra,
            challenge=ScoreDistribution(micro=55, mystiko=15, macro=30),
            reward=ScoreDistribution(micro=30, mystiko=40, macro=30),
        )

        cutoff_b = timezone.now()
        population_b, _, _ = freeze_population(game, cutoff_b)
        hash_b = population_b.population_hash
        self.assertNotEqual(hash_a, hash_b)

        epoch_b = CalculationEpoch.objects.create(
            epoch_id="epoch-b", cutoff_at=cutoff_b, master_version="V"
        )
        run_game_calculation(
            game=game, epoch=epoch_b, attempt_number=1, cutoff_at=cutoff_b
        )
        snapshot_b = ClassificationSnapshot.objects.get(game=game, epoch=epoch_b)
        self.assertTrue(snapshot_b.is_current)
        snapshot_a.refresh_from_db()
        self.assertFalse(snapshot_a.is_current)
        self.assertTrue(snapshot_a.is_stale)
        self.assertEqual(snapshot_b.validated_count, 12)
        self.assertEqual(
            ClassificationSnapshot.objects.filter(game=game, is_current=True).count(),
            1,
        )

    def test_engine_failure_does_not_partially_replace_current(self):
        game = _game("recalc-fail")
        superuser = User.objects.create_superuser(
            "root2", email="root2@example.com", password="pw"
        )
        self._provisional_population(game, superuser, 10)
        epoch_a = CalculationEpoch.objects.create(
            epoch_id="fail-a", cutoff_at=timezone.now(), master_version="V"
        )
        run_game_calculation(
            game=game,
            epoch=epoch_a,
            attempt_number=1,
            cutoff_at=timezone.now(),
        )
        current_before = ClassificationSnapshot.objects.filter(
            game=game, is_current=True
        ).get()

        import classifications.services.calculations as service_module

        original = service_module.calculate_game

        def broken(population, **kwargs):
            raise RuntimeError("boom")

        service_module.calculate_game = broken
        epoch_b = CalculationEpoch.objects.create(
            epoch_id="fail-b", cutoff_at=timezone.now(), master_version="V"
        )
        try:
            with self.assertRaises(RuntimeError):
                run_game_calculation(
                    game=game,
                    epoch=epoch_b,
                    attempt_number=1,
                    cutoff_at=timezone.now(),
                )
        finally:
            service_module.calculate_game = original

        current_after = ClassificationSnapshot.objects.filter(
            game=game, is_current=True
        ).get()
        self.assertEqual(current_after.pk, current_before.pk)
        self.assertTrue(current_after.is_stale)
        published = get_published_classification(game)
        self.assertTrue(published.available)


class StatusLogicTests(TestCase):
    def test_legitimate_non_ready_domain_outcome_becomes_current(self):
        game = _game("status-nonready")
        superuser = User.objects.create_superuser(
            "root3", email="root3@example.com", password="pw"
        )
        create_submission(
            game=game,
            submitted_by=superuser,
            updated_by=superuser,
            challenge=ScoreDistribution(micro=50, mystiko=20, macro=30),
            reward=ScoreDistribution(micro=20, mystiko=50, macro=30),
        )
        for index in range(10):
            user = User.objects.create_user(f"status-m{index}")
            create_submission(
                game=game,
                submitted_by=user,
                updated_by=user,
                challenge=ScoreDistribution(micro=45, mystiko=25, macro=30),
                reward=ScoreDistribution(micro=40, mystiko=30, macro=30),
            )
        epoch_a = CalculationEpoch.objects.create(
            epoch_id="status-a", cutoff_at=timezone.now(), master_version="V"
        )
        run_game_calculation(
            game=game, epoch=epoch_a, attempt_number=1, cutoff_at=timezone.now()
        )
        self.assertTrue(get_published_classification(game).available)

        # Delete all submissions -> NO_SUBMISSIONS becomes current, not an
        # obsolete READY.
        from classifications.models import EditorialClassification

        EditorialClassification.objects.filter(game=game).delete()
        epoch_b = CalculationEpoch.objects.create(
            epoch_id="status-b", cutoff_at=timezone.now(), master_version="V"
        )
        run_game_calculation(
            game=game, epoch=epoch_b, attempt_number=1, cutoff_at=timezone.now()
        )
        current = ClassificationSnapshot.objects.filter(
            game=game, is_current=True
        ).get()
        self.assertEqual(current.status, "NO_SUBMISSIONS")
        published = get_published_classification(game)
        self.assertFalse(published.available)
        self.assertEqual(published.status, "NO_SUBMISSIONS")
