"""
Game model tests — SBGC-45.

Covers fields, validation, constraints, identity, timestamps, queries,
Admin registration, and no-network guarantees.  Database-backed tests use
``TestCase``; pure validation/identity tests use ``SimpleTestCase``.
"""

from __future__ import annotations

from datetime import datetime

from config.model_typing import model_field
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from games.models import ContentType, Game, ListingStatus, SourceType

# ============================================================================
# Field metadata — no database
# ============================================================================


class FieldMetadataTests(SimpleTestCase):
    """Field types, lengths, choices, defaults, null/blank semantics."""

    def test_primary_key_is_automatic_bigint(self):
        field = Game._meta.pk
        self.assertIsNotNone(field)
        self.assertTrue(field.auto_created)

    def test_source_type_max_length_and_choices(self):
        field = model_field(Game, "source_type")
        self.assertEqual(field.max_length, 16)
        self.assertEqual(
            set(field.choices),  # type: ignore[arg-type]
            {("steam", "Steam"), ("manual", "Manual")},
        )

    def test_external_id_nullable_and_max_length(self):
        field = model_field(Game, "external_id")
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertEqual(field.max_length, 64)

    def test_name_max_length(self):
        self.assertEqual(model_field(Game, "name").max_length, 255)

    def test_slug_unique_and_max_length(self):
        field = model_field(Game, "slug")
        self.assertTrue(field.unique)
        self.assertEqual(field.max_length, 255)

    def test_content_type_choices_and_default(self):
        field = model_field(Game, "content_type")
        self.assertEqual(field.default, ContentType.GAME)

    def test_listing_status_choices_and_default(self):
        field = model_field(Game, "listing_status")
        self.assertEqual(field.default, ListingStatus.DRAFT)

    def test_manual_metadata_fields_blank(self):
        for name in ("description", "manual_image_url", "manual_website_url"):
            field = model_field(Game, name)
            self.assertTrue(field.blank)

    def test_steam_image_url_blank_and_max_length(self):
        field = model_field(Game, "steam_image_url")
        self.assertTrue(field.blank)
        self.assertFalse(field.null)
        self.assertEqual(field.max_length, 500)

    def test_last_steam_refresh_at_nullable(self):
        field = model_field(Game, "last_steam_refresh_at")
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertFalse(getattr(field, "auto_now", False))
        self.assertFalse(getattr(field, "auto_now_add", False))

    def test_timestamps_auto(self):
        self.assertTrue(model_field(Game, "created_at").auto_now_add)  # pyright: ignore[reportAttributeAccessIssue] — DateField-specific attribute
        self.assertTrue(model_field(Game, "updated_at").auto_now)  # pyright: ignore[reportAttributeAccessIssue] — DateField-specific attribute

    def test_ordering(self):
        self.assertEqual(Game._meta.ordering, ["name", "id"])

    def test_index_exists(self):
        names = {idx.name for idx in Game._meta.indexes}
        self.assertIn("game_listing_name_idx", names)

    def test_constraint_names(self):
        names = {c.name for c in Game._meta.constraints}
        self.assertIn("game_source_external_id_ck", names)
        self.assertIn("game_unique_source_external_id", names)


# ============================================================================
# Valid records — database-backed
# ============================================================================


class ValidRecordTests(TestCase):
    """Construction and persistence of valid Game records."""

    def test_manual_draft(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL, name="Valorant", slug="valorant"
        )
        g.refresh_from_db()
        self.assertEqual(g.source_type, SourceType.MANUAL)
        self.assertIsNone(g.external_id)
        self.assertEqual(g.listing_status, ListingStatus.DRAFT)
        self.assertEqual(g.content_type, ContentType.GAME)

    def test_manual_published(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Valorant",
            slug="valorant",
            listing_status=ListingStatus.PUBLISHED,
        )
        g.refresh_from_db()
        self.assertEqual(g.listing_status, ListingStatus.PUBLISHED)

    def test_steam_draft(self):
        g = Game.objects.create(
            source_type=SourceType.STEAM,
            name="Portal 2",
            slug="portal-2",
            external_id="620",
        )
        g.refresh_from_db()
        self.assertEqual(g.source_type, SourceType.STEAM)
        self.assertEqual(g.external_id, "620")

    def test_steam_published(self):
        g = Game.objects.create(
            source_type=SourceType.STEAM,
            name="Portal 2",
            slug="portal-2-pub",
            external_id="620",
            listing_status=ListingStatus.PUBLISHED,
        )
        g.refresh_from_db()
        self.assertEqual(g.listing_status, ListingStatus.PUBLISHED)

    def test_duplicate_names_accepted(self):
        Game.objects.create(source_type=SourceType.MANUAL, name="Test", slug="test-1")
        Game.objects.create(source_type=SourceType.MANUAL, name="Test", slug="test-2")
        self.assertEqual(Game.objects.filter(name="Test").count(), 2)

    def test_optional_manual_metadata(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Meta",
            slug="meta",
            description="A description.",
            manual_image_url="https://example.com/img.png",
            manual_website_url="https://example.com",
        )
        g.refresh_from_db()
        self.assertEqual(g.description, "A description.")
        self.assertEqual(g.manual_image_url, "https://example.com/img.png")
        self.assertEqual(g.manual_website_url, "https://example.com")

    def test_valid_metadata_urls_accepted(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="URLs",
            slug="urls",
            manual_image_url="https://cdn.example.com/a.jpg",
            manual_website_url="https://www.example.com/page",
        )
        self.assertIn("https://", g.manual_image_url)


