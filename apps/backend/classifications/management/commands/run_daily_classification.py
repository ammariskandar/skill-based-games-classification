"""
Run the canonical daily derived-classification epoch — SBGC-65 / SBGC-197 / SBGC-198.

Each Game is evaluated through the three-phase pipeline (claim → calculate →
finalize), with two content-aware gates ahead of any attempt claim:

1. Resume gate — a Game that already SUCCEEDED earlier in this epoch is
   skipped (SBGC-197 idempotent resume).
2. Content-addressed gate (SBGC-198 / R4-03) — if the published current
   snapshot already reflects the same frozen input population hash AND the
   same normative algorithm versions, the Game is skipped entirely: no
   attempt is claimed, no CPU/bootstrap work runs, and no duplicate snapshot
   is created.  Epoch audit counters record the skip.

Engine failures are retried within the invocation (maximum four attempts per
Game per epoch); a failed attempt marks any retained fallback snapshot stale,
which forces the next wave (and later epochs) to recompute rather than skip.

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
from classifications.models import CalculationAttempt, CalculationEpoch
from classifications.services.calculations import (
    MAX_ATTEMPTS_PER_GAME_EPOCH,
    ClaimStatus,
    claim_game_calculation_attempt,
    execute_pure_calculation,
    fail_engine_attempt,
    finalize_successful_calculation,
    freeze_population,
    should_skip_unchanged_game,
)
from classifications.services.notifications import CalculationFailureNotifier


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
        skipped_unchanged = 0
        failed: list[Game] = []
        pending: list[Game] = list(games)
        for wave in range(1, MAX_ATTEMPTS_PER_GAME_EPOCH + 1):
            wave_failed: list[Game] = []
            for game in pending:
                # Resume gate: already SUCCEEDED earlier in this epoch.
                if CalculationAttempt.objects.filter(
                    epoch=epoch,
                    game=game,
                    status=CalculationAttempt.Status.SUCCEEDED,
                ).exists():
                    succeeded += 1
                    continue

                # Freeze once and reuse the population for both the
                # content-addressed check and the calculation itself.
                population, received, invalid = freeze_population(game, cutoff)

                # Content-addressed gate: identical inputs + versions -> skip.
                is_unchanged, snapshot = should_skip_unchanged_game(
                    game.pk, population.population_hash
                )
                if is_unchanged:
                    skipped_unchanged += 1
                    assert snapshot is not None
                    self.stdout.write(
                        f"Game {game.slug}: unchanged population and algorithm "
                        f"versions. Skipping (reusing snapshot {snapshot.pk})."
                    )
                    continue

                claim_status, attempt = claim_game_calculation_attempt(epoch, game.pk)
                if claim_status is ClaimStatus.SKIPPED_ALREADY_SUCCEEDED:
                    succeeded += 1
                    continue
                if claim_status is ClaimStatus.EXHAUSTED:
                    failed.append(game)
                    continue

                assert attempt is not None
                try:
                    pure = execute_pure_calculation(
                        game=game,
                        cutoff_at=cutoff,
                        frozen_population=(population, received, invalid),
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
        epoch.games_skipped_unchanged = skipped_unchanged
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
                "games_skipped_unchanged",
                "status",
                "completed_at",
            ]
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Epoch {epoch_id} complete: {succeeded} succeeded, "
                f"{skipped_unchanged} skipped (unchanged), {len(failed)} failed."
            )
        )


__all__ = ["Command"]
