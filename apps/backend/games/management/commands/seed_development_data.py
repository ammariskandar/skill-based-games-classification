"""
``seed_development_data`` management command — SBGC-50.

Creates deterministic sample Games and editorial classifications for
local development.  Idempotent — safe to re-run.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from games.development_data import seed_development_data


class Command(BaseCommand):
    help = "Seed the database with deterministic development data."

    def handle(self, **options):
        if not getattr(settings, "DEVELOPMENT_SEEDING_ENABLED", False):
            raise CommandError(
                "DEVELOPMENT_SEEDING_ENABLED is False.  "
                "Use --settings=config.settings.development."
            )

        with transaction.atomic():
            stats = seed_development_data()

        self.stdout.write("Development data seeded.")
        self.stdout.write(f"  Games created:   {stats['games_created']}")
        self.stdout.write(f"  Games updated:   {stats['games_updated']}")
        self.stdout.write(
            f"  Classifications created: {stats['classifications_created']}"
        )
        self.stdout.write(
            f"  Classifications updated: {stats['classifications_updated']}"
        )
