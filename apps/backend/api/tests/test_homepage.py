"""
Homepage carousel endpoint tests — SBGC-189.

Exercises ``GET /api/v1/games/homepage`` eligibility, randomness, count
bounds, and card fields.
"""

from __future__ import annotations

from django.test import Client, TestCase
from games.models import Game, ListingStatus, SourceType

_app_id = 1_000_000


def _game(slug: str, **kwargs) -> Game:
    global _app_id
    _app_id += 1
    defaults = dict(
        name=slug.replace("-", " ").title(),
        slug=slug,
        source_type=SourceType.STEAM,
        external_id=str(_app_id),
        content_type="game",
        listing_status=ListingStatus.PUBLISHED,
        library_capsule_url=f"https://cdn.example.com/{slug}/capsule.jpg",
    )
    defaults.update(kwargs)
    return Game.objects.create(**defaults)


def _get():
    return Client().get("/api/v1/games/homepage")


class HomepageCarouselEligibilityTests(TestCase):
    def test_returns_public_steam_base_games_with_capsule(self):
        a = _game("game-a")
        b = _game("game-b")
        r = _get()

        self.assertEqual(r.status_code, 200)
        slugs = {card["slug"] for card in r.json()["games"]}
        self.assertEqual(slugs, {a.slug, b.slug})

    def test_excludes_manual_games(self):
        _game("manual-game", source_type=SourceType.MANUAL, external_id=None)
        r = _get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["games"], [])

    def test_excludes_non_public_listing_statuses(self):
        for status in ("draft", "archived"):
            _game(f"game-{status}", listing_status=status)
        r = _get()
        self.assertEqual(r.json()["games"], [])

    def test_excludes_non_game_content(self):
        for ct in ("dlc", "demo", "software", "soundtrack", "unknown"):
            _game(f"content-{ct}", content_type=ct)
        r = _get()
        self.assertEqual(r.json()["games"], [])

    def test_excludes_games_without_capsule(self):
        _game("no-capsule", library_capsule_url="")
        r = _get()
        self.assertEqual(r.json()["games"], [])

    def test_result_count_bounded_at_ten(self):
        for i in range(15):
            _game(f"game-{i}")
        r = _get()
        self.assertLessEqual(len(r.json()["games"]), 10)

    def test_no_duplicates(self):
        for i in range(12):
            _game(f"game-{i}")
        r = _get()
        slugs = [card["slug"] for card in r.json()["games"]]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_fewer_than_ten_returns_available_count(self):
        for i in range(3):
            _game(f"game-{i}")
        r = _get()
        self.assertEqual(len(r.json()["games"]), 3)

    def test_card_fields(self):
        _game("game-a", name="Game A")
        r = _get()
        card = r.json()["games"][0]
        self.assertEqual(set(card.keys()), {"slug", "name", "library_capsule_url"})
        self.assertEqual(card["slug"], "game-a")
        self.assertEqual(card["name"], "Game A")
        self.assertEqual(
            card["library_capsule_url"],
            "https://cdn.example.com/game-a/capsule.jpg",
        )
