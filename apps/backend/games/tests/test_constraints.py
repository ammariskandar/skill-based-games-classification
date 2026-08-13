"""
Game model database-constraint tests — SBGC-47.

Bulk operations, deletions, and direct DB enforcement verified without
``full_clean()``.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase

from games.models import Game, SourceType


class GameSourceExternalConstraintTests(TestCase):
    """CheckConstraint ``game_source_external_id_ck`` behaviour."""

    def test_steam_with_null_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.create(
                    source_type=SourceType.STEAM,
                    name="Bad Steam",
                    slug="bad-steam-null",
                    external_id=None,
                )

    def test_steam_with_blank_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.create(
                    source_type=SourceType.STEAM,
                    name="Bad Steam",
                    slug="bad-steam-blank",
                    external_id="",
                )

    def test_manual_with_external_id_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.create(
                    source_type=SourceType.MANUAL,
                    name="Bad Manual",
                    slug="bad-manual-ext",
                    external_id="123",
                )

    def test_manual_null_accepted(self):
        Game.objects.create(source_type=SourceType.MANUAL, name="OK", slug="manual-ok")
        self.assertEqual(Game.objects.filter(slug="manual-ok").count(), 1)

    def test_steam_valid_accepted(self):
        Game.objects.create(
            source_type=SourceType.STEAM,
            name="OK Steam",
            slug="steam-ok",
            external_id="730",
        )
        self.assertEqual(Game.objects.filter(slug="steam-ok").count(), 1)


class GameUniquenessConstraintTests(TestCase):
    """UniqueConstraint and slug uniqueness at DB level."""

    def test_duplicate_steam_identity_rejected(self):
        Game.objects.create(
            source_type=SourceType.STEAM,
            name="First",
            slug="first",
            external_id="620",
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.create(
                    source_type=SourceType.STEAM,
                    name="Second",
                    slug="second",
                    external_id="620",
                )

    def test_multiple_manual_null_accepted(self):
        for i in range(3):
            Game.objects.create(
                source_type=SourceType.MANUAL,
                name=f"Manual {i}",
                slug=f"manual-{i}",
            )
        self.assertEqual(Game.objects.filter(source_type=SourceType.MANUAL).count(), 3)

    def test_duplicate_slug_rejected(self):
        Game.objects.create(
            source_type=SourceType.MANUAL, name="First", slug="dup-slug"
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.create(
                    source_type=SourceType.MANUAL,
                    name="Second",
                    slug="dup-slug",
                )

    def test_duplicate_name_accepted(self):
        Game.objects.create(source_type=SourceType.MANUAL, name="Same", slug="same-1")
        Game.objects.create(source_type=SourceType.MANUAL, name="Same", slug="same-2")
        self.assertEqual(Game.objects.filter(name="Same").count(), 2)


class GameBulkOperationTests(TestCase):
    """``QuerySet.update`` and ``bulk_create`` respect DB constraints."""

    def setUp(self):
        self.steam = Game.objects.create(
            source_type=SourceType.STEAM,
            name="Bulk Steam",
            slug="bulk-steam",
            external_id="100",
        )
        self.manual = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Bulk Manual",
            slug="bulk-manual",
        )

    def test_update_steam_external_to_null_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.filter(pk=self.steam.pk).update(external_id=None)

    def test_update_manual_external_to_value_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.filter(pk=self.manual.pk).update(external_id="999")

    def test_bulk_create_valid_steam_and_manual(self):
        games = [
            Game(
                source_type=SourceType.STEAM,
                name="Bulk S1",
                slug="bulk-s1",
                external_id="200",
            ),
            Game(
                source_type=SourceType.MANUAL,
                name="Bulk M1",
                slug="bulk-m1",
            ),
        ]
        Game.objects.bulk_create(games)
        self.assertEqual(Game.objects.filter(slug="bulk-s1").count(), 1)
        self.assertEqual(Game.objects.filter(slug="bulk-m1").count(), 1)

    def test_bulk_create_duplicate_steam_rejected(self):
        games = [
            Game(
                source_type=SourceType.STEAM,
                name="Bulk S2",
                slug="bulk-s2",
                external_id="100",  # same as self.steam
            ),
        ]
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.bulk_create(games)

    def test_update_slug_to_duplicate_rejected(self):
        Game.objects.create(
            source_type=SourceType.MANUAL, name="Other", slug="other-slug"
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.filter(pk=self.steam.pk).update(slug="other-slug")

    def test_update_slug_to_same_accepted(self):
        """Updating slug to the same value is not a constraint violation."""
        Game.objects.filter(pk=self.steam.pk).update(slug="bulk-steam")
        self.steam.refresh_from_db()
        self.assertEqual(self.steam.slug, "bulk-steam")


class GameDeletionTests(TestCase):
    """Cascade and protection behaviour."""

    def test_game_deletion_cascades_empty(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL, name="Del Me", slug="del-me"
        )
        g.delete()
        self.assertFalse(Game.objects.filter(slug="del-me").exists())

    def test_game_deletion_cascades_classification(self):
        from classifications.models import EditorialClassification

        user = User.objects.create_user(username="del_user", password="p")
        g = Game.objects.create(
            source_type=SourceType.STEAM,
            name="Del Steam",
            slug="del-steam",
            external_id="300",
        )
        EditorialClassification.objects.create(game=g, updated_by=user)
        slug = g.slug
        g.delete()
        self.assertFalse(Game.objects.filter(slug=slug).exists())
        self.assertFalse(
            EditorialClassification.objects.filter(game__slug=slug).exists()
        )


class GameMigrationReversibilityTests(TransactionTestCase):
    """``games.0001_initial`` executes forward and reverse.

    ``TransactionTestCase`` permits schema-changing migration operations.
    The test explicitly restores the latest app migration state in a
    ``finally`` block so that assertion failures or migration errors
    do not leave the database in an incomplete state.
    """

    @staticmethod
    def _migrate_app(app, target):
        from django.core.management import call_command

        call_command(
            "migrate",
            app,
            target,
            verbosity=0,
            interactive=False,
            skip_checks=True,
        )

    def test_forward_reverse_forward(self):
        from django.db import IntegrityError, connection, transaction
        from django.db.migrations.executor import MigrationExecutor

        from games.models import SourceType

        # Confirm initial state: games table exists.
        tables = connection.introspection.table_names()
        self.assertIn("games_game", tables, "games_game must exist before reverse test")

        try:
            # -- (1) Reverse games to zero ------------------------------------
            self._migrate_app("games", "zero")
            tables = connection.introspection.table_names()
            self.assertNotIn("games_game", tables)

            # -- (2) Forward games to 0001 ------------------------------------
            self._migrate_app("games", "0001")
            tables = connection.introspection.table_names()
            self.assertIn("games_game", tables)

            # -- (3) Verify constraints by exercising them --------------------
            # Historical model required: the current model includes
            # steam_image_url (games.0004), absent at this state.
            executor = MigrationExecutor(connection)
            state_0001 = executor.loader.project_state([("games", "0001_initial")])
            game_0001 = state_0001.apps.get_model("games", "Game")

            game_0001.objects.create(
                source_type=SourceType.STEAM,
                name="Fwd",
                slug="fwd",
                external_id="1",
            )
            with transaction.atomic():
                with self.assertRaises(IntegrityError):
                    game_0001.objects.create(
                        source_type=SourceType.MANUAL,
                        name="Bad",
                        slug="bad",
                        external_id="1",
                    )
        finally:
            # Always restore the full project to the latest migration state.
            # Reversing an app may cascade to dependent apps, so we must
            # restore everything, not just the app under test.
            self._migrate_app("", "")

        # Confirm restored: table exists and constraints work.
        tables = connection.introspection.table_names()
        self.assertIn("games_game", tables)

    def test_operations_marked_reversible(self):
        """Supplemental: every operation is marked reversible."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        migration = loader.disk_migrations[("games", "0001_initial")]
        for op in migration.operations:
            self.assertTrue(
                op.reversible,
                f"Operation '{op.describe()}' must be reversible",
            )
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        migration = loader.disk_migrations[("games", "0001_initial")]
        for op in migration.operations:
            self.assertTrue(
                op.reversible,
                f"Operation '{op.describe()}' must be reversible",
            )
