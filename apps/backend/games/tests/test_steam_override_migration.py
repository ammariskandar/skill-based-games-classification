"""
Steam override-flag data migration tests — SBGC-188.

Uses ``MigrationExecutor`` to prove the 0011 backfill maps pre-existing
manually-entered metadata into per-field override flags on SQLite.
"""

from __future__ import annotations

from datetime import date

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SteamOverrideBackfillMigrationTests(TransactionTestCase):
    def tearDown(self):
        call_command("migrate", verbosity=0, interactive=False)

    def _model(self, migration: str):
        executor = MigrationExecutor(connection)
        state = executor.loader.project_state([("games", migration)])
        return state.apps.get_model("games", "Game")

    def test_backfill_maps_existing_metadata_to_overrides(self):
        target = "0010_game_description_and_steam_override_flags"
        executor = MigrationExecutor(connection)
        executor.migrate([("games", target)])

        Game0010 = self._model(target)
        Game0010.objects.create(
            source_type="steam",
            external_id="a",
            name="A",
            slug="a",
            content_type="game",
            listing_status="draft",
            description="desc",
            developer="dev",
            release_date=date(2020, 1, 1),
        )
        Game0010.objects.create(
            source_type="steam",
            external_id="b",
            name="B",
            slug="b",
            content_type="game",
            listing_status="draft",
        )
        Game0010.objects.create(
            source_type="steam",
            external_id="c",
            name="C",
            slug="c",
            content_type="game",
            listing_status="draft",
            description="desc",
            developer="",
            release_date=None,
        )
        Game0010.objects.create(
            source_type="manual",
            name="Manual",
            slug="manual",
            content_type="game",
            listing_status="draft",
            description="manual desc",
        )

        executor = MigrationExecutor(connection)
        executor.migrate([("games", "0011_backfill_steam_override_flags")])

        Game0011 = self._model("0011_backfill_steam_override_flags")

        a = Game0011.objects.get(external_id="a")
        self.assertTrue(a.description_overridden)
        self.assertTrue(a.developer_overridden)
        self.assertTrue(a.release_date_overridden)

        b = Game0011.objects.get(external_id="b")
        self.assertFalse(b.description_overridden)
        self.assertFalse(b.developer_overridden)
        self.assertFalse(b.release_date_overridden)

        c = Game0011.objects.get(external_id="c")
        self.assertTrue(c.description_overridden)
        self.assertFalse(c.developer_overridden)
        self.assertFalse(c.release_date_overridden)

        manual = Game0011.objects.get(slug="manual")
        self.assertFalse(manual.description_overridden)
        self.assertFalse(manual.developer_overridden)
        self.assertFalse(manual.release_date_overridden)
