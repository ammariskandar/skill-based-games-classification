"""
Game Admin integration tests — SBGC-51.

Validates create, edit, duplicate-identity, manual-validation,
DLC-exclusion, changelist, and no-network behaviour through the
real Django test client and actual Admin URLs.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from games.models import ContentType, Game, ListingStatus, SourceType

# ============================================================================
# Helpers
# ============================================================================


def _steam_guard():
    """Patch SteamClient so any instantiation raises RuntimeError."""
    return patch(
        "games.services.steam.client.SteamClient.__init__",
        side_effect=RuntimeError("SteamClient must not be called"),
    )


def _valid_steam_data(
    *,
    name="Test Steam",
    slug="test-steam",
    external_id="999",
    content_type=ContentType.GAME,
    listing_status=ListingStatus.DRAFT,
):
    return {
        "source_type": SourceType.STEAM,
        "external_id": external_id,
        "name": name,
        "slug": slug,
        "content_type": content_type,
        "listing_status": listing_status,
    }


def _valid_manual_data(
    *,
    name="Test Manual",
    slug="test-manual",
    content_type=ContentType.GAME,
    listing_status=ListingStatus.DRAFT,
):
    return {
        "source_type": SourceType.MANUAL,
        "external_id": "",
        "name": name,
        "slug": slug,
        "content_type": content_type,
        "listing_status": listing_status,
    }


# ============================================================================
# Access control
# ============================================================================


class AccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="super_user",
            password="testpass",
        )
        cls.non_staff = User.objects.create_user(
            username="non_staff",
            password="testpass",
        )
        cls.add_url = reverse("admin:games_game_add")
        cls.changelist_url = reverse("admin:games_game_changelist")

    def setUp(self):
        self.client = self.client_class()

    def test_unauthenticated_redirect(self):
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 302)

    def test_non_staff_denied(self):
        self.client.force_login(self.non_staff)
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 302)

    def test_superuser_allowed(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 200)


# ============================================================================
# Valid creation
# ============================================================================


class ValidCreateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="creator", password="testpass"
        )
        self.client.force_login(self.user)
        self.url = reverse("admin:games_game_add")

    # -- Steam ------------------------------------------------------------------

    def test_create_steam_game(self):
        response = self.client.post(self.url, _valid_steam_data())
        self.assertEqual(response.status_code, 302)
        game = Game.objects.get(slug="test-steam")
        self.assertEqual(game.source_type, SourceType.STEAM)
        self.assertEqual(game.external_id, "999")
        self.assertEqual(game.name, "Test Steam")
        self.assertEqual(game.content_type, ContentType.GAME)
        self.assertEqual(game.listing_status, ListingStatus.DRAFT)

    def test_create_steam_game_published(self):
        data = _valid_steam_data(
            slug="steam-pub", listing_status=ListingStatus.PUBLISHED
        )
        self.client.post(self.url, data)
        game = Game.objects.get(slug="steam-pub")
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)

    # -- Manual -----------------------------------------------------------------

    def test_create_manual_game(self):
        response = self.client.post(self.url, _valid_manual_data())
        self.assertEqual(response.status_code, 302)
        game = Game.objects.get(slug="test-manual")
        self.assertEqual(game.source_type, SourceType.MANUAL)
        self.assertIsNone(game.external_id)

    def test_create_manual_with_metadata(self):
        data = _valid_manual_data(slug="meta-manual")
        data["description"] = "A description"
        data["manual_image_url"] = "https://example.invalid/img.png"
        data["manual_website_url"] = "https://example.invalid"
        self.client.post(self.url, data)
        game = Game.objects.get(slug="meta-manual")
        self.assertEqual(game.description, "A description")
        self.assertEqual(game.manual_image_url, "https://example.invalid/img.png")
        self.assertEqual(game.manual_website_url, "https://example.invalid")

    # -- Non-game content types -------------------------------------------------

    def test_create_published_dlc(self):
        data = _valid_steam_data(
            slug="test-dlc",
            external_id="1000",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.client.post(self.url, data)
        game = Game.objects.get(slug="test-dlc")
        self.assertEqual(game.content_type, ContentType.DLC)
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)

    def test_create_draft_game(self):
        data = _valid_manual_data(slug="draft-game", listing_status=ListingStatus.DRAFT)
        self.client.post(self.url, data)
        game = Game.objects.get(slug="draft-game")
        self.assertEqual(game.listing_status, ListingStatus.DRAFT)

    # -- Timestamps -------------------------------------------------------------

    def test_created_at_is_set(self):
        self.client.post(self.url, _valid_manual_data(slug="ts-test"))
        game = Game.objects.get(slug="ts-test")
        self.assertIsNotNone(game.created_at)
        self.assertIsNotNone(game.updated_at)


# ============================================================================
# Edit tests
# ============================================================================


class EditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="editor", password="testpass")
        cls.steam_game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Original Name",
            slug="edit-steam",
        )
        cls.manual_game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Manual Original",
            slug="edit-manual",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def _change_url(self, game):
        return reverse("admin:games_game_change", args=(game.pk,))

    # -- Name and slug ----------------------------------------------------------

    def test_steam_name_readonly_on_edit(self):
        url = self._change_url(self.steam_game)
        data = _valid_steam_data(name="New Name", slug="edit-steam")
        data["_changelist_filters"] = ""
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.steam_game.refresh_from_db()
        self.assertEqual(self.steam_game.name, "Original Name")

    def test_edit_slug(self):
        url = self._change_url(self.steam_game)
        data = _valid_steam_data(slug="new-slug")
        data["_changelist_filters"] = ""
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.steam_game.refresh_from_db()
        self.assertEqual(self.steam_game.slug, "new-slug")

    # -- Content type and listing status independence ---------------------------

    def test_steam_content_type_editable_marks_override(self):
        self.steam_game.listing_status = ListingStatus.PUBLISHED
        self.steam_game.save()
        url = self._change_url(self.steam_game)
        data = _valid_steam_data(
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
            slug="edit-steam",
        )
        data["_changelist_filters"] = ""
        self.client.post(url, data)
        self.steam_game.refresh_from_db()
        # An Admin edit to a Steam game's content type is an owner override
        # (SBGC-96): applied immediately and marked so refresh preserves it.
        self.assertEqual(self.steam_game.content_type, ContentType.DLC)
        self.assertTrue(self.steam_game.content_type_overridden)
        self.assertEqual(self.steam_game.listing_status, ListingStatus.PUBLISHED)

    def test_edit_listing_status_does_not_change_content_type(self):
        url = self._change_url(self.steam_game)
        data = _valid_steam_data(listing_status=ListingStatus.PUBLISHED)
        data["_changelist_filters"] = ""
        self.client.post(url, data)
        self.steam_game.refresh_from_db()
        self.assertEqual(self.steam_game.listing_status, ListingStatus.PUBLISHED)
        self.assertEqual(self.steam_game.content_type, ContentType.GAME)

    # -- Manual metadata --------------------------------------------------------

    def test_edit_manual_metadata(self):
        url = self._change_url(self.manual_game)
        data = _valid_manual_data(
            slug="edit-manual",
            listing_status=ListingStatus.DRAFT,
        )
        data["description"] = "Updated description"
        data["manual_image_url"] = "https://example.invalid/new.png"
        data["manual_website_url"] = "https://example.invalid/new-site"
        data["_changelist_filters"] = ""
        self.client.post(url, data)
        self.manual_game.refresh_from_db()
        self.assertEqual(self.manual_game.description, "Updated description")
        self.assertEqual(
            self.manual_game.manual_image_url, "https://example.invalid/new.png"
        )
        self.assertEqual(
            self.manual_game.manual_website_url, "https://example.invalid/new-site"
        )

    def test_manual_name_and_content_type_editable(self):
        url = self._change_url(self.manual_game)
        data = _valid_manual_data(
            slug="edit-manual",
            name="Manual Renamed",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.DRAFT,
        )
        data["_changelist_filters"] = ""
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.manual_game.refresh_from_db()
        self.assertEqual(self.manual_game.name, "Manual Renamed")
        self.assertEqual(self.manual_game.content_type, ContentType.DLC)

    # -- Source identity preservation -------------------------------------------

    def test_source_type_not_changed_on_edit(self):
        url = self._change_url(self.steam_game)
        data = _valid_steam_data(external_id="730")
        data["_changelist_filters"] = ""
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.steam_game.refresh_from_db()
        self.assertEqual(self.steam_game.source_type, SourceType.STEAM)
        self.assertEqual(self.steam_game.external_id, "730")


# ============================================================================
# Duplicate external-ID tests
# ============================================================================


class DuplicateExternalIdTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="dup_admin", password="testpass"
        )
        cls.game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="12345",
            name="Existing Steam",
            slug="existing-steam",
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.add_url = reverse("admin:games_game_add")

    def test_duplicate_steam_external_id_rejected_on_create(self):
        data = _valid_steam_data(
            slug="dup-steam",
            external_id="12345",  # same external_id as existing
        )
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Game.objects.filter(slug="dup-steam").exists())
        # Existing row unchanged.
        self.game.refresh_from_db()
        self.assertEqual(self.game.slug, "existing-steam")

    def test_steam_external_id_immutable_on_edit(self):
        other = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="99999",
            name="Other Steam",
            slug="other-steam",
        )
        url = reverse("admin:games_game_change", args=(other.pk,))
        data = _valid_steam_data(
            external_id="12345",  # attempted App-ID conversion is ignored
        )
        data["_changelist_filters"] = ""
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        other.refresh_from_db()
        self.assertEqual(other.external_id, "99999")  # immutable on edit

    def test_multiple_manual_null_external_allowed(self):
        Game.objects.create(
            source_type=SourceType.MANUAL, name="Manual One", slug="manual-one"
        )
        data = _valid_manual_data(slug="manual-two")
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Game.objects.filter(slug="manual-two").exists())


# ============================================================================
# Manual-game validation tests
# ============================================================================


class SourceIdentityImmutableTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="identity_admin", password="testpass"
        )
        cls.steam_game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Steam Immutable",
            slug="steam-immutable",
        )
        cls.manual_game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Manual Immutable",
            slug="manual-immutable",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def _change_url(self, game):
        return reverse("admin:games_game_change", args=(game.pk,))

    def test_manual_source_type_cannot_change(self):
        url = self._change_url(self.manual_game)
        data = _valid_manual_data(slug="manual-immutable")
        data["source_type"] = SourceType.STEAM
        data["external_id"] = "123"
        data["_changelist_filters"] = ""

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.manual_game.refresh_from_db()
        self.assertEqual(self.manual_game.source_type, SourceType.MANUAL)

    def test_manual_cannot_acquire_external_id(self):
        url = self._change_url(self.manual_game)
        data = _valid_manual_data(slug="manual-immutable")
        data["source_type"] = SourceType.STEAM
        data["external_id"] = "123"
        data["_changelist_filters"] = ""

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.manual_game.refresh_from_db()
        self.assertIsNone(self.manual_game.external_id)

    def test_steam_source_type_cannot_change(self):
        url = self._change_url(self.steam_game)
        data = _valid_steam_data(external_id="730")
        data["source_type"] = SourceType.MANUAL
        data["external_id"] = ""
        data["_changelist_filters"] = ""

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.steam_game.refresh_from_db()
        self.assertEqual(self.steam_game.source_type, SourceType.STEAM)
        self.assertEqual(self.steam_game.external_id, "730")

    def test_steam_external_id_cannot_change(self):
        url = self._change_url(self.steam_game)
        data = _valid_steam_data(external_id="620")
        data["_changelist_filters"] = ""

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.steam_game.refresh_from_db()
        self.assertEqual(self.steam_game.external_id, "730")

    def test_steam_local_metadata_still_editable(self):
        url = self._change_url(self.steam_game)
        data = _valid_steam_data(
            external_id="730",
            slug="steam-immutable",
            listing_status=ListingStatus.PUBLISHED,
        )
        data["_changelist_filters"] = ""

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.steam_game.refresh_from_db()
        self.assertEqual(self.steam_game.listing_status, ListingStatus.PUBLISHED)
        self.assertEqual(self.steam_game.source_type, SourceType.STEAM)
        self.assertEqual(self.steam_game.external_id, "730")


class ManualValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="val_admin", password="testpass"
        )
        self.client.force_login(self.user)
        self.url = reverse("admin:games_game_add")

    # -- Valid manual -----------------------------------------------------------

    def test_manual_with_empty_external_id_succeeds(self):
        data = _valid_manual_data(slug="manual-empty-ext")
        data["external_id"] = ""
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        game = Game.objects.get(slug="manual-empty-ext")
        self.assertIsNone(game.external_id)

    # -- Invalid: manual with external_id ---------------------------------------

    def test_manual_with_external_id_rejected(self):
        data = _valid_manual_data(slug="manual-with-ext")
        data["external_id"] = "123"
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Game.objects.filter(slug="manual-with-ext").exists())

    # -- Invalid: Steam missing external_id -------------------------------------

    def test_steam_missing_external_id_rejected(self):
        data = _valid_steam_data(slug="steam-no-ext", external_id="")
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Game.objects.filter(slug="steam-no-ext").exists())

    # -- Invalid: Steam nondigit external_id ------------------------------------

    def test_steam_nondigit_external_id_rejected(self):
        data = _valid_steam_data(slug="steam-nondigit", external_id="abc123")
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Game.objects.filter(slug="steam-nondigit").exists())

    # -- Invalid: whitespace-only name ------------------------------------------

    def test_whitespace_only_name_rejected(self):
        data = _valid_manual_data(name="   ", slug="blank-name")
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Game.objects.filter(slug="blank-name").exists())

    # -- Invalid: duplicate slug ------------------------------------------------

    def test_duplicate_slug_rejected(self):
        Game.objects.create(
            source_type=SourceType.MANUAL, name="First", slug="same-slug"
        )
        data = _valid_manual_data(slug="same-slug")
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Game.objects.filter(slug="same-slug").count(), 1)

    def test_invalid_manual_image_url_rejected(self):
        data = _valid_manual_data(slug="bad-manual-image")
        data["manual_image_url"] = "http://example.com/img.jpg"
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Game.objects.filter(slug="bad-manual-image").exists())


# ============================================================================
# DLC / non-game exclusion tests
# ============================================================================


class DLCExclusionTests(TestCase):
    """Public listing excludes non-game content types regardless of listing status."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="dlc_admin", password="testpass"
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("admin:games_game_add")

    def _create_via_admin(self, *, slug, content_type, listing_status):
        """Create a game through Admin POST and return the ORM instance."""
        data = {
            "source_type": SourceType.MANUAL,
            "external_id": "",
            "name": slug.replace("-", " ").title(),
            "slug": slug,
            "content_type": content_type,
            "listing_status": listing_status,
        }
        self.client.post(self.url, data)
        return Game.objects.get(slug=slug)

    def test_published_dlc_excluded_from_public_listing(self):
        game = self._create_via_admin(
            slug="pub-dlc",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.assertIn(game, Game.objects.all())
        self.assertNotIn(game, Game.objects.publicly_listable())

    def test_published_demo_excluded_from_public_listing(self):
        game = self._create_via_admin(
            slug="pub-demo",
            content_type=ContentType.DEMO,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.assertIn(game, Game.objects.all())
        self.assertNotIn(game, Game.objects.publicly_listable())

    def test_published_software_excluded_from_public_listing(self):
        game = self._create_via_admin(
            slug="pub-sw",
            content_type=ContentType.SOFTWARE,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.assertIn(game, Game.objects.all())
        self.assertNotIn(game, Game.objects.publicly_listable())

    def test_published_soundtrack_excluded_from_public_listing(self):
        game = self._create_via_admin(
            slug="pub-snd",
            content_type=ContentType.SOUNDTRACK,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.assertIn(game, Game.objects.all())
        self.assertNotIn(game, Game.objects.publicly_listable())

    def test_published_unknown_excluded_from_public_listing(self):
        game = self._create_via_admin(
            slug="pub-unk",
            content_type=ContentType.UNKNOWN,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.assertIn(game, Game.objects.all())
        self.assertNotIn(game, Game.objects.publicly_listable())

    def test_published_game_included_in_public_listing(self):
        game = self._create_via_admin(
            slug="pub-game",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.assertIn(game, Game.objects.publicly_listable())

    def test_draft_game_excluded_from_public_listing(self):
        game = self._create_via_admin(
            slug="draft-game",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.DRAFT,
        )
        self.assertIn(game, Game.objects.all())
        self.assertNotIn(game, Game.objects.publicly_listable())


# ============================================================================
# Changelist tests
# ============================================================================


class ChangelistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="list_admin", password="testpass"
        )
        cls.steam = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="100",
            name="Steam List",
            slug="steam-list",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        cls.manual = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Manual List",
            slug="manual-list",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
        )
        cls.draft = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Draft List",
            slug="draft-list",
            listing_status=ListingStatus.DRAFT,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("admin:games_game_changelist")

    def test_changelist_loads(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_changelist_shows_steam_record(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Steam List")

    def test_changelist_shows_manual_record(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Manual List")

    def test_changelist_shows_draft_record(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Draft List")

    def test_changelist_shows_all_content_types(self):
        # DLC record should appear
        response = self.client.get(self.url)
        self.assertContains(response, "Manual List")

    def test_default_manager_not_filtered_by_public_listing(self):
        # All records regardless of content type or listing status
        all_count = Game.objects.count()
        self.assertGreaterEqual(all_count, 3)


# ============================================================================
# No-network tests
# ============================================================================


class NoNetworkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="nonet", password="testpass")
        cls.game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="550",
            name="NoNet Game",
            slug="nonet-game",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_game_add_get_no_steam(self):
        with _steam_guard():
            url = reverse("admin:games_game_add")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_game_add_post_no_steam(self):
        with _steam_guard():
            url = reverse("admin:games_game_add")
            data = _valid_steam_data(slug="nonet-create", external_id="1001")
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 302)

    def test_game_edit_get_no_steam(self):
        with _steam_guard():
            url = reverse("admin:games_game_change", args=(self.game.pk,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_game_edit_post_no_steam(self):
        with _steam_guard():
            url = reverse("admin:games_game_change", args=(self.game.pk,))
            data = _valid_steam_data()
            data["_changelist_filters"] = ""
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 302)

    def test_game_changelist_no_steam(self):
        with _steam_guard():
            url = reverse("admin:games_game_changelist")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_dlc_scenario_no_steam(self):
        """Creating a Published DLC through Admin must not call Steam."""
        with _steam_guard():
            url = reverse("admin:games_game_add")
            data = _valid_steam_data(
                slug="nonet-dlc",
                external_id="2000",
                content_type=ContentType.DLC,
                listing_status=ListingStatus.PUBLISHED,
            )
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 302)
