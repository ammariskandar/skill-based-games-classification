"""
Game catalogue endpoint tests — SBGC-76.

Exercises ``GET /api/v1/games/`` public eligibility, search, source and
classification filters, pagination, ordering, response shape, and query-count
boundedness.
"""

from __future__ import annotations

from decimal import Decimal

from classifications.models import CalculationEpoch, ClassificationSnapshot
from django.test import Client, TestCase
from django.utils import timezone
from games.models import ContentType, Game, ListingStatus, SourceType
from games.services.catalogue import CatalogueQuery, get_game_catalogue

_app_id = 2_000_000


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


def _epoch(epoch_id: str = "catalogue-epoch") -> CalculationEpoch:
    epoch, _ = CalculationEpoch.objects.get_or_create(
        epoch_id=epoch_id,
        defaults={
            "cutoff_at": timezone.now(),
            "master_version": "STATISTICAL_MODEL_V1.0.0",
        },
    )
    return epoch


def _snapshot(game: Game, **kwargs) -> ClassificationSnapshot:
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
        confidence_final=Decimal("85.50"),
        confidence_label="High",
    )
    defaults.update(kwargs)
    return ClassificationSnapshot.objects.create(game=game, **defaults)


def _get(**params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/api/v1/games/?{qs}" if qs else "/api/v1/games/"
    return Client().get(url)


class CatalogueEligibilityTests(TestCase):
    def test_only_published_base_games_returned(self):
        _game("published-game")
        _game("draft-game", listing_status=ListingStatus.DRAFT)
        _game("archived-game", listing_status=ListingStatus.ARCHIVED)
        _game("dlc", content_type=ContentType.DLC)
        _game("demo", content_type=ContentType.DEMO)
        _game("software", content_type=ContentType.SOFTWARE)
        _game("soundtrack", content_type=ContentType.SOUNDTRACK)
        _game("unknown", content_type=ContentType.UNKNOWN)
        _manual("manual-game")

        r = _get()
        self.assertEqual(r.status_code, 200)
        body = r.json()
        slugs = {item["slug"] for item in body["results"]}
        self.assertEqual(slugs, {"published-game", "manual-game"})
        self.assertEqual(body["count"], 2)


class CataloguePaginationTests(TestCase):
    def _make(self, n: int, *, name: str = "Game") -> list[Game]:
        return [_game(f"g-{i}", name=f"{name} {i:03d}") for i in range(n)]

    def test_default_page_size_is_24(self):
        self._make(30)
        r = _get()
        body = r.json()
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 24)
        self.assertEqual(body["count"], 30)
        self.assertEqual(body["total_pages"], 2)
        self.assertEqual(len(body["results"]), 24)

    def test_custom_page_size(self):
        self._make(10)
        r = _get(page_size=3)
        body = r.json()
        self.assertEqual(body["page_size"], 3)
        self.assertEqual(body["total_pages"], 4)
        self.assertEqual(len(body["results"]), 3)

    def test_last_partial_page(self):
        self._make(10)
        r = _get(page=4, page_size=3)
        body = r.json()
        self.assertEqual(len(body["results"]), 1)

    def test_page_beyond_last_returns_empty(self):
        self._make(5)
        r = _get(page=99, page_size=3)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["results"], [])
        self.assertEqual(r.json()["count"], 5)

    def test_zero_results_total_pages_zero(self):
        r = _get()
        body = r.json()
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["total_pages"], 0)
        self.assertEqual(body["results"], [])

    def test_stable_ordering_with_duplicate_names(self):
        a = _game("dup-a", name="Same Name")
        b = _game("dup-b", name="Same Name")
        r = _get(page_size=2)
        slugs = [item["slug"] for item in r.json()["results"]]
        self.assertEqual(slugs, [a.slug, b.slug])

    def test_invalid_page_rejected(self):
        for page in (0, -1):
            r = _get(page=page)
            self.assertEqual(r.status_code, 422)

    def test_invalid_page_size_rejected(self):
        for page_size in (0, 101):
            r = _get(page_size=page_size)
            self.assertEqual(r.status_code, 422)

    def test_page_size_100_accepted(self):
        self._make(101)
        r = _get(page_size=100)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["results"]), 100)


class CatalogueSearchTests(TestCase):
    def test_partial_and_case_insensitive(self):
        _game("elden-ring", name="ELDEN RING")
        _game("portal-2", name="Portal 2")
        r = _get(q="elden")
        self.assertEqual([i["slug"] for i in r.json()["results"]], ["elden-ring"])

    def test_whitespace_trimmed(self):
        _game("elden-ring", name="ELDEN RING")
        r = _get(q="  elden  ")
        self.assertEqual(r.json()["count"], 1)

    def test_whitespace_only_q_is_no_filter(self):
        _game("portal-2")
        r = _get(q="   ")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)

    def test_no_match(self):
        _game("portal-2")
        r = _get(q="zzz")
        self.assertEqual(r.json()["count"], 0)
        self.assertEqual(r.json()["results"], [])

    def test_hidden_matching_game_not_leaked(self):
        _game("hidden-match", name="Elden Match", listing_status=ListingStatus.DRAFT)
        r = _get(q="elden")
        self.assertEqual(r.json()["count"], 0)


