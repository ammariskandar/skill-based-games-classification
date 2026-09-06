"""Nightly batch: flush daily logins and rotate inactive superusers — SBGC-186."""

from __future__ import annotations

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from security.superuser_rotation import (
    evaluate_designated_superusers,
    flush_login_buffer_for_date,
)


class Command(BaseCommand):
    help = (
        "Flushes buffered daily logins and evaluates superuser inactivity "
        "rotation (demote dormant designated superusers, promote top moderators)."
    )

    def handle(self, *args, **options) -> None:
        today = date.today()
        yesterday = today - timedelta(days=1)

        flushed = 0
        for day in (yesterday, today):
            flushed += flush_login_buffer_for_date(day)

        demoted = evaluate_designated_superusers(today)

        self.stdout.write(
            self.style.SUCCESS(
                f"Login buffer flushed ({flushed} distinct day-increments); "
                f"{len(demoted)} superuser(s) demoted."
            )
        )
