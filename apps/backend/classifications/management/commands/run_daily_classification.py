"""
Run the canonical daily derived-classification epoch — SBGC-65 / SBGC-197.

Claims and calculates each Game through the three-phase pipeline (claim →
calculate → finalize).  Engine failures are retried within the invocation
(initial attempt plus three retries = maximum four attempts per Game per
epoch), and re-invoking the command against the same epoch resumes safely:
Games that already SUCCEEDED are skipped and still-failed Games continue at
their next free attempt number — never colliding on the
``(game, epoch, attempt_number)`` unique constraint (R4-02).

The engine is scheduler-vendor independent: a deployment cron (or platform
scheduler) invokes this command once per day; nothing here depends on a
specific scheduler product.
"""

from __future__ import annotations

import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from games.models import Game

from classifications.calculations.constants import MASTER_VERSION
from classifications.models import CalculationEpoch
from classifications.services.calculations import (
    MAX_ATTEMPTS_PER_GAME_EPOCH,
    ClaimStatus,
    claim_game_calculation_attempt,
    execute_pure_calculation,
    fail_engine_attempt,
    finalize_successful_calculation,
)
from classifications.services.notifications import CalculationFailureNotifier

logger = logging.getLogger(__name__)


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

        succeeded = 0
        failed: list[Game] = []
        pending: list[Game] = list(games)
        for wave in range(1, MAX_ATTEMPTS_PER_GAME_EPOCH + 1):
            wave_failed: list[Game] = []
            for game in pending:
                claim_status, attempt = claim_game_calculation_attempt(epoch, game.pk)
                if claim_status is ClaimStatus.SKIPPED_ALREADY_SUCCEEDED:
                    # Idempotent resume: the Game already SUCCEEDED this epoch.
                    succeeded += 1
                    self.stdout.write(
                        f"Game {game.slug}: already SUCCEEDED in epoch "
                        f"{epoch.epoch_id}. Skipping."
                    )
                    continue
                if claim_status is ClaimStatus.EXHAUSTED:
                    # Attempt budget consumed by an earlier invocation.
                    failed.append(game)
                    continue

                assert attempt is not None
                try:
                    pure = execute_pure_calculation(
                        game=game,
                        cutoff_at=cutoff,
                        bootstrap_replicates=options["bootstrap_replicates"],
                        governance_draws=options["governance_draws"],
                    )
                    finalize_successful_calculation(attempt, pure)
                    succeeded += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Game {game.slug}: Attempt "
                            f"{attempt.attempt_number} SUCCEEDED."
                        )
                    )
                except Exception as exc:
                    summary = f"{exc.__class__.__name__}: {exc}"[:1000]
                    fail_engine_attempt(attempt, summary, notifier=notifier)
                    self.stderr.write(
                        self.style.ERROR(
                            f"Game {game.slug}: Attempt "
                            f"{attempt.attempt_number} FAILED: {exc}"
                        )
                    )
                    wave_failed.append(game)

            pending = wave_failed
            if not pending:
                break
            if wave < MAX_ATTEMPTS_PER_GAME_EPOCH:
                self.stdout.write(
                    self.style.WARNING(
                        f"Retrying {len(pending)} failed game(s) after "
                        f"{retry_delay}s (wave {wave + 1})."
                    )
                )
                time.sleep(retry_delay)
        failed = [*failed, *pending]

        epoch.games_attempted = games.count()
        epoch.games_succeeded = succeeded
        epoch.games_failed = len(failed)
        epoch.status = (
            CalculationEpoch.Status.COMPLETED
            if not failed
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
                f"{epoch.games_failed} failed."
            )
        )


__all__ = ["Command"]