class CatalogueSourceTests(TestCase):
    def test_steam_only(self):
        _game("steam-a")
        _manual("manual-a")
        r = _get(source="steam")
        self.assertEqual([i["slug"] for i in r.json()["results"]], ["steam-a"])

    def test_manual_only(self):
        _game("steam-a")
        _manual("manual-a")
        r = _get(source="manual")
        self.assertEqual([i["slug"] for i in r.json()["results"]], ["manual-a"])

    def test_omitted_returns_both(self):
        _game("steam-a")
        _manual("manual-a")
        r = _get()
        self.assertEqual(r.json()["count"], 2)

    def test_invalid_source_rejected(self):
        r = _get(source="invalid")
        self.assertEqual(r.status_code, 422)


class CatalogueClassificationTests(TestCase):
    def test_classified_true_readonly_ready(self):
        a = _game("ready-game")
        _snapshot(a, status="READY", unified_integer_challenge=[51, 31, 18])
        _game("unclassified-game")

        r = _get(classified="true")
        self.assertEqual([i["slug"] for i in r.json()["results"]], ["ready-game"])

    def test_classified_false_complement(self):
        a = _game("ready-game")
        _snapshot(a, status="READY")
        _game("unclassified-game")

        r = _get(classified="false")
        self.assertEqual(
            [i["slug"] for i in r.json()["results"]], ["unclassified-game"]
        )

    def test_non_ready_current_snapshot_not_classified(self):
        a = _game("no-submissions")
        _snapshot(
            a,
            status="NO_SUBMISSIONS",
            unified_integer_challenge=None,
            unified_integer_reward=None,
        )
        r = _get(classified="true")
        self.assertEqual(r.json()["count"], 0)

    def test_no_snapshot_not_classified(self):
        _game("no-snapshot")
        r = _get(classified="true")
        self.assertEqual(r.json()["count"], 0)

    def test_stale_ready_is_classified(self):
        a = _game("stale-ready")
        _snapshot(a, status="READY", is_stale=True)
        r = _get(classified="true")
        self.assertEqual([i["slug"] for i in r.json()["results"]], ["stale-ready"])


class CatalogueCombinedFilterTests(TestCase):
    def test_q_plus_source(self):
        _game("elden-ring", name="ELDEN RING")
        _manual("elden-manual", name="Elden Manual")
        _game("portal-2")
        r = _get(q="elden", source="steam")
        self.assertEqual([i["slug"] for i in r.json()["results"]], ["elden-ring"])

    def test_source_plus_classified(self):
        a = _game("steam-ready")
        _snapshot(a)
        _game("steam-bare")
        m = _manual("manual-ready")
        _snapshot(m)
        r = _get(source="steam", classified="true")
        self.assertEqual([i["slug"] for i in r.json()["results"]], ["steam-ready"])

    def test_q_source_classified(self):
        a = _game("persona-4-golden", name="Persona 4 Golden")
        _snapshot(a)
        r = _get(q="persona", source="steam", classified="true")
        self.assertEqual([i["slug"] for i in r.json()["results"]], ["persona-4-golden"])


class CatalogueResponseShapeTests(TestCase):
    def test_classification_summary_with_asymmetric_scores(self):
        a = _game("shape-game", name="Shape Game")
        _snapshot(
            a,
            unified_integer_challenge=[51, 31, 18],
            unified_integer_reward=[17, 29, 54],
        )

        r = _get()
        item = r.json()["results"][0]
        self.assertEqual(
            set(item.keys()),
            {
                "slug",
                "name",
                "source",
                "image_url",
                "library_capsule_url",
                "classification",
            },
        )
        self.assertEqual(item["classification"]["status"], "READY")
        self.assertEqual(
            item["classification"]["challenge"],
            {"micro": 51, "macro": 31, "mystiko": 18},
        )
        self.assertEqual(
            item["classification"]["reward"], {"micro": 17, "macro": 29, "mystiko": 54}
        )
        self.assertEqual(item["classification"]["confidence_level"], 85.5)
        self.assertEqual(item["classification"]["confidence_label"], "High")

    def test_unavailable_classification_is_null(self):
        _game("bare-game")
        r = _get()
        self.assertIsNone(r.json()["results"][0]["classification"])

    def test_manual_capsule_override_is_effective_capsule(self):
        _game(
            "override-game",
            library_capsule_url="https://cdn.example.com/steam-capsule.jpg",
            manual_capsule_url="https://example.com/manual-capsule.jpg",
        )
        r = _get()
        self.assertEqual(
            r.json()["results"][0]["library_capsule_url"],
            "https://example.com/manual-capsule.jpg",
        )


class CatalogueQueryCountTests(TestCase):
    def test_no_per_item_classification_query(self):
        for i in range(6):
            g = _game(f"qc-{i}")
            _snapshot(g, unified_integer_challenge=[51, 31, 18])

        with self.assertNumQueries(3):
            result = get_game_catalogue(CatalogueQuery(page=1, page_size=5))

        self.assertEqual(len(result.games), 5)
        self.assertTrue(all(g.classification is not None for g in result.games))
