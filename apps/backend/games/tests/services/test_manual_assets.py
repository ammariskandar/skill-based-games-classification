"""
Manual asset handling tests — SBGC-60.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase

from games.models import Game, SourceType
from games.services.assets import ManualAssetError, validate_manual_image_url
from games.services.manual import create_manual_game, update_manual_game


class ValidateManualImageUrlTests(TestCase):
    def test_blank_returns_empty(self):
        self.assertEqual(validate_manual_image_url(""), "")

    def test_whitespace_returns_empty(self):
        self.assertEqual(validate_manual_image_url("   "), "")

    def test_valid_https_returned_stripped(self):
        self.assertEqual(
            validate_manual_image_url("  https://example.com/img.jpg  "),
            "https://example.com/img.jpg",
        )

    def test_http_rejected(self):
        with self.assertRaises(ManualAssetError):
            validate_manual_image_url("http://example.com/img.jpg")

    def test_ftp_rejected(self):
        with self.assertRaises(ManualAssetError):
            validate_manual_image_url("ftp://example.com/img.jpg")

    def test_javascript_rejected(self):
        with self.assertRaises(ManualAssetError):
            validate_manual_image_url("javascript:alert(1)")

    def test_credentials_rejected(self):
        with self.assertRaises(ManualAssetError):
            validate_manual_image_url("https://user:pass@example.com/img.jpg")

    def test_missing_hostname_rejected(self):
        with self.assertRaises(ManualAssetError):
            validate_manual_image_url("https:///img.jpg")

    def test_non_string_rejected(self):
        with self.assertRaises(ManualAssetError):
            validate_manual_image_url(123)  # type: ignore[arg-type]

    def test_control_characters_rejected(self):
        with self.assertRaises(ManualAssetError):
            validate_manual_image_url("https://example.com/img.jpg\x00")


class ManualImageServiceTests(TestCase):
    def test_create_manual_game_valid_image_persists(self):
        game = create_manual_game(
            name="Chess", manual_image_url="https://example.com/chess.jpg"
        )
        self.assertEqual(game.manual_image_url, "https://example.com/chess.jpg")

    def test_create_manual_game_invalid_image_rejected(self):
        with self.assertRaises(ValidationError):
            create_manual_game(
                name="Chess", manual_image_url="http://example.com/chess.jpg"
            )

    def test_update_manual_game_replaces_image(self):
        game = create_manual_game(name="Chess")
        update_manual_game(game, manual_image_url="https://example.com/new.jpg")
        game.refresh_from_db()
        self.assertEqual(game.manual_image_url, "https://example.com/new.jpg")

    def test_update_manual_game_clears_image_with_empty_string(self):
        game = create_manual_game(
            name="Chess", manual_image_url="https://example.com/chess.jpg"
        )
        update_manual_game(game, manual_image_url="")
        game.refresh_from_db()
        self.assertEqual(game.manual_image_url, "")

    def test_manual_asset_does_not_touch_steam_image_url(self):
        game = create_manual_game(
            name="Chess", manual_image_url="https://example.com/chess.jpg"
        )
        update_manual_game(game, name="Chess Renamed")

        game.refresh_from_db()
        self.assertEqual(game.steam_image_url, "")
        self.assertIsNone(game.last_steam_refresh_at)


class DisplayImageUrlTests(TestCase):
    def test_manual_override_for_steam(self):
        game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
            steam_image_url="https://cdn.example.com/steam.jpg",
            manual_image_url="https://example.com/manual.jpg",
        )
        self.assertEqual(game.display_image_url, "https://example.com/manual.jpg")

    def test_falls_back_to_steam(self):
        game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Counter-Strike",
            slug="counter-strike",
            steam_image_url="https://cdn.example.com/steam.jpg",
        )
        self.assertEqual(game.display_image_url, "https://cdn.example.com/steam.jpg")

    def test_empty_for_manual_without_image(self):
        game = create_manual_game(name="Chess")
        self.assertEqual(game.display_image_url, "")
