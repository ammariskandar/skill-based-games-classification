"""
Owner content-type override tests — SBGC-96.

Admin-driven content_type overrides for both sources, the public-listing
boundary toggle, Draft/Archive respect, and Steam-refresh preservation of a
manual override.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from games.models import ContentType, Game, ListingStatus, SourceType
from games.services.imports.steam import (
    SteamGamePersistenceService,
    SteamGameRefreshService,
    SteamGameRefreshStatus,
)
from games.services.steam.dto import (
    LookupStatus,
    SteamAppLookupResult,
    SteamGameImportCandidate,
)
from games.services.steam.import_foundation import SteamImportFoundation


def _steam_change_data(**overrides) -> dict:
    data = {
        "source_type": SourceType.STEAM,
        "external_id": "730",
        "name": "Test Steam",
        "slug": "test-steam",
        "content_type": ContentType.DLC,
        "listing_status": ListingStatus.PUBLISHED,
        "release_date": "",
        "developer": "",
        "description": "",
        "manual_image_url": "",
        "manual_website_url": "",
        "_changelist_filters": "",
    }
    data.update(overrides)
    return data


def _refresh_lookup(content_type: str) -> SteamAppLookupResult:
    candidate = SteamGameImportCandidate(
        app_id="730",
        name="Test Steam",
        content_type=content_type,
    )
    return SteamAppLookupResult(
        status=LookupStatus.FOUND,
        app_id="730",
        candidate=candidate,
    )


# ---------------------------------------------------------------------------
# Admin override flow
# ---------------------------------------------------------------------------


class AdminOverrideFlowTests(TestCase):
    """A staff edit to content_type applies immediately and marks the override."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="editor", password="p")
        cls.game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Test Steam",
            slug="test-steam",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("admin:games_game_change", args=(self.game.pk,))

    def test_dlc_to_game_override_becomes_publicly_listable(self):
        self.assertNotIn(self.game, Game.objects.publicly_listable())

        response = self.client.post(
            self.url,
            _steam_change_data(content_type=ContentType.GAME),
        )
        self.assertEqual(response.status_code, 302)

        self.game.refresh_from_db()
        self.assertEqual(self.game.content_type, ContentType.GAME)
        self.assertTrue(self.game.content_type_overridden)
        self.assertIn(self.game, Game.objects.publicly_listable())

    def test_game_to_dlc_override_revokes_public_listing(self):
        game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.assertIn(game, Game.objects.publicly_listable())

        url = reverse("admin:games_game_change", args=(game.pk,))
        self.client.post(
            url,
            _steam_change_data(
                external_id="620",
                name="Portal 2",
                slug="portal-2",
                content_type=ContentType.DLC,
            ),
        )

        game.refresh_from_db()
        self.assertEqual(game.content_type, ContentType.DLC)
        self.assertTrue(game.content_type_overridden)
        self.assertNotIn(game, Game.objects.publicly_listable())


class DraftArchiveOverrideTests(TestCase):
    """Overriding to GAME never leaks a DRAFT or ARCHIVED record."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="editor", password="p")

    def setUp(self):
        self.client.force_login(self.user)

    def test_draft_or_archived_override_never_leaks(self):
        for status in (ListingStatus.DRAFT, ListingStatus.ARCHIVED):
            with self.subTest(status=status):
                game = Game.objects.create(
                    source_type=SourceType.MANUAL,
                    name=f"Manual {status.value}",
                    slug=f"manual-{status.value}",
                    content_type=ContentType.DLC,
                    listing_status=status,
                )
                url = reverse("admin:games_game_change", args=(game.pk,))
                self.client.post(
                    url,
                    {
                        "source_type": SourceType.MANUAL,
                        "external_id": "",
                        "name": f"Manual {status.value}",
                        "slug": f"manual-{status.value}",
                        "content_type": ContentType.GAME,
                        "listing_status": status,
                        "release_date": "",
                        "developer": "",
                        "description": "",
                        "manual_image_url": "",
                        "manual_website_url": "",
                        "_changelist_filters": "",
                    },
                )
                game.refresh_from_db()
                self.assertEqual(game.content_type, ContentType.GAME)
                self.assertNotIn(game, Game.objects.publicly_listable())


# ---------------------------------------------------------------------------
# Steam refresh preservation
# ---------------------------------------------------------------------------


class RefreshOverridePreservationTests(TestCase):
    """Steam refresh never reverts a manual content_type override (SBGC-96)."""

    def _make_game(self, **kwargs) -> Game:
        defaults = dict(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Test Steam",
            slug="test-steam",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        defaults.update(kwargs)
        return Game.objects.create(**defaults)

    def _refresh_service(self, foundation):
        return SteamGameRefreshService(
            foundation,
            SteamGamePersistenceService(),
        )

    def test_override_preserved_on_refresh(self):
        game = self._make_game(content_type_overridden=True)

        foundation = mock.MagicMock(spec=SteamImportFoundation)
        foundation.prepare_candidate.return_value = _refresh_lookup("dlc")
        service = self._refresh_service(foundation)

        result = service.refresh(game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UNCHANGED)
        game.refresh_from_db()
        self.assertEqual(game.content_type, ContentType.GAME)
        self.assertTrue(game.content_type_overridden)

    def test_unoverridden_refresh_applies_upstream_type(self):
        game = self._make_game()

        foundation = mock.MagicMock(spec=SteamImportFoundation)
        foundation.prepare_candidate.return_value = _refresh_lookup("dlc")
        service = self._refresh_service(foundation)

        result = service.refresh(game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        game.refresh_from_db()
        self.assertEqual(game.content_type, ContentType.DLC)
        self.assertFalse(game.content_type_overridden)