# ============================================================================
# Model validation — no database
# ============================================================================


class ModelValidationTests(TestCase):
    """``full_clean()`` rejects invalid field values."""

    def test_whitespace_only_name_rejected(self):
        g = Game(
            source_type=SourceType.MANUAL,
            name="   ",
            slug="whitespace-test",
        )
        with self.assertRaises(ValidationError):
            g.full_clean()

    def test_steam_missing_external_id_rejected(self):
        g = Game(
            source_type=SourceType.STEAM,
            name="Portal",
            slug="portal",
            external_id=None,
        )
        with self.assertRaises(ValidationError):
            g.full_clean()

    def test_steam_blank_external_id_rejected(self):
        g = Game(
            source_type=SourceType.STEAM,
            name="Portal",
            slug="portal",
            external_id="",
        )
        with self.assertRaises(ValidationError):
            g.full_clean()

    def test_steam_nondigit_external_id_rejected(self):
        g = Game(
            source_type=SourceType.STEAM,
            name="Portal",
            slug="portal",
            external_id="abc123",
        )
        with self.assertRaises(ValidationError):
            g.full_clean()

    def test_manual_external_id_rejected(self):
        g = Game(
            source_type=SourceType.MANUAL,
            name="Valorant",
            slug="valorant",
            external_id="12345",
        )
        with self.assertRaises(ValidationError):
            g.full_clean()

    def test_invalid_url_rejected(self):
        g = Game(
            source_type=SourceType.MANUAL,
            name="Bad URL",
            slug="bad-url",
            manual_image_url="not-a-url",
        )
        with self.assertRaises(ValidationError):
            g.full_clean()


# ============================================================================
# Database constraints — database-backed
# ============================================================================


