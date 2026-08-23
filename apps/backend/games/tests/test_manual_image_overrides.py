"""
Manual image override + effective resolver tests — SBGC-190.

Covers the three independent manual image roles (image/hero/capsule), the
source-aware effective resolvers, the shared extension validator, and Steam
refresh preservation of manual overrides.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from games.models import ContentType, Game, ListingStatus, SourceType
from games.services.assets import ManualAssetError, validate_manual_image_url
from games.services.imports.steam import (
    SteamGamePersistenceService,
    SteamGameRefreshService,
)
from games.services.steam.dto import (
    LookupStatus,
    SteamAppLookupResult,
    SteamGameImportCandidate,
)
from games.services.steam.import_foundation import SteamImportFoundation


def _steam(**kwargs) -> Game:
    defaults = dict(
        source_type=SourceType.STEAM,
        external_id="620",
        name="Portal 2",
        slug="portal-2",
        content_type=ContentType.GAME,
        steam_image_url="https://cdn.example.com/steam.jpg",
        library_hero_url="https://cdn.example.com/steam_hero.jpg",
        library_capsule_url="https://cdn.example.com/steam_capsule.jpg",
    )
    defaults.update(kwargs)
    return Game.objects.create(**defaults)


def _manual(**kwargs) -> Game:
    defaults = dict(source_type=SourceType.MANUAL, name="Chess", slug="chess")
    defaults.update(kwargs)
    return Game.objects.create(**defaults)


class EffectiveResolverTests(TestCase):
    def test_steam_no_overrides_uses_steam(self):
        game = _steam()
        self.assertEqual(game.display_image_url, game.steam_image_url)
        self.assertEqual(game.display_hero_url, game.library_hero_url)
        self.assertEqual(game.display_capsule_url, game.library_capsule_url)

    def test_steam_image_override_only(self):
        game = _steam(manual_image_url="https://example.com/image.jpg")
        self.assertEqual(game.display_image_url, "https://example.com/image.jpg")
        self.assertEqual(game.display_hero_url, game.library_hero_url)
        self.assertEqual(game.display_capsule_url, game.library_capsule_url)

    def test_steam_hero_override_only(self):
        game = _steam(manual_hero_url="https://example.com/hero.jpg")
        self.assertEqual(game.display_image_url, game.steam_image_url)
        self.assertEqual(game.display_hero_url, "https://example.com/hero.jpg")
        self.assertEqual(game.display_capsule_url, game.library_capsule_url)

    def test_steam_capsule_override_only(self):
        game = _steam(manual_capsule_url="https://example.com/capsule.jpg")
        self.assertEqual(game.display_image_url, game.steam_image_url)
        self.assertEqual(game.display_hero_url, game.library_hero_url)
        self.assertEqual(game.display_capsule_url, "https://example.com/capsule.jpg")

    def test_steam_all_overrides(self):
        game = _steam(
            manual_image_url="https://example.com/image.jpg",
            manual_hero_url="https://example.com/hero.jpg",
            manual_capsule_url="https://example.com/capsule.jpg",
        )
        self.assertEqual(game.display_image_url, "https://example.com/image.jpg")
        self.assertEqual(game.display_hero_url, "https://example.com/hero.jpg")
        self.assertEqual(game.display_capsule_url, "https://example.com/capsule.jpg")

    def test_manual_effective_uses_manual_values(self):
        game = _manual(
            manual_image_url="https://example.com/image.jpg",
            manual_hero_url="https://example.com/hero.jpg",
            manual_capsule_url="https://example.com/capsule.jpg",
        )
        self.assertEqual(game.display_image_url, "https://example.com/image.jpg")
        self.assertEqual(game.display_hero_url, "https://example.com/hero.jpg")
        self.assertEqual(game.display_capsule_url, "https://example.com/capsule.jpg")

    def test_manual_never_falls_back_to_steam_even_if_corrupt(self):
        game = _manual(
            steam_image_url="https://cdn.example.com/steam.jpg",
            library_hero_url="https://cdn.example.com/hero.jpg",
            library_capsule_url="https://cdn.example.com/capsule.jpg",
            manual_image_url="https://example.com/image.jpg",
        )
        self.assertEqual(game.display_image_url, "https://example.com/image.jpg")
        self.assertEqual(game.display_hero_url, "")
        self.assertEqual(game.display_capsule_url, "")


class ManualImageExtensionValidationTests(TestCase):
    ACCEPT = [
        "https://example.com/a.jpg",
        "https://example.com/a.JPG",
        "https://example.com/a.jpeg",
        "https://example.com/a.JPEG",
        "https://example.com/a.png",
        "https://example.com/a.PNG",
        "https://example.com/a.webp",
        "https://example.com/a.WEBP",
        "https://example.com/a.jpg?v=1",
        "https://example.com/a.jpeg?token=abc",
        "https://example.com/path/a.webp?token=abc",
        "https://example.com/path/a.JPEG?cache=1",
    ]
    REJECT = [
        "http://example.com/a.jpg",
        "http://example.com/a.jpeg",
        "ftp://example.com/a.jpg",
        "https://example.com/a.gif",
        "https://example.com/a.svg",
        "https://example.com/a.avif",
        "https://example.com/a.bmp",
        "https://example.com/a.tif",
        "https://example.com/a.tiff",
        "https://example.com/a",
        "https://example.com/a.jpg.gif",
        "https://example.com/a.jpeg.gif",
        "https://example.com/a.png.exe",
        "not-a-url",
    ]

    def test_accept(self):
        for url in self.ACCEPT:
            with self.subTest(url=url):
                self.assertTrue(validate_manual_image_url(url))

    def test_reject(self):
        for url in self.REJECT:
            with self.subTest(url=url):
                with self.assertRaises(ManualAssetError):
                    validate_manual_image_url(url)

    def test_model_clean_rejects_bad_extension(self):
        game = Game(
            source_type=SourceType.MANUAL,
            name="Bad",
            slug="bad",
            manual_image_url="https://example.com/img.gif",
        )
        with self.assertRaises(ValidationError):
            game.full_clean()

    def test_model_clean_accepts_valid_manual_fields(self):
        game = Game(
            source_type=SourceType.MANUAL,
            name="Good",
            slug="good",
            manual_image_url="https://example.com/img.jpg",
            manual_hero_url="https://example.com/hero.jpeg",
            manual_capsule_url="https://example.com/capsule.png",
        )
        game.full_clean()  # must not raise


class SteamRefreshPreservationTests(TestCase):
    def _refresh(self, game: Game, header_image_url: str) -> Game:
        candidate = SteamGameImportCandidate(
            app_id=game.external_id,
            name=game.name,
            content_type=game.content_type,
            header_image_url=header_image_url,
            description=None,
            developer=None,
            release_date=None,
        )
        lookup = SteamAppLookupResult(
            status=LookupStatus.FOUND,
            app_id=game.external_id,
            candidate=candidate,
        )
        foundation = mock.MagicMock(spec=SteamImportFoundation)
        foundation.prepare_candidate.return_value = lookup
        service = SteamGameRefreshService(foundation, SteamGamePersistenceService())
        service.refresh(game)
        game.refresh_from_db()
        return game

    def test_refresh_updates_steam_but_preserves_manual_overrides(self):
        game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
            content_type=ContentType.GAME,
            steam_image_url="https://cdn.example.com/A.jpg",
            library_hero_url="https://cdn.example.com/B.jpg",
            library_capsule_url="https://cdn.example.com/C.jpg",
            manual_image_url="https://example.com/X.jpg",
            manual_hero_url="https://example.com/Y.jpeg",
            manual_capsule_url="https://example.com/Z.webp",
        )

        game = self._refresh(game, "https://cdn.example.com/A2.jpg")

        # Steam source metadata updated.
        self.assertEqual(game.steam_image_url, "https://cdn.example.com/A2.jpg")
        # Manual overrides preserved.
        self.assertEqual(game.manual_image_url, "https://example.com/X.jpg")
        self.assertEqual(game.manual_hero_url, "https://example.com/Y.jpeg")
        self.assertEqual(game.manual_capsule_url, "https://example.com/Z.webp")
        # Effective values still resolve to the manual overrides.
        self.assertEqual(game.display_image_url, "https://example.com/X.jpg")
        self.assertEqual(game.display_hero_url, "https://example.com/Y.jpeg")
        self.assertEqual(game.display_capsule_url, "https://example.com/Z.webp")

        # Clear only the Hero override → falls back to the refreshed Steam Hero.
        game.manual_hero_url = ""
        game.save()
        self.assertEqual(game.display_hero_url, game.library_hero_url)
        self.assertNotEqual(game.display_hero_url, "")
        # Other roles remain overridden.
        self.assertEqual(game.display_image_url, "https://example.com/X.jpg")
        self.assertEqual(game.display_capsule_url, "https://example.com/Z.webp")


class GameAdminImageOverrideTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="editor", password="p")
        self.client.force_login(self.user)
        self.game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Test Steam",
            slug="test-steam",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.DRAFT,
        )
        self.url = reverse("admin:games_game_change", args=(self.game.pk,))

    def _data(self, **overrides) -> dict:
        data = {
            "source_type": SourceType.STEAM,
            "external_id": "730",
            "name": "Test Steam",
            "slug": "test-steam",
            "content_type": ContentType.GAME,
            "listing_status": ListingStatus.DRAFT,
            "release_date": "",
            "developer": "",
            "description": "",
            "manual_image_url": "",
            "manual_hero_url": "",
            "manual_capsule_url": "",
            "manual_website_url": "",
            "_changelist_filters": "",
        }
        data.update(overrides)
        return data

    def test_save_valid_manual_image_overrides(self):
        response = self.client.post(
            self.url,
            self._data(
                manual_image_url="https://example.com/image.jpg",
                manual_hero_url="https://example.com/hero.jpeg",
                manual_capsule_url="https://example.com/capsule.webp",
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.game.refresh_from_db()
        self.assertEqual(self.game.manual_image_url, "https://example.com/image.jpg")
        self.assertEqual(self.game.manual_hero_url, "https://example.com/hero.jpeg")
        self.assertEqual(
            self.game.manual_capsule_url, "https://example.com/capsule.webp"
        )

    def test_invalid_extension_returns_form_error(self):
        response = self.client.post(
            self.url,
            self._data(manual_capsule_url="https://example.com/capsule.gif"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Use an HTTPS image URL ending in .jpg, .jpeg, .png, or .webp.",
        )
        self.game.refresh_from_db()
        self.assertEqual(self.game.manual_capsule_url, "")
