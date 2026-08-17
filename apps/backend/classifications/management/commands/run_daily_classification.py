"""
Run the canonical daily derived-classification epoch — SBGC-65.

Freezes each Game's submission population at ``cutoff_at``, runs the
calculation engine outside long transactions, and atomically promotes
successful snapshots.  Engine failures are retried (initial attempt plus
three retries = maximum four attempts per Game per epoch); only failed
Games are retried.  After the final failed attempt the failure-notification
scaffold is invoked.

The engine is scheduler-vendor independent: a deployment cron (or platform
scheduler) invokes this command once per day; nothing here depends on a
specific scheduler product.
"""

from __future__ import annotations

import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from games.models import Game

from classifications.calculations.constants import MASTER_VERSION
from classifications.models import CalculationEpoch
from classifications.services.calculations import (
    MAX_ATTEMPTS_PER_GAME_EPOCH,
    run_game_calculation,
)
from classifications.services.notifications import (
    CalculationFailureNotifier,
)


class Command(BaseCommand):
    help = "Run one daily derived-classification calculation epoch."

    def add_arguments(self, parser):
        parser.add_argument(
            "--epoch-id",
            default=None,
            help="Epoch identifier; defaults to the calendar date (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--cutoff",
            default=None,
            help="Cutoff timestamp; defaults to now.",
        )
        parser.add_argument(
            "--game-ids",
            default=None,
            help="Comma-separated Game ids to restrict the run.",
        )
        parser.add_argument(
            "--bootstrap-replicates",
            type=int,
            default=None,
            help="Override the frozen bootstrap replicate count (tests/simulation).",
        )
        parser.add_argument(
            "--governance-draws",
            type=int,
            default=None,
            help="Override the frozen governance-draw count (tests/simulation).",
        )
        parser.add_argument(
            "--retry-delay",
            type=float,
            default=None,
            help="Seconds between retry waves; default settings-driven.",
        )

    def handle(self, *args, **options):
        epoch_id = options["epoch_id"] or timezone.localdate().isoformat()
        cutoff = options["cutoff"] or timezone.now()
        retry_delay = (
            options["retry_delay"]
            if options["retry_delay"] is not None
            else float(getattr(settings, "CLASSIFICATION_RETRY_DELAY_SECONDS", "60"))
        )
        notifier = CalculationFailureNotifier()

        games = Game.objects.all()
        if options["game_ids"]:
            try:
                ids = [int(part) for part in options["game_ids"].split(",")]
            except ValueError as exc:
                raise CommandError(
                    "--game-ids must be comma-separated integers"
                ) from exc
            games = games.filter(pk__in=ids)

        epoch, created = CalculationEpoch.objects.get_or_create(
            epoch_id=epoch_id,
            defaults={
                "cutoff_at": cutoff,
                "master_version": MASTER_VERSION,
                "status": CalculationEpoch.Status.RUNNING,
            },
        )
        if not created:
            # Resuming a partially completed epoch: keep the original cutoff.
            cutoff = epoch.cutoff_at

        failed_games: list[Game] = list(games)
        for attempt_number in range(1, MAX_ATTEMPTS_PER_GAME_EPOCH + 1):
            wave = list(failed_games)
            if not wave:
                break
            still_failed: list[Game] = []
            for game in wave:
                try:
                    run_game_calculation(
                        game=game,
                        epoch=epoch,
                        attempt_number=attempt_number,
                        cutoff_at=cutoff,
                        bootstrap_replicates=options["bootstrap_replicates"],
                        governance_draws=options["governance_draws"],
                        notifier=notifier,
                    )
                except Exception:
                    still_failed.append(game)
            failed_games = still_failed
            if not failed_games:
                break
            if attempt_number < MAX_ATTEMPTS_PER_GAME_EPOCH:
                self.stdout.write(
                    self.style.WARNING(
                        f"Retrying {len(failed_games)} failed game(s) "
                        f"after {retry_delay}s (attempt {attempt_number + 1})."
                    )
                )
                time.sleep(retry_delay)

        epoch.games_attempted = games.count()
        epoch.games_succeeded = epoch.games_attempted - len(failed_games)
        epoch.games_failed = len(failed_games)
        epoch.status = (
            CalculationEpoch.Status.COMPLETED
            if not failed_games
            else CalculationEpoch.Status.PARTIAL
        )
        epoch.completed_at = timezone.now()
        epoch.save(
            update_fields=[
                "games_attempted",
                "games_succeeded",
                "games_failed",
                "status",
                "completed_at",
            ]
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Epoch {epoch_id} complete: {epoch.games_succeeded} succeeded, "
                f"{epoch.games_failed} failed after "
                f"{MAX_ATTEMPTS_PER_GAME_EPOCH} attempts."
            )
        )


__all__ = ["Command"]