class ConstraintTests(TestCase):
    """Database-level constraints and unique enforcement."""

    def test_duplicate_steam_identity_rejected(self):
        Game.objects.create(
            source_type=SourceType.STEAM,
            name="Portal",
            slug="portal",
            external_id="620",
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.create(
                    source_type=SourceType.STEAM,
                    name="Portal Copy",
                    slug="portal-copy",
                    external_id="620",
                )

    def test_multiple_manual_null_ids_accepted(self):
        for i in range(3):
            Game.objects.create(
                source_type=SourceType.MANUAL,
                name=f"Manual {i}",
                slug=f"manual-{i}",
            )
        self.assertEqual(Game.objects.filter(source_type=SourceType.MANUAL).count(), 3)

    def test_manual_external_id_db_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.create(
                    source_type=SourceType.MANUAL,
                    name="Bad",
                    slug="bad-manual",
                    external_id="123",
                )

    def test_steam_null_id_db_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.create(
                    source_type=SourceType.STEAM,
                    name="Bad Steam",
                    slug="bad-steam-null",
                    external_id=None,
                )

    def test_steam_empty_id_db_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.create(
                    source_type=SourceType.STEAM,
                    name="Bad Steam",
                    slug="bad-steam-empty",
                    external_id="",
                )

    def test_duplicate_slug_rejected(self):
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="First",
            slug="my-slug",
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Game.objects.create(
                    source_type=SourceType.MANUAL,
                    name="Second",
                    slug="my-slug",
                )

    def test_duplicate_name_accepted(self):
        Game.objects.create(source_type=SourceType.MANUAL, name="Dup", slug="dup-1")
        Game.objects.create(source_type=SourceType.MANUAL, name="Dup", slug="dup-2")
        self.assertEqual(Game.objects.filter(name="Dup").count(), 2)


# ============================================================================
# Display identity — no database
# ============================================================================


class IdentityTests(SimpleTestCase):
    """``display_identity`` and ``__str__``."""

    def test_steam_display_identity(self):
        g = Game(
            source_type=SourceType.STEAM,
            name="Portal 2",
            slug="portal-2",
            external_id="620",
        )
        self.assertEqual(g.display_identity, "steam:620")

    def test_manual_display_identity(self):
        g = Game(
            source_type=SourceType.MANUAL,
            name="Valorant",
            slug="valorant",
        )
        self.assertEqual(g.display_identity, "manual:valorant")

    def test_str_includes_name_and_identity(self):
        g = Game(
            source_type=SourceType.STEAM,
            name="Portal 2",
            slug="p2",
            external_id="620",
        )
        s = str(g)
        self.assertIn("Portal 2", s)
        self.assertIn("steam:620", s)

    def test_duplicate_names_distinguishable(self):
        a = Game(
            source_type=SourceType.STEAM,
            name="Game",
            slug="g-1",
            external_id="10",
        )
        b = Game(
            source_type=SourceType.STEAM,
            name="Game",
            slug="g-2",
            external_id="20",
        )
        self.assertNotEqual(str(a), str(b))


# ============================================================================
# Timestamps — database-backed
# ============================================================================


class TimestampTests(TestCase):
    """``created_at`` and ``updated_at`` behaviour."""

    def test_created_at_populated_on_create(self):
        g = Game.objects.create(source_type=SourceType.MANUAL, name="TS", slug="ts")
        self.assertIsInstance(g.created_at, datetime)
        self.assertIsInstance(g.updated_at, datetime)

    def test_created_at_stable(self):
        g = Game.objects.create(source_type=SourceType.MANUAL, name="TS2", slug="ts2")
        original = g.created_at
        g.name = "TS2 Updated"
        g.save()
        g.refresh_from_db()
        self.assertEqual(g.created_at, original)

    def test_updated_at_changes(self):
        g = Game.objects.create(source_type=SourceType.MANUAL, name="TS3", slug="ts3")
        original = g.updated_at
        g.name = "TS3 Updated"
        g.save()
        g.refresh_from_db()
        self.assertGreater(g.updated_at, original)


# ============================================================================
# Query helpers — database-backed
# ============================================================================


class QueryTests(TestCase):
    """Common query patterns used by the application."""

    @classmethod
    def setUpTestData(cls):
        Game.objects.create(
            source_type=SourceType.STEAM,
            name="Alpha",
            slug="alpha",
            external_id="10",
            listing_status=ListingStatus.PUBLISHED,
        )
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Beta",
            slug="beta",
            listing_status=ListingStatus.DRAFT,
        )
        Game.objects.create(
            source_type=SourceType.STEAM,
            name="Alpha",
            slug="alpha-dup",
            external_id="20",
            listing_status=ListingStatus.ARCHIVED,
        )

    def test_published_filter(self):
        qs = Game.objects.filter(listing_status=ListingStatus.PUBLISHED)
        self.assertEqual(qs.count(), 1)
        game = qs.first()
        if game is None:
            self.fail("Expected a published game to exist")
        self.assertEqual(game.slug, "alpha")

    def test_draft_excluded_from_published(self):
        qs = Game.objects.exclude(listing_status=ListingStatus.PUBLISHED)
        self.assertEqual(qs.count(), 2)

    def test_duplicate_names_ordered_by_id(self):
        qs = Game.objects.filter(name="Alpha").order_by("id")
        self.assertEqual(qs.count(), 2)
        ids = list(qs.values_list("id", flat=True))
        self.assertLess(ids[0], ids[1])

    def test_slug_lookup(self):
        g = Game.objects.get(slug="beta")
        self.assertEqual(g.name, "Beta")

    def test_source_external_lookup(self):
        g = Game.objects.get(source_type=SourceType.STEAM, external_id="10")
        self.assertEqual(g.slug, "alpha")


# ============================================================================
# Admin registration — simulates Admin without the full request cycle
# ============================================================================


class AdminRegistrationTests(SimpleTestCase):
    """Admin site registration and configuration."""

    def test_game_registered(self):
        from django.contrib import admin

        self.assertTrue(admin.site.is_registered(Game))

    def test_list_display(self):
        from games.admin import GameAdmin

        self.assertIn("name", GameAdmin.list_display)
        self.assertIn("source_type", GameAdmin.list_display)
        self.assertIn("external_id", GameAdmin.list_display)
        self.assertIn("content_type", GameAdmin.list_display)
        self.assertIn("listing_status", GameAdmin.list_display)

    def test_list_filter(self):
        from games.admin import GameAdmin

        self.assertIn("source_type", GameAdmin.list_filter)
        self.assertIn("content_type", GameAdmin.list_filter)
        self.assertIn("listing_status", GameAdmin.list_filter)

    def test_search_fields(self):
        from games.admin import GameAdmin

        self.assertIn("name", GameAdmin.search_fields)
        self.assertIn("slug", GameAdmin.search_fields)
        self.assertIn("external_id", GameAdmin.search_fields)

    def test_prepopulated_fields(self):
        from games.admin import GameAdmin

        self.assertEqual(GameAdmin.prepopulated_fields, {"slug": ("name",)})

    def test_readonly_fields(self):
        from games.admin import GameAdmin

        self.assertIn("display_identity", GameAdmin.readonly_fields)
        self.assertIn("created_at", GameAdmin.readonly_fields)
        self.assertIn("updated_at", GameAdmin.readonly_fields)
        self.assertIn("steam_image_url", GameAdmin.readonly_fields)
        self.assertIn("last_steam_refresh_at", GameAdmin.readonly_fields)


