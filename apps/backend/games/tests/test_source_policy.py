"""
Source-specific Game policy tests — SBGC-61.
"""

from __future__ import annotations

from django.test import TestCase

from games.models import Game, ListingStatus, SourceType
from games.services.manual import create_manual_game
from games.services.source_policy import can_manual_edit, can_steam_refresh
from games.types import ContentType


class SourcePropertyTests(TestCase):
    def test_manual_game_flags(self):
        game = create_manual_game(name="Chess")
        self.assertTrue(game.is_manual)
        self.assertFalse(game.is_steam)

    def test_steam_game_flags(self):
        game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
        )
        self.assertTrue(game.is_steam)
        self.assertFalse(game.is_manual)


class CapabilityTests(TestCase):
    def setUp(self):
        self.manual = create_manual_game(name="Chess")
        self.steam = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
        )

    def test_manual_edit_capability(self):
        self.assertTrue(can_manual_edit(self.manual))
        self.assertFalse(can_manual_edit(self.steam))

    def test_steam_refresh_capability(self):
        self.assertFalse(can_steam_refresh(self.manual))
        self.assertTrue(can_steam_refresh(self.steam))


class ListingSourceIndependenceTests(TestCase):
    def test_published_manual_and_steam_games_listable(self):
        manual = create_manual_game(
            name="Chess", listing_status=ListingStatus.PUBLISHED
        )
        steam = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
            listing_status=ListingStatus.PUBLISHED,
        )

        listed_ids = set(Game.objects.publicly_listable().values_list("id", flat=True))
        self.assertIn(manual.pk, listed_ids)
        self.assertIn(steam.pk, listed_ids)

    def test_published_non_game_excluded_regardless_of_source(self):
        manual_dlc = create_manual_game(
            name="Manual DLC",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
        )
        steam_dlc = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="1",
            name="Steam DLC",
            slug="steam-dlc",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
        )

        listed = Game.objects.publicly_listable()
        self.assertNotIn(manual_dlc, listed)
        self.assertNotIn(steam_dlc, listed)
