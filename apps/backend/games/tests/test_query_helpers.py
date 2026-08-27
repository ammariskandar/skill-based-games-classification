"""
Game query helper tests — SBGC-49 / SBGC-199.

Table-level listing/source helpers only. The submission-level queryset helpers
(``editorially_classified``, ``with_editorial_profiles``, submission-joining
dominance/score filters, and score sortings) were retired in SBGC-199: the
published ``ClassificationSnapshot`` is now the sole read authority.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from games.models import ContentType, Game, ListingStatus, SourceType


def _make(**kw):
    defaults = {
        "source_type": SourceType.MANUAL,
        "content_type": ContentType.GAME,
        "listing_status": ListingStatus.PUBLISHED,
    }
    return Game.objects.create(**{**defaults, **kw})


class SourceHelperTests(TestCase):
    def setUp(self):
        _make(
            name="Steam Game",
            slug="steam-game",
            source_type=SourceType.STEAM,
            external_id="100",
        )
        _make(name="Manual Game", slug="manual-game")

    def test_steam_returns_only_steam(self):
        qs = Game.objects.steam()
        self.assertEqual(qs.count(), 1)
        game = qs.first()
        if game is None:
            self.fail("Expected a Steam game to exist")
        self.assertEqual(game.source_type, SourceType.STEAM)

    def test_manual_returns_only_manual(self):
        qs = Game.objects.manual()
        self.assertEqual(qs.count(), 1)
        game = qs.first()
        if game is None:
            self.fail("Expected a manual game to exist")
        self.assertEqual(game.source_type, SourceType.MANUAL)

    def test_steam_chainable_with_publicly_listable(self):
        qs = Game.objects.steam().publicly_listable()
        self.assertEqual(qs.count(), 1)

    def test_manual_chainable_with_publicly_listable(self):
        qs = Game.objects.manual().publicly_listable()
        self.assertEqual(qs.count(), 1)


class DefaultManagerTests(TestCase):
    def setUp(self):
        _make(
            name="DM Published",
            slug="dm-pub",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        _make(
            name="DM DLC",
            slug="dm-dlc",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
        )
        _make(
            name="DM Draft",
            slug="dm-draft",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.DRAFT,
        )

    def test_all_returns_every_record(self):
        self.assertEqual(Game.objects.all().count(), 3)

    def test_all_includes_non_game(self):
        slugs = set(Game.objects.all().values_list("slug", flat=True))
        self.assertIn("dm-dlc", slugs)

    def test_all_includes_draft(self):
        slugs = set(Game.objects.all().values_list("slug", flat=True))
        self.assertIn("dm-draft", slugs)

    def test_publicly_listable_excludes_draft_and_non_game(self):
        slugs = set(Game.objects.publicly_listable().values_list("slug", flat=True))
        self.assertEqual(slugs, {"dm-pub"})


class NoNetworkTests(TestCase):
    def _steam_guard(self):
        return patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("SteamClient must not be called"),
        )

    def setUp(self):
        _make(name="NoNet", slug="nonet")

    def test_steam_helper_no_steam(self):
        with self._steam_guard():
            list(Game.objects.steam())
