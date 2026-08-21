"""
``run_scheduled_steam_refresh`` management command — SBGC-183.

Thin entry point for the daily scheduled Steam metadata refresh.  Delegates
all orchestration to ``ScheduledSteamRefreshService``; the scheduler (Render
Cron or equivalent) owns starting this command once per day.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from games.services.imports.factory import build_steam_refresh_service
from games.services.scheduled_refresh import ScheduledSteamRefreshService


class Command(BaseCommand):
    help = "Run one daily scheduled Steam metadata refresh."

    def handle(self, **options):
        service = ScheduledSteamRefreshService(build_steam_refresh_service())
        run = service.run()

        if run is None:
            self.stdout.write(
                self.style.WARNING(
                    "A scheduled Steam refresh run is already active; skipping."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Steam refresh run finished: {run.successful_count} succeeded, "
                f"{run.failed_count} failed (status={run.status})."
            )
        )
