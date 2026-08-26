"""
Rankings edge-case tests — SBGC-83.

Covers the schema on an empty database, deterministic tie-breaking across
pagination, extreme/split score distributions, Unified ``.5`` precision, public
listing exclusion, invalid/malicious query parameters, and out-of-bounds pages.
"""

from __future__ import annotations

from classifications.models import CalculationEpoch, ClassificationSnapshot
from django.test import Client, TestCase
from django.utils import timezone
from games.models import ContentType, Game, ListingStatus, SourceType

_app_id = 5_000_000


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


def _epoch() -> CalculationEpoch:
    epoch, _ = CalculationEpoch.objects.get_or_create(
        epoch_id="rankings-edge-epoch",
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
    )
    defaults.update(kwargs)
    return ClassificationSnapshot.objects.create(game=game, **defaults)


def _get(**params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/api/v1/rankings/?{qs}" if qs else "/api/v1/rankings/"
    return Client().get(url)


def _slugs(response) -> list[str]:
    return [item["slug"] for item in response.json()["results"]]


def _scores(response) -> list[int | float]:
    return [item["score"] for item in response.json()["results"]]


def _all_slugs(page_size: int, **params) -> list[str]:
    params.setdefault("page_size", page_size)
    slugs: list[str] = []
    page = 1
    while True:
        params["page"] = page
        body = _get(**params).json()
        results = body["results"]
        if not results:
            break
        slugs.extend(item["slug"] for item in results)
        if page >= body["total_pages"]:
            break
        page += 1
    return slugs


class EmptyDatabaseTests(TestCase):
    def test_empty_database_ranking_response(self):
        r = _get()
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["results"], [])
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 24)
        self.assertEqual(body["total_pages"], 0)
        self.assertEqual(
            set(body.keys()),
            {"count", "page", "page_size", "total_pages", "results"},
        )


class DeterministicTieBreakingTests(TestCase):
    def _seed(self) -> None:
        _game("g1", name="Zeta")
        _game("g2", name="Alpha")
        _game("g3", name="Alpha")
        _game("g4", name="Beta")
        _game("g5", name="Gamma")
        for slug in ("g1", "g2", "g3", "g4", "g5"):
            _snapshot(
                Game.objects.get(slug=slug),
                unified_integer_challenge=[60, 20, 20],
            )

    def test_identical_scores_break_by_name_then_id(self):
        self._seed()
        r = _get(profile="challenge", dimension="micro")
        self.assertEqual(_slugs(r), ["g2", "g3", "g4", "g5", "g1"])
        self.assertEqual(_scores(r), [60, 60, 60, 60, 60])

    def test_ties_are_stable_across_pagination(self):
        self._seed()
        self.assertEqual(
            _all_slugs(2, profile="challenge", dimension="micro"),
            ["g2", "g3", "g4", "g5", "g1"],
        )


class ExtremeScoreDistributionTests(TestCase):
    def test_extreme_and_split_scores_are_exact(self):
        extreme = _game("extreme")
        split = _game("split")
        _snapshot(extreme, unified_integer_challenge=[100, 0, 0])
        _snapshot(split, unified_integer_challenge=[34, 33, 33])

        micro = _get(profile="challenge", dimension="micro")
        self.assertEqual(_slugs(micro), ["extreme", "split"])
        self.assertEqual(_scores(micro), [100, 34])

        macro = _get(profile="challenge", dimension="macro")
        self.assertEqual(_slugs(macro), ["split", "extreme"])
        self.assertEqual(_scores(macro), [33, 0])

        mystiko = _get(profile="challenge", dimension="mystiko")
        self.assertEqual(_slugs(mystiko), ["split", "extreme"])
        self.assertEqual(_scores(mystiko), [33, 0])


class UnifiedHalfIntegerPrecisionTests(TestCase):
    def test_half_integer_scores_sort_and_serialize_exactly(self):
        a = _game("a")
        b = _game("b")
        c = _game("c")
        # Unified micro: a = (75+74)/2 = 74.5, b = (80+60)/2 = 70,
        # c = (70+65)/2 = 67.5 — distinct and orderable without truncation.
        _snapshot(
            a,
            unified_integer_challenge=[75, 10, 10],
            unified_integer_reward=[74, 10, 10],
        )
        _snapshot(
            b,
            unified_integer_challenge=[80, 10, 10],
            unified_integer_reward=[60, 10, 10],
        )
        _snapshot(
            c,
            unified_integer_challenge=[70, 10, 10],
            unified_integer_reward=[65, 10, 10],
        )

        r = _get(profile="unified", dimension="micro")
        self.assertEqual(_slugs(r), ["a", "b", "c"])
        self.assertEqual(_scores(r), [74.5, 70, 67.5])


class PublicListingExclusionTests(TestCase):
    def test_non_public_or_unclassified_games_are_excluded(self):
        ranked = _game("ranked")
        _snapshot(ranked)
        _game("draft", listing_status=ListingStatus.DRAFT)
        _game("archived", listing_status=ListingStatus.ARCHIVED)
        _game("dlc", content_type=ContentType.DLC)
        _game("software", content_type=ContentType.SOFTWARE)
        _game("unclassified")  # no snapshot at all
        in_review = _game("in-review")
        _snapshot(in_review, status="IN_REVIEW")

        r = _get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual({item["slug"] for item in r.json()["results"]}, {"ranked"})
        self.assertEqual(r.json()["count"], 1)


class InvalidParamTests(TestCase):
    def test_invalid_enums_rejected(self):
        self.assertEqual(_get(profile="malicious_sql").status_code, 422)
        self.assertEqual(_get(dimension="malicious_sql").status_code, 422)
        self.assertEqual(_get(direction="malicious_sql").status_code, 422)
        self.assertEqual(_get(dominant="malicious_sql").status_code, 422)

    def test_invalid_page_and_size_rejected(self):
        self.assertEqual(_get(page=0).status_code, 422)
        self.assertEqual(_get(page=-5).status_code, 422)
        self.assertEqual(_get(page="abc").status_code, 422)
        self.assertEqual(_get(page_size=0).status_code, 422)
        self.assertEqual(_get(page_size=-10).status_code, 422)
        self.assertEqual(_get(page_size=101).status_code, 422)


class OutOfBoundsPageTests(TestCase):
    def test_out_of_bounds_page_returns_empty_slice(self):
        for i in range(3):
            _snapshot(_game(f"g-{i}"), unified_integer_challenge=[100 - i, 10, 10])

        r = _get(profile="challenge", dimension="micro", page=99999)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["results"], [])
        self.assertEqual(body["count"], 3)
        self.assertEqual(body["page"], 99999)
        self.assertEqual(body["total_pages"], 1)
