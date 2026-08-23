"""
Game search-index endpoint tests — SBGC-78.

Exercises ``GET /api/v1/games/search-index``: public eligibility (Steam +
Manual, excluding non-game/draft/archived), missing-Capsule inclusion,
effective Capsule override, deterministic ordering, and the minimal response
shape.
"""

from __future__ import annotations

from django.test import Client, TestCase
from games.models import ContentType, Game, ListingStatus, SourceType

_app_id = 3_000_000


def _game(slug: str, **kwargs) -> Game:
    global _app_id
    _app_id += 1
    defaults = dict(
        name=slug.replace("-", " ").title(),
        slug=slug,
        source_type=SourceType.STEAM,
        external_id=str(_app_id),
        content_type=ContentType.GAME,
        listing_status=ListingStatus.PUBLISHED,
    )
    defaults.update(kwargs)
    return Game.objects.create(**defaults)


def _manual(slug: str, **kwargs) -> Game:
    kwargs.setdefault("source_type", SourceType.MANUAL)
    kwargs.setdefault("external_id", None)
    return _game(slug, **kwargs)


def _get():
    return Client().get("/api/v1/games/search-index")


class SearchIndexEligibilityTests(TestCase):
    def test_only_public_base_games_returned(self):
        _game("published-steam", name="A Steam")
        _manual("published-manual", name="B Manual")
        _game("draft-game", name="C Draft", listing_status=ListingStatus.DRAFT)
        _game("archived-game", name="D Archived", listing_status=ListingStatus.ARCHIVED)
        _game("dlc", name="E Dlc", content_type=ContentType.DLC)
        _game("demo", name="F Demo", content_type=ContentType.DEMO)
        _game("software", name="G Software", content_type=ContentType.SOFTWARE)
        _game("soundtrack", name="H Soundtrack", content_type=ContentType.SOUNDTRACK)
        _game("unknown", name="I Unknown", content_type=ContentType.UNKNOWN)

        r = _get()
        self.assertEqual(r.status_code, 200)
        slugs = {item["slug"] for item in r.json()["games"]}
        self.assertEqual(slugs, {"published-steam", "published-manual"})

    def test_missing_capsule_included(self):
        _game("no-capsule", name="No Capsule")
        r = _get()
        self.assertEqual(r.json()["games"][0]["slug"], "no-capsule")
        self.assertIsNone(r.json()["games"][0]["capsule_url"])

    def test_deterministic_ordering(self):
        _game("zeta", name="Zeta")
        _game("alpha", name="Alpha")
        _game("beta", name="Beta")
        r = _get()
        names = [item["name"] for item in r.json()["games"]]
        self.assertEqual(names, ["Alpha", "Beta", "Zeta"])

    def test_duplicate_name_stable_by_id(self):
        a = _game("dup-a", name="Same Name")
        b = _game("dup-b", name="Same Name")
        r = _get()
        slugs = [item["slug"] for item in r.json()["games"]]
        self.assertEqual(slugs, [a.slug, b.slug])


class SearchIndexShapeTests(TestCase):
    def test_minimal_shape(self):
        _game("shape-game", name="Shape Game")
        r = _get()
        item = r.json()["games"][0]
        self.assertEqual(set(item.keys()), {"slug", "name", "capsule_url", "image_url"})

    def test_effective_manual_capsule_override(self):
        _game(
            "override-game",
            name="Override Game",
            library_capsule_url="https://cdn.example.com/steam-capsule.jpg",
            manual_capsule_url="https://example.com/manual-capsule.jpg",
        )
        r = _get()
        self.assertEqual(
            r.json()["games"][0]["capsule_url"],
            "https://example.com/manual-capsule.jpg",
        )

    def test_effective_general_image(self):
        _game(
            "image-game",
            name="Image Game",
            steam_image_url="https://cdn.example.com/header.jpg",
            manual_image_url="https://example.com/manual-header.jpg",
        )
        r = _get()
        self.assertEqual(
            r.json()["games"][0]["image_url"],
            "https://example.com/manual-header.jpg",
        )

    def test_no_capsule_or_image_are_null(self):
        _manual("bare-manual", name="Bare Manual")
        r = _get()
        item = r.json()["games"][0]
        self.assertIsNone(item["capsule_url"])
        self.assertIsNone(item["image_url"])
