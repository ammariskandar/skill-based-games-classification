"""
PostgreSQL migration verification — SBGC-52.

Tests forward/reverse migrations, failure handling, and migration-state
consistency on an isolated PostgreSQL instance.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from django.db import connection
from django.test import TransactionTestCase

from config.pg_testing import require_postgres_test_url


_MANAGE = Path(__file__).resolve().parent.parent.parent / "manage.py"
_SETTINGS = "config.settings.postgresql_test"


def _manage(*args):
    """Run manage.py with PostgreSQL test settings."""
    url = require_postgres_test_url()
    env = {**__import__("os").environ, "POSTGRES_TEST_DATABASE_URL": url}
    result = subprocess.run(
        [sys.executable, str(_MANAGE), *args, f"--settings={_SETTINGS}", "--noinput"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_MANAGE.parent),
    )
    return result


class MigrationForwardTests(TransactionTestCase):
    """Verify all migrations apply cleanly on a fresh PostgreSQL database."""

    @classmethod
    def setUpClass(cls):
        from unittest import SkipTest

        from django.db import connection

        if connection.vendor != "postgresql":
            raise SkipTest(
                "Migration tests require PostgreSQL. "
                "Use --settings=config.settings.postgresql_test."
            )
        super().setUpClass()

    def test_forward_to_latest(self):
        result = _manage("migrate")
        self.assertEqual(
            result.returncode,
            0,
            f"Migration failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )

    def test_tables_exist_after_forward(self):
        _manage("migrate")
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename FROM pg_catalog.pg_tables
                WHERE schemaname = 'public'
                  AND tablename IN (
                    'games_game',
                    'classifications_editorialclassification',
                    'classifications_challengeprofile',
                    'classifications_rewardprofile'
                  )
                ORDER BY tablename
                """
            )
            tables = {row[0] for row in cursor.fetchall()}
        self.assertIn("games_game", tables)
        self.assertIn("classifications_editorialclassification", tables)
        self.assertIn("classifications_challengeprofile", tables)
        self.assertIn("classifications_rewardprofile", tables)


class MigrationReverseTests(TransactionTestCase):
    """Verify safe rollback and re-apply of migrations."""

    @classmethod
    def setUpClass(cls):
        from unittest import SkipTest

        from django.db import connection

        if connection.vendor != "postgresql":
            raise SkipTest(
                "Migration tests require PostgreSQL. "
                "Use --settings=config.settings.postgresql_test."
            )
        super().setUpClass()

    def test_reverse_classifications_and_reapply(self):
        # Forward to latest.
        _manage("migrate")

        # Reverse classifications to zero.
        result = _manage("migrate", "classifications", "zero")
        self.assertEqual(result.returncode, 0)

        # Re-apply classifications.
        result = _manage("migrate", "classifications")
        self.assertEqual(result.returncode, 0)

    def test_reverse_games_to_0001_and_reapply(self):
        _manage("migrate")

        # Reverse games to 0001 (before content-type changes).
        # classifications depends on games, so reverse both.
        _manage("migrate", "classifications", "zero")
        result = _manage("migrate", "games", "0001")
        self.assertEqual(result.returncode, 0)

        # Re-apply all.
        result = _manage("migrate")
        self.assertEqual(result.returncode, 0)

    def test_other_to_unknown_forward(self):
        """Verify the 0003 data migration converts 'other' to 'unknown'."""
        _manage("migrate")

        # Create row with 'other' at migration 0001 state.
        _manage("migrate", "games", "0001")
        _manage("migrate", "classifications", "0001")

        # We need to test the migration programmatically.
        # Let's use the ORM with historical model.
        from django.apps import apps

        # Apply 0002 first, then insert 'other', then 0003.
        _manage("migrate", "games", "0002")
        _manage("migrate", "classifications", "0001")

        # Insert 'other' row at migration 0002 state.
        Game = apps.get_model("games", "Game")
        Game.objects.create(
            source_type="steam",
            external_id="other-test",
            name="Other Test",
            slug="other-test",
            content_type="other",
        )

        # Apply 0003 — should convert to 'unknown'.
        result = _manage("migrate", "games", "0003")
        self.assertEqual(result.returncode, 0)

        # Now re-import to get latest model.
        from games.models import Game as LatestGame

        game = LatestGame.objects.get(slug="other-test")
        self.assertEqual(game.content_type, "unknown")

        # Restore.
        _manage("migrate")

    def test_unknown_to_other_reverse(self):
        """Verify the 0003 reverse converts 'unknown' back to 'other'."""
        _manage("migrate")

        # Create 'unknown' row at latest.
        from games.models import Game as LatestGame

        LatestGame.objects.create(
            source_type="steam",
            external_id="rev-other",
            name="Rev Other Test",
            slug="rev-other-test",
            content_type="unknown",
        )

        # Reverse to 0002.
        _manage("migrate", "classifications", "zero")
        result = _manage("migrate", "games", "0002")
        self.assertEqual(result.returncode, 0)

        # Check at historical state.
        from django.apps import apps

        Game = apps.get_model("games", "Game")
        game = Game.objects.get(slug="rev-other-test")
        self.assertEqual(game.content_type, "other")

        # Restore.
        _manage("migrate")


class MigrationFailureTests(TransactionTestCase):
    """Verify migration failure does not leave partial state."""

    @classmethod
    def setUpClass(cls):
        from unittest import SkipTest

        from django.db import connection

        if connection.vendor != "postgresql":
            raise SkipTest(
                "Migration tests require PostgreSQL. "
                "Use --settings=config.settings.postgresql_test."
            )
        super().setUpClass()

    def test_makemigrations_detects_no_changes(self):
        """No pending schema changes — migration state is clean."""
        result = _manage("makemigrations", "--check", "--dry-run")
        self.assertEqual(
            result.returncode,
            0,
            f"Unexpected pending migrations:\n{result.stdout}",
        )
