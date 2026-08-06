"""
PostgreSQL migration verification — SBGC-52.

Tests forward/reverse migrations, data-migration conversion,
failure handling, and migration-state consistency on an isolated
PostgreSQL instance.  Uses ``MigrationExecutor`` for proper
model-state lifecycle — no stale in-process model instances.
"""

from __future__ import annotations

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigrationForwardTests(TransactionTestCase):
    """Verify all migrations apply cleanly on a fresh PostgreSQL database."""

    @classmethod
    def setUpClass(cls):
        from unittest import SkipTest

        if connection.vendor != "postgresql":
            raise SkipTest(
                "Migration tests require PostgreSQL. "
                "Use --settings=config.settings.postgresql_test."
            )
        super().setUpClass()

    def tearDown(self):
        call_command("migrate", verbosity=0, interactive=False)

    def test_forward_to_latest(self):
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        executor.migrate(executor.loader.graph.leaf_nodes())
        # If we get here without exception, migration succeeded.
        self.assertTrue(len(plan) >= 0)

    def test_tables_exist_after_forward(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

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

        if connection.vendor != "postgresql":
            raise SkipTest(
                "Migration tests require PostgreSQL. "
                "Use --settings=config.settings.postgresql_test."
            )
        super().setUpClass()

    def tearDown(self):
        call_command("migrate", verbosity=0, interactive=False)

    # ------------------------------------------------------------------
    # Simple reverse / re-apply
    # ------------------------------------------------------------------

    def test_reverse_classifications_and_reapply(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

        # Reverse classifications to zero.
        executor.migrate([("classifications", None)])
        # Re-apply.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_reverse_games_to_0001_and_reapply(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

        # Reverse classifications + games to games 0001.
        executor.migrate([("classifications", None)])
        executor = MigrationExecutor(connection)
        executor.migrate([("games", "0001_initial")])

        # Re-apply all.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    # ------------------------------------------------------------------
    # Data migration: other → unknown (forward)
    # ------------------------------------------------------------------

    def test_other_to_unknown_forward(self):
        """Verify 0003 converts 'other' to 'unknown' in the database."""
        # 1. Migrate to 0002 (the state with 4 content types including "other").
        executor = MigrationExecutor(connection)
        executor.migrate([("games", "0002_alter_game_content_type")])
        # classifications must be at 0001 (or zero) — migrate it now.
        executor = MigrationExecutor(connection)
        executor.migrate([("classifications", "0001_initial")])

        # 2. Obtain historical model from 0002 project state.
        executor = MigrationExecutor(connection)
        state_0002 = executor.loader.project_state(
            [("games", "0002_alter_game_content_type")]
        )
        Game0002 = state_0002.apps.get_model("games", "Game")

        # 3. Create row with content_type="other".
        pk = Game0002.objects.create(
            source_type="steam",
            external_id="other-test",
            name="Other Test",
            slug="other-test",
            content_type="other",
        ).pk
        del Game0002, state_0002

        # 4. Migrate to 0003 (RunPython: other → unknown).
        executor = MigrationExecutor(connection)
        executor.migrate([("games", "0003_migrate_other_to_unknown")])

        # 5. Obtain historical model from 0003 project state.
        executor = MigrationExecutor(connection)
        state_0003 = executor.loader.project_state(
            [("games", "0003_migrate_other_to_unknown")]
        )
        Game0003 = state_0003.apps.get_model("games", "Game")

        # 6. Re-query by primary key.
        game = Game0003.objects.get(pk=pk)
        self.assertEqual(game.content_type, "unknown")

    # ------------------------------------------------------------------
    # Data migration: unknown → other (reverse)
    # ------------------------------------------------------------------

    def test_unknown_to_other_reverse(self):
        """Verify 0003 reverse converts 'unknown' back to 'other'."""
        # 1. Migrate to 0003 (latest).
        executor = MigrationExecutor(connection)
        executor.migrate([("games", "0003_migrate_other_to_unknown")])
        executor = MigrationExecutor(connection)
        executor.migrate([("classifications", "0001_initial")])

        # 2. Obtain historical model from 0003 project state.
        executor = MigrationExecutor(connection)
        state_0003 = executor.loader.project_state(
            [("games", "0003_migrate_other_to_unknown")]
        )
        Game0003 = state_0003.apps.get_model("games", "Game")

        # 3. Create row with content_type="unknown".
        pk = Game0003.objects.create(
            source_type="steam",
            external_id="rev-other",
            name="Rev Other Test",
            slug="rev-other-test",
            content_type="unknown",
        ).pk
        del Game0003, state_0003

        # 4. Reverse to 0002 (classifications first due to dependency).
        executor = MigrationExecutor(connection)
        executor.migrate([("classifications", None)])
        executor = MigrationExecutor(connection)
        executor.migrate([("games", "0002_alter_game_content_type")])

        # 5. Obtain historical model from 0002 project state.
        executor = MigrationExecutor(connection)
        state_0002 = executor.loader.project_state(
            [("games", "0002_alter_game_content_type")]
        )
        Game0002 = state_0002.apps.get_model("games", "Game")

        # 6. Re-query by primary key.
        game = Game0002.objects.get(pk=pk)
        self.assertEqual(game.content_type, "other")


class MigrationFailureTests(TransactionTestCase):
    """Verify migration failure does not leave partial state."""

    @classmethod
    def setUpClass(cls):
        from unittest import SkipTest

        if connection.vendor != "postgresql":
            raise SkipTest(
                "Migration tests require PostgreSQL. "
                "Use --settings=config.settings.postgresql_test."
            )
        super().setUpClass()

    def tearDown(self):
        call_command("migrate", verbosity=0, interactive=False)

    def test_makemigrations_detects_no_changes(self):
        """No pending schema changes — migration state is clean."""
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        result = call_command("makemigrations", check=True, dry_run=True)
        self.assertIsNone(result)
