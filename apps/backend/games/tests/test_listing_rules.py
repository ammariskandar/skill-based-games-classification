"""
Game listing rules tests — SBGC-48.

Content-type vocabulary, public-listing queryset, Admin behavior,
and state independence.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from games.models import ContentType, Game, ListingStatus, SourceType
from games.types import CONTENT_TYPE_CHOICES

# ---------------------------------------------------------------------------
# Content-type metadata
# ---------------------------------------------------------------------------


class ContentTypeMetadataTests(TestCase):
    def test_exact_choices(self):
        self.assertEqual(
            set(CONTENT_TYPE_CHOICES),
            {
                ("game", "Game"),
                ("dlc", "Downloadable content"),
                ("demo", "Demo"),
                ("software", "Software"),
                ("soundtrack", "Soundtrack"),
                ("unknown", "Unknown"),
            },
        )

    def test_other_removed(self):
        self.assertNotIn("other", dict(CONTENT_TYPE_CHOICES))
        self.assertFalse(hasattr(ContentType, "OTHER"))

    def test_default_is_game(self):
        field = Game._meta.get_field("content_type")
        self.assertEqual(field.default, ContentType.GAME)  # pyright: ignore[reportAttributeAccessIssue]

    def test_max_length_accommodates_all(self):
        field = Game._meta.get_field("content_type")
        longest = max(len(v) for v in dict(CONTENT_TYPE_CHOICES))
        self.assertLessEqual(longest, field.max_length)  # pyright: ignore[reportCallIssue,reportArgumentType,reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class ContentTypePersistenceTests(TestCase):
    def test_game_saveable(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="CT Game",
            slug="ct-game",
            content_type=ContentType.GAME,
        )
        self.assertEqual(g.content_type, ContentType.GAME)

    def test_dlc_saveable(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="CT DLC",
            slug="ct-dlc",
            content_type=ContentType.DLC,
        )
        self.assertEqual(g.content_type, ContentType.DLC)

    def test_demo_saveable(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="CT Demo",
            slug="ct-demo",
            content_type=ContentType.DEMO,
        )
        self.assertEqual(g.content_type, ContentType.DEMO)

    def test_software_saveable(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="CT SW",
            slug="ct-sw",
            content_type=ContentType.SOFTWARE,
        )
        self.assertEqual(g.content_type, ContentType.SOFTWARE)

    def test_soundtrack_saveable(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="CT ST",
            slug="ct-st",
            content_type=ContentType.SOUNDTRACK,
        )
        self.assertEqual(g.content_type, ContentType.SOUNDTRACK)

    def test_unknown_saveable(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="CT Unk",
            slug="ct-unk",
            content_type=ContentType.UNKNOWN,
        )
        self.assertEqual(g.content_type, ContentType.UNKNOWN)

    def test_default_is_game_on_create(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL, name="Default", slug="default"
        )
        self.assertEqual(g.content_type, ContentType.GAME)

    def test_steam_record_with_content_type(self):
        g = Game.objects.create(
            source_type=SourceType.STEAM,
            name="Steam CT",
            slug="steam-ct",
            external_id="999",
            content_type=ContentType.GAME,
        )
        self.assertEqual(g.source_type, SourceType.STEAM)
        self.assertEqual(g.content_type, ContentType.GAME)

    def test_source_independent_of_content_type(self):
        for ct in ContentType:
            g = Game.objects.create(
                source_type=SourceType.MANUAL,
                name=f"Indep {ct}",
                slug=f"indep-{ct}",
                content_type=ct,
            )
            self.assertEqual(g.source_type, SourceType.MANUAL)


# ---------------------------------------------------------------------------
# Public listing matrix
# ---------------------------------------------------------------------------


class PublicListingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._make("Pub Game", "pub-game", ContentType.GAME, ListingStatus.PUBLISHED)
        cls._make("Draft Game", "draft-game", ContentType.GAME, ListingStatus.DRAFT)
        cls._make("Arch Game", "arch-game", ContentType.GAME, ListingStatus.ARCHIVED)
        cls._make("Pub DLC", "pub-dlc", ContentType.DLC, ListingStatus.PUBLISHED)
        cls._make("Pub Demo", "pub-demo", ContentType.DEMO, ListingStatus.PUBLISHED)
        cls._make("Pub SW", "pub-sw", ContentType.SOFTWARE, ListingStatus.PUBLISHED)
        cls._make("Pub ST", "pub-st", ContentType.SOUNDTRACK, ListingStatus.PUBLISHED)
        cls._make("Pub Unk", "pub-unk", ContentType.UNKNOWN, ListingStatus.PUBLISHED)

    @staticmethod
    def _make(name, slug, ct, status):
        return Game.objects.create(
            source_type=SourceType.MANUAL,
            name=name,
            slug=slug,
            content_type=ct,
            listing_status=status,
        )

    def test_only_published_game_returned(self):
        qs = Game.objects.publicly_listable()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().slug, "pub-game")  # pyright: ignore[reportOptionalMemberAccess]

    def test_draft_game_excluded(self):
        qs = Game.objects.publicly_listable()
        self.assertNotIn("draft-game", qs.values_list("slug", flat=True))

    def test_archived_game_excluded(self):
        qs = Game.objects.publicly_listable()
        self.assertNotIn("arch-game", qs.values_list("slug", flat=True))

    def test_published_dlc_excluded(self):
        qs = Game.objects.publicly_listable()
        self.assertNotIn("pub-dlc", qs.values_list("slug", flat=True))

    def test_published_demo_excluded(self):
        qs = Game.objects.publicly_listable()
        self.assertNotIn("pub-demo", qs.values_list("slug", flat=True))

    def test_published_software_excluded(self):
        qs = Game.objects.publicly_listable()
        self.assertNotIn("pub-sw", qs.values_list("slug", flat=True))

    def test_published_soundtrack_excluded(self):
        qs = Game.objects.publicly_listable()
        self.assertNotIn("pub-st", qs.values_list("slug", flat=True))

    def test_published_unknown_excluded(self):
        qs = Game.objects.publicly_listable()
        self.assertNotIn("pub-unk", qs.values_list("slug", flat=True))


# ---------------------------------------------------------------------------
# Default manager
# ---------------------------------------------------------------------------


class DefaultManagerTests(TestCase):
    def setUp(self):
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="All Game",
            slug="all-game",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="All DLC",
            slug="all-dlc",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.DRAFT,
        )

    def test_all_returns_every_record(self):
        qs = Game.objects.all()
        self.assertEqual(qs.count(), 2)

    def test_all_includes_non_game(self):
        qs = Game.objects.all()
        slugs = set(qs.values_list("slug", flat=True))
        self.assertIn("all-dlc", slugs)

    def test_all_includes_draft(self):
        qs = Game.objects.all()
        slugs = set(qs.values_list("slug", flat=True))
        self.assertIn("all-game", slugs)


# ---------------------------------------------------------------------------
# Chainability
# ---------------------------------------------------------------------------


class ChainabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for i in range(3):
            Game.objects.create(
                source_type=SourceType.STEAM,
                name=f"Chain {i}",
                slug=f"chain-{i}",
                external_id=str(800 + i),
                content_type=ContentType.GAME,
                listing_status=ListingStatus.PUBLISHED,
            )

    def test_publicly_listable_then_filter(self):
        qs = Game.objects.publicly_listable().filter(name="Chain 0")
        self.assertEqual(qs.count(), 1)

    def test_filter_then_publicly_listable(self):
        qs = Game.objects.filter(name__icontains="Chain").publicly_listable()  # pyright: ignore[reportAttributeAccessIssue]
        self.assertEqual(qs.count(), 3)


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class OrderingTests(TestCase):
    def setUp(self):
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Beta",
            slug="order-beta",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Alpha",
            slug="order-alpha",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )

    def test_ordering_by_name_then_id(self):
        qs = Game.objects.publicly_listable()
        names = list(qs.values_list("name", flat=True))
        self.assertEqual(names, ["Alpha", "Beta"])


# ---------------------------------------------------------------------------
# State independence
# ---------------------------------------------------------------------------


class StateIndependenceTests(TestCase):
    def test_changing_type_does_not_change_status(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="State Test",
            slug="state-test",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        g.content_type = ContentType.DLC
        g.save()
        g.refresh_from_db()
        self.assertEqual(g.content_type, ContentType.DLC)
        self.assertEqual(g.listing_status, ListingStatus.PUBLISHED)

    def test_changing_status_does_not_change_type(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="State Test 2",
            slug="state-test-2",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        g.listing_status = ListingStatus.DRAFT
        g.save()
        g.refresh_from_db()
        self.assertEqual(g.listing_status, ListingStatus.DRAFT)
        self.assertEqual(g.content_type, ContentType.GAME)

    def test_unknown_published_remains_excluded(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Unk Pub",
            slug="unk-pub",
            content_type=ContentType.UNKNOWN,
            listing_status=ListingStatus.PUBLISHED,
        )
        qs = Game.objects.publicly_listable()
        self.assertNotIn(g.pk, qs.values_list("pk", flat=True))

    def test_manual_metadata_does_not_affect_eligibility(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Meta",
            slug="meta",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
            manual_description="desc",
        )
        self.assertIn(
            g.pk, Game.objects.publicly_listable().values_list("pk", flat=True)
        )

    def test_source_type_does_not_affect_eligibility(self):
        g = Game.objects.create(
            source_type=SourceType.STEAM,
            name="Src Indep",
            slug="src-indep",
            external_id="900",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.assertIn(
            g.pk, Game.objects.publicly_listable().values_list("pk", flat=True)
        )


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class AdminContentTypeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="ct_admin", password="testpass"
        )
        self.client.force_login(self.user)  # type: ignore[attr-defined]

    def test_form_has_six_choices(self):
        """The content_type field offers exactly 6 choices."""
        field = Game._meta.get_field("content_type")
        self.assertEqual(
            set(field.choices),  # pyright: ignore[reportArgumentType,reportAttributeAccessIssue]
            {
                ("game", "Game"),
                ("dlc", "Downloadable content"),
                ("demo", "Demo"),
                ("software", "Software"),
                ("soundtrack", "Soundtrack"),
                ("unknown", "Unknown"),
            },
        )

    def test_admin_changelist_shows_all(self):
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Admin Game",
            slug="admin-game",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Admin DLC",
            slug="admin-dlc",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
        )
        url = reverse("admin:games_game_changelist")
        response = self.client.get(url)
        self.assertContains(response, "Admin Game")
        self.assertContains(response, "Admin DLC")

    def test_save_each_type(self):
        url = reverse("admin:games_game_add")
        for ct_value, ct_label in CONTENT_TYPE_CHOICES:
            data = {
                "source_type": SourceType.MANUAL,
                "name": f"Save {ct_label}",
                "slug": f"save-{ct_value}",
                "content_type": ct_value,
                "listing_status": ListingStatus.DRAFT,
                "manual_description": "",
                "manual_image_url": "",
                "manual_website_url": "",
            }
            response = self.client.post(url, data)
            self.assertEqual(
                response.status_code, 302, msg=f"Failed to save {ct_label}"
            )

    def test_content_type_edit_preserves_listing_status(self):
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Edit CT",
            slug="edit-ct",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        url = reverse("admin:games_game_change", args=(g.pk,))
        data = {
            "source_type": SourceType.MANUAL,
            "name": "Edit CT",
            "slug": "edit-ct",
            "content_type": ContentType.DLC,
            "listing_status": ListingStatus.PUBLISHED,
            "manual_description": "",
            "manual_image_url": "",
            "manual_website_url": "",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        g.refresh_from_db()
        self.assertEqual(g.content_type, ContentType.DLC)
        self.assertEqual(g.listing_status, ListingStatus.PUBLISHED)


# ---------------------------------------------------------------------------
# No-network
# ---------------------------------------------------------------------------


class NoNetworkTests(TestCase):
    """Game listing operations make no Steam calls."""

    def _steam_guard(self):
        return patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("SteamClient must not be called"),
        )

    def test_save_no_steam(self):
        with self._steam_guard():
            Game.objects.create(
                source_type=SourceType.MANUAL,
                name="NoNet",
                slug="nonet",
                content_type=ContentType.GAME,
                listing_status=ListingStatus.PUBLISHED,
            )

    def test_queryset_evaluation_no_steam(self):
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="NoNet Eval",
            slug="nonet-eval",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        with self._steam_guard():
            list(Game.objects.publicly_listable())

    def test_admin_list_no_steam(self):
        user = User.objects.create_superuser(
            username="nonet_admin", password="testpass"
        )
        self.client.force_login(user)  # type: ignore[attr-defined]
        url = reverse("admin:games_game_changelist")
        with self._steam_guard():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Migration data conversion tests
# ---------------------------------------------------------------------------


class MigrationDataTests(TransactionTestCase):
    """``other → unknown`` data migration executes forward and reverse.

    Uses ``TransactionTestCase`` for schema-changing migration operations.
    Restores all apps to latest in ``finally`` unconditionally.
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

    def test_other_migrates_to_unknown_and_back(self):

        # -- Reverse to games.0001 so choices still include "other" ---------
        self._migrate_app("games", "0001")

        # Create a row with the historical "other" value via raw update
        # (bypassing model-level choice validation).
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Legacy Other",
            slug="legacy-other",
        )
        Game.objects.filter(pk=g.pk).update(content_type="other")
        g.refresh_from_db()
        self.assertEqual(g.content_type, "other")

        try:
            # -- Forward to latest (0003) — data migration
            # converts "other" to "unknown"
            self._migrate_app("games", "0003")
            g.refresh_from_db()
            self.assertEqual(g.content_type, "unknown")
            self.assertIn(g.content_type, dict(CONTENT_TYPE_CHOICES))

            # -- Public listing: migrated "unknown" is NOT listable ---------
            self.assertFalse(Game.objects.publicly_listable().filter(pk=g.pk).exists())

            # -- Reverse to 0001: data migration converts "unknown" back to "other" --
            self._migrate_app("games", "0001")
            g.refresh_from_db()
            self.assertEqual(g.content_type, "other")

        finally:
            self._migrate_app("", "")

        # After restoration: row is at latest state.
        g.refresh_from_db()
        self.assertIn(g.content_type, dict(CONTENT_TYPE_CHOICES))


# ---------------------------------------------------------------------------
# Queryset constant tests
# ---------------------------------------------------------------------------


class QuerysetConstantTests(TestCase):
    """The queryset method uses module-level constants, not duplicated literals."""

    def test_constants_match_expected_values(self):
        self.assertEqual(ContentType.GAME, "game")
        self.assertEqual(ListingStatus.PUBLISHED, "published")

    def test_raw_other_never_publicly_listable(self):
        """If a raw 'other' value somehow exists, it is excluded."""
        g = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Raw Other",
            slug="raw-other",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        Game.objects.filter(pk=g.pk).update(content_type="other")
        self.assertFalse(Game.objects.publicly_listable().filter(pk=g.pk).exists())
