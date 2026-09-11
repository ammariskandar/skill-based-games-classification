"""
``compute_similarities`` management command — SBGC-227.

Thin entry point for the similar-Games engine.  A platform scheduler invokes it
on the similarity cadence (every three days, after that day's classification
epoch); ``--full`` forces a complete N x (N - 1) rebuild while the default
``--delta`` only recomputes pairs touching a Game changed since its last
similarity generation.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from games.services.similarity import run_similarity_engine


class Command(BaseCommand):
    help = "Compute directed similar-Game scores."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument(
            "--delta",
            action="store_true",
            help=(
                "Recompute only pairs touching Games changed since their last "
                "similarity run (default)."
            ),
        )
        mode.add_argument(
            "--full",
            action="store_true",
            help="Recompute every ordered pair from scratch.",
        )

    def handle(self, **options):
        if options["delta"] and options["full"]:
            raise CommandError("--delta and --full are mutually exclusive.")

        delta = not options["full"]
        report = run_similarity_engine(delta=delta)
        mode = "delta" if report.delta else "full"

        self.stdout.write(
            self.style.SUCCESS(
                f"Similarity ({mode}) complete: {report.games_considered} games "
                f"considered, {report.changed_games} changed, "
                f"{report.pairs_written} pairs written."
            )
        )