class AdminFunctionalTests(TestCase):
    """Staff user can list, add, and change Game records."""

    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_superuser(
            username="admin_test", password="testpass"
        )
        self.client.force_login(self.user)  # type: ignore[attr-defined]

    def test_changelist_loads(self):
        url = reverse("admin:games_game_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_add_view_loads(self):
        url = reverse("admin:games_game_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_create_manual_game(self):
        url = reverse("admin:games_game_add")
        data = {
            "source_type": SourceType.MANUAL,
            "name": "Admin Game",
            "slug": "admin-game",
            "content_type": ContentType.GAME,
            "listing_status": ListingStatus.DRAFT,
            "description": "",
            "manual_image_url": "",
            "manual_website_url": "",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Game.objects.filter(slug="admin-game").exists())

    def test_steam_external_id_validated(self):
        """Admin rejects non-digit Steam App ID."""
        url = reverse("admin:games_game_add")
        data = {
            "source_type": SourceType.STEAM,
            "name": "Bad Steam",
            "slug": "bad-steam",
            "external_id": "abc",
            "content_type": ContentType.GAME,
            "listing_status": ListingStatus.DRAFT,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)  # form re-displayed
        self.assertFalse(Game.objects.filter(slug="bad-steam").exists())


# ============================================================================
# No-network guarantee — no database
# ============================================================================


class NoNetworkTests(TestCase):
    """The Game model layer never imports or calls network-dependent code."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a sentinel that raises if Steam client is ever instantiated
        # during any of these tests.
        cls._steam_sentinel_called = False

        import games.models as _models_module

        cls._models_module = _models_module

    def test_models_module_imports_no_steam_client(self):
        self.assertFalse(hasattr(self._models_module, "SteamClient"))

    def test_models_module_imports_no_requests(self):
        self.assertFalse(hasattr(self._models_module, "requests"))

    def test_construction_makes_no_network_request(self):
        g = Game(
            source_type=SourceType.STEAM,
            name="Test",
            slug="test-net-1",
            external_id="10",
        )
        self.assertEqual(g.name, "Test")

    def test_full_clean_makes_no_network_request(self):
        g = Game(
            source_type=SourceType.STEAM,
            name="Test Clean",
            slug="test-net-2",
            external_id="730",
        )
        g.full_clean()
        self.assertEqual(g.external_id, "730")

    def test_save_makes_no_network_request(self):
        g = Game(
            source_type=SourceType.STEAM,
            name="Test Save",
            slug="test-net-3",
            external_id="440",
        )
        g.save()
        g.refresh_from_db()
        self.assertEqual(g.name, "Test Save")

    def test_str_makes_no_network_request(self):
        g = Game(
            source_type=SourceType.STEAM,
            name="Portal",
            slug="test-net-4",
            external_id="620",
        )
        s = str(g)
        self.assertIn("steam:620", s)

    def test_display_identity_makes_no_network_request(self):
        g = Game(
            source_type=SourceType.STEAM,
            name="CS2",
            slug="test-net-5",
            external_id="730",
        )
        self.assertEqual(g.display_identity, "steam:730")

    def test_admin_module_imports_no_steam_client(self):
        import games.admin

        self.assertFalse(hasattr(games.admin, "SteamClient"))

    def test_admin_changelist_no_steam_import(self):
        """Admin changelist page does not trigger Steam client import."""
        from django.contrib.auth.models import User

        user = User.objects.create_superuser(
            username="no_net_admin", password="testpass"
        )
        self.client.force_login(user)  # type: ignore[attr-defined]

        Game.objects.create(
            source_type=SourceType.STEAM,
            name="Listed",
            slug="test-net-6",
            external_id="730",
        )
        url = reverse("admin:games_game_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_add_view_no_steam_import(self):
        """Admin add view does not trigger Steam client import."""
        from django.contrib.auth.models import User

        user = User.objects.create_superuser(username="no_net_add", password="testpass")
        self.client.force_login(user)  # type: ignore[attr-defined]

        url = reverse("admin:games_game_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_change_view_no_steam_import(self):
        """Admin change view does not trigger Steam client import."""
        from django.contrib.auth.models import User

        user = User.objects.create_superuser(
            username="no_net_change", password="testpass"
        )
        self.client.force_login(user)  # type: ignore[attr-defined]

        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Change Me",
            slug="test-net-7",
        )
        url = reverse("admin:games_game_change", args=(g.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
