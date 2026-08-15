"""
Manual Game service tests — SBGC-59.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from classifications.services.editorial import (
    ScoreDistribution,
    set_editorial_classification,
)
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from games.models import Game, ListingStatus, SourceType
from games.services.manual import (
    ManualGameError,
    create_manual_game,
    update_manual_game,
)
from games.types import ContentType


class CreateManualGameTests(TestCase):
    def test_creates_manual_game_with_forced_identity(self):
        game = create_manual_game(name="Chess")

        self.assertEqual(game.source_type, SourceType.MANUAL)
        self.assertIsNone(game.external_id)
        self.assertEqual(game.name, "Chess")
        self.assertEqual(game.slug, "chess")
        self.assertEqual(game.content_type, ContentType.GAME)
        self.assertEqual(game.listing_status, ListingStatus.DRAFT)
        self.assertEqual(game.manual_description, "")
        self.assertEqual(game.manual_image_url, "")
        self.assertEqual(game.manual_website_url, "")
        self.assertEqual(game.steam_image_url, "")
        self.assertIsNone(game.last_steam_refresh_at)

    def test_persists_metadata_content_and_listing(self):
        game = create_manual_game(
            name="Go",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
            manual_description="Abstract strategy game",
            manual_image_url="https://example.com/go.jpg",
            manual_website_url="https://example.com",
        )

        self.assertEqual(game.manual_description, "Abstract strategy game")
        self.assertEqual(game.manual_image_url, "https://example.com/go.jpg")
        self.assertEqual(game.manual_website_url, "https://example.com")
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)

    def test_release_date_and_developer_default_empty(self):
        game = create_manual_game(name="Go")

        self.assertIsNone(game.release_date)
        self.assertEqual(game.developer, "")

    def test_persists_release_date_and_developer(self):
        game = create_manual_game(
            name="Go",
            release_date=date(2026, 1, 15),
            developer="Acme Games",
        )

        self.assertEqual(game.release_date, date(2026, 1, 15))
        self.assertEqual(game.developer, "Acme Games")

    def test_slug_generated_from_name(self):
        game = create_manual_game(name="  Hello  World  ")
        self.assertEqual(game.slug, "hello-world")

    def test_explicit_slug(self):
        game = create_manual_game(name="Chess", slug="custom-chess")
        self.assertEqual(game.slug, "custom-chess")

    def test_blank_name_rejected(self):
        with self.assertRaises(ValueError):
            create_manual_game(name="   ")

    def test_duplicate_slug_rejected(self):
        create_manual_game(name="Chess", slug="chess")
        with self.assertRaises(ValidationError):
            create_manual_game(name="Chess 2", slug="chess")

    def test_published_manual_game_is_publicly_listable(self):
        game = create_manual_game(name="Chess", listing_status=ListingStatus.PUBLISHED)
        self.assertIn(game, Game.objects.publicly_listable())

    def test_published_manual_non_game_is_excluded(self):
        game = create_manual_game(
            name="Sample Tool",
            content_type=ContentType.SOFTWARE,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.assertNotIn(game, Game.objects.publicly_listable())


class UpdateManualGameTests(TestCase):
    def setUp(self):
        self.game = create_manual_game(name="Chess")

    def test_updates_allowed_fields_and_preserves_slug(self):
        game = update_manual_game(
            self.game,
            name="Chess Renamed",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
            manual_description="updated",
            manual_image_url="https://example.com/new.jpg",
            manual_website_url="https://example.com/new",
        )

        self.assertEqual(game.name, "Chess Renamed")
        self.assertEqual(game.slug, "chess")
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)
        self.assertEqual(game.manual_description, "updated")
        self.assertEqual(game.manual_image_url, "https://example.com/new.jpg")
        self.assertEqual(game.manual_website_url, "https://example.com/new")

    def test_explicit_slug_update(self):
        game = update_manual_game(self.game, slug="new-slug")
        self.assertEqual(game.slug, "new-slug")

    def test_updates_release_date_and_developer(self):
        game = update_manual_game(
            self.game,
            release_date=date(2025, 6, 1),
            developer="Indie Studio",
        )

        self.assertEqual(game.release_date, date(2025, 6, 1))
        self.assertEqual(game.developer, "Indie Studio")

    def test_release_date_kept_when_omitted(self):
        self.game.release_date = date(2024, 1, 1)
        self.game.save()

        game = update_manual_game(self.game, name="Chess Renamed")

        self.assertEqual(game.release_date, date(2024, 1, 1))

    def test_release_date_cleared_with_none(self):
        self.game.release_date = date(2024, 1, 1)
        self.game.save()

        game = update_manual_game(self.game, release_date=None)

        self.assertIsNone(game.release_date)

    def test_developer_kept_when_omitted(self):
        self.game.developer = "Old Studio"
        self.game.save()

        game = update_manual_game(self.game, name="Chess Renamed")

        self.assertEqual(game.developer, "Old Studio")

    def test_developer_cleared_with_empty_string(self):
        self.game.developer = "Old Studio"
        self.game.save()

        game = update_manual_game(self.game, developer="")

        self.assertEqual(game.developer, "")

    def test_steam_identity_and_metadata_untouched(self):
        game = update_manual_game(self.game, manual_description="edited")

        self.assertEqual(game.source_type, SourceType.MANUAL)
        self.assertIsNone(game.external_id)
        self.assertEqual(game.steam_image_url, "")
        self.assertIsNone(game.last_steam_refresh_at)

    def test_steam_game_rejected_without_mutation(self):
        steam = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
        )

        with self.assertRaises(ManualGameError):
            update_manual_game(steam, name="Changed")

        steam.refresh_from_db()
        self.assertEqual(steam.name, "Portal 2")
        self.assertEqual(steam.source_type, SourceType.STEAM)
        self.assertEqual(steam.external_id, "620")

    def test_unsaved_game_rejected(self):
        unsaved = Game(source_type=SourceType.MANUAL, name="X", slug="x")
        with self.assertRaises(ManualGameError):
            update_manual_game(unsaved, name="Y")

    def test_editorial_classification_preserved(self):
        user = User.objects.create_user(username="editor", password="p")
        parent = set_editorial_classification(
            game=self.game,
            updated_by=user,
            challenge=ScoreDistribution(micro=30, mystiko=30, macro=40),
            reward=ScoreDistribution(micro=50, mystiko=20, macro=30),
            notes="original notes",
        )

        update_manual_game(self.game, name="Chess Renamed", manual_description="x")

        parent.refresh_from_db()
        self.assertEqual(parent.notes, "original notes")
        self.assertEqual(parent.challenge_profile.micro_score, 30)
        self.assertEqual(parent.challenge_profile.mystiko_score, 30)
        self.assertEqual(parent.challenge_profile.macro_score, 40)
        self.assertEqual(parent.reward_profile.micro_score, 50)
        self.assertEqual(parent.reward_profile.mystiko_score, 20)
        self.assertEqual(parent.reward_profile.macro_score, 30)


class NoNetworkTests(TestCase):
    def test_manual_crud_does_not_touch_steam(self):
        with patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("SteamClient must not be called"),
        ):
            game = create_manual_game(name="No Network")
            update_manual_game(game, name="No Network 2")
