"""
Content-type & listing exclusions across every public read path — SBGC-97.

End-to-end verification that DLC/DEMO/SOFTWARE/SOUNDTRACK/UNKNOWN and
DRAFT/ARCHIVED records are unreachable through the public detail, catalogue,
rankings, and search-index surfaces — even when they carry current READY
published classifications.  The queryset boundary everywhere is
``Game.objects.publicly_listable()`` (content_type=GAME AND
listing_status=PUBLISHED).
"""

from __future__ import annotations

from classifications.models import CalculationEpoch, ClassificationSnapshot
from django.test import Client, TestCase
from django.utils import timezone

from games.models import ContentType, Game, ListingStatus, SourceType

_APP_SEQ = 2_000_000


def _next_app_id() -> str:
    global _APP_SEQ
    _APP_SEQ += 1
    return str(_APP_SEQ)


def _game(slug: str, **kwargs) -> Game:
    defaults = dict(
        name=slug.replace("-", " ").title(),
        slug=slug,
        source_type=SourceType.STEAM,
        external_id=_next_app_id(),
        content_type=ContentType.GAME,
        listing_status=ListingStatus.PUBLISHED,
    )
    defaults.update(kwargs)
    return Game.objects.create(**defaults)


def _epoch() -> CalculationEpoch:
    epoch, _ = CalculationEpoch.objects.get_or_create(
        epoch_id="exclusions-everywhere-epoch",
        defaults={
            "cutoff_at": timezone.now(),
            "master_version": "STATISTICAL_MODEL_V1.0.0",
        },
    )
    return epoch


def _ready_snapshot(game: Game, **kwargs) -> ClassificationSnapshot:
    """A current READY published classification (the API read boundary)."""
    defaults = dict(
        epoch=_epoch(),
        regime="provisional",
        status="READY",
        cutoff_at=timezone.now(),
        is_current=True,
        is_stale=False,
        calculated_at=timezone.now(),
        master_version="STATISTICAL_MODEL_V1.0.0",
        methods_version="METHODS_V1",
        bhpcm_version="BHPCM_V1",
        confidence_final_version="CONFIDENCE_V1",
        unified_integer_challenge=[51, 31, 18],
        unified_integer_reward=[17, 29, 54],
    )
    defaults.update(kwargs)
    return ClassificationSnapshot.objects.create(game=game, **defaults)


class ExclusionFixtureMixin:
    """One control Game + every exclusion class, all with READY snapshots."""

    @classmethod
    def setUpTestData(cls):
        cls.control = _game("valid-game")
        _ready_snapshot(cls.control)

        cls.non_games = [
            _game("expansion-pass", content_type=ContentType.DLC),
            _game("demo-slice", content_type=ContentType.DEMO),
            _game("benchmark-tool", content_type=ContentType.SOFTWARE),
            _game("official-soundtrack", content_type=ContentType.SOUNDTRACK),
            _game("unknown-entry", content_type=ContentType.UNKNOWN),
        ]
        # A published classification must never make a non-game listable.
        for game in cls.non_games:
            _ready_snapshot(game)

        cls.draft = _game("draft-game", listing_status=ListingStatus.DRAFT)
        cls.archived = _game("archived-game", listing_status=ListingStatus.ARCHIVED)


class DetailEndpointExclusionTests(ExclusionFixtureMixin, TestCase):
    """GET /api/v1/games/{slug} — identical 404s, zero disclosure."""

    def test_control_game_returns_200(self):
        response = Client().get("/api/v1/games/valid-game")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["game"]["slug"], "valid-game")

    def test_non_game_and_unlisted_slugs_all_404(self):
        for slug in (
            "expansion-pass",
            "demo-slice",
            "benchmark-tool",
            "official-soundtrack",
            "unknown-entry",
            "draft-game",
            "archived-game",
            "does-not-exist",
        ):
            with self.subTest(slug=slug):
                response = Client().get(f"/api/v1/games/{slug}")
                self.assertEqual(response.status_code, 404, slug)
                self.assertEqual(response.json()["error"]["code"], "GAME_NOT_FOUND")

    def test_non_game_404_is_indistinguishable_from_unknown_slug(self):
        non_game = Client().get("/api/v1/games/expansion-pass").json()
        unknown = Client().get("/api/v1/games/does-not-exist").json()
        self.assertEqual(non_game, unknown)


class CatalogueEndpointExclusionTests(ExclusionFixtureMixin, TestCase):
    """GET /api/v1/games/ — count/page/results strictly cover the control."""

    def test_base_catalogue_contains_only_control(self):
        body = Client().get("/api/v1/games/").json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["total_pages"], 1)
        self.assertEqual([g["slug"] for g in body["results"]], ["valid-game"])

    def test_search_matching_non_game_name_returns_nothing(self):
        # "Official Soundtrack" matches q=Soundtrack (icontains) but is
        # excluded, so the truthful result is an empty set.
        body = Client().get("/api/v1/games/?q=Soundtrack").json()
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["results"], [])

    def test_classified_filter_returns_only_control(self):
        body = Client().get("/api/v1/games/?classified=true").json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["slug"], "valid-game")

    def test_source_filter_returns_only_control(self):
        body = Client().get("/api/v1/games/?source=steam").json()
        self.assertEqual(body["count"], 1)
        self.assertEqual([g["slug"] for g in body["results"]], ["valid-game"])

    def test_full_filter_composition_never_counts_non_games(self):
        # sort + profile + dominant + coverless_last compose on top of
        # publicly_listable(); the non-games have READY snapshots that would
        # qualify them on score/dominance alone.
        body = (
            Client()
            .get(
                "/api/v1/games/?sort=micro&profile=challenge&dominant=micro"
                "&coverless_last=false"
            )
            .json()
        )
        self.assertEqual(body["count"], 1)
        self.assertEqual([g["slug"] for g in body["results"]], ["valid-game"])


class RankingsEndpointExclusionTests(ExclusionFixtureMixin, TestCase):
    """GET /api/v1/rankings/ — non-games with READY snapshots never rank."""

    def test_all_profiles_exclude_non_games(self):
        for params in (
            {"profile": "challenge", "dimension": "micro"},
            {"profile": "reward", "dimension": "macro"},
            {"profile": "unified", "dimension": "mystiko"},
        ):
            with self.subTest(**params):
                query = "&".join(f"{k}={v}" for k, v in params.items())
                body = Client().get(f"/api/v1/rankings/?{query}").json()
                self.assertEqual(body["count"], 1, params)
                self.assertEqual(
                    [item["slug"] for item in body["results"]],
                    ["valid-game"],
                    params,
                )


class SearchIndexEndpointExclusionTests(ExclusionFixtureMixin, TestCase):
    """GET /api/v1/games/search-index — the autocomplete array never leaks."""

    def test_search_index_contains_only_control(self):
        body = Client().get("/api/v1/games/search-index").json()
        self.assertEqual(len(body["games"]), 1)
        self.assertEqual(body["games"][0]["slug"], "valid-game")
