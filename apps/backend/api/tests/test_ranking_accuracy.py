"""
Ranking accuracy tests — SBGC-84.

Exhaustively verifies profile × dimension × direction sorting (18
combinations), Unified half-integer arithmetic, multi-page partition integrity,
dominant-category consistency, and public-listing eligibility boundaries over a
deterministic seeded dataset.  Read-only: never modifies production ranking
code, never contacts Steam.
"""

from __future__ import annotations

from classifications.models import CalculationEpoch, ClassificationSnapshot
from django.test import Client, TestCase
from django.utils import timezone
from games.models import ContentType, Game, ListingStatus, SourceType

_app_id = 6_000_000

_PROFILES = ("unified", "challenge", "reward")
_DIMENSIONS = ("micro", "macro", "mystiko")
_DIRECTIONS = ("desc", "asc")


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
        epoch_id="ranking-accuracy-epoch",
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


def _all_items(page_size: int, **params) -> list[tuple[str, int | float]]:
    """Fetch every ranked item across pages as ``(slug, score)`` tuples."""
    params.setdefault("page_size", page_size)
    items: list[tuple[str, int | float]] = []
    page = 1
    while True:
        params["page"] = page
        body = _get(**params).json()
        results = body["results"]
        if not results:
            break
        items.extend((item["slug"], item["score"]) for item in results)
        if page >= body["total_pages"]:
            break
        page += 1
    return items


def _is_sorted(values: list[int | float], direction: str) -> bool:
    for i in range(len(values) - 1):
        if direction == "desc" and values[i] < values[i + 1]:
            return False
        if direction == "asc" and values[i] > values[i + 1]:
            return False
    return True


def _seed_dataset(count: int) -> list[Game]:
    """Seed *count* games with deterministic, varied Challenge/Reward vectors."""
    games: list[Game] = []
    for i in range(count):
        challenge = [(17 + i * 6) % 100, (41 + i * 3) % 100, (73 + i * 5) % 100]
        reward = [(29 + i * 4) % 100, (67 + i * 7) % 100, (11 + i * 9) % 100]
        g = _game(f"acc-{i}", name=f"Accuracy {i:02d}")
        _snapshot(
            g,
            unified_integer_challenge=challenge,
            unified_integer_reward=reward,
        )
        games.append(g)
    return games


class ProfileDimensionSortingTests(TestCase):
    """Matrix A — every profile × dimension × direction sorts monotonically."""

    def test_all_eighteen_combinations_are_sorted(self):
        count = 15
        _seed_dataset(count)

        for profile in _PROFILES:
            for dimension in _DIMENSIONS:
                for direction in _DIRECTIONS:
                    with self.subTest(
                        profile=profile,
                        dimension=dimension,
                        direction=direction,
                    ):
                        items = _all_items(
                            100,
                            profile=profile,
                            dimension=dimension,
                            direction=direction,
                        )
                        self.assertEqual(len(items), count)
                        scores = [score for _, score in items]
                        self.assertTrue(
                            _is_sorted(scores, direction),
                            f"{profile}/{dimension}/{direction} not sorted: {scores}",
                        )


class UnifiedArithmeticTests(TestCase):
    """Matrix B — Unified = (Challenge + Reward) / 2, half-integers preserved."""

    def _seed(self) -> None:
        a = _game("a")
        b = _game("b")
        c = _game("c")
        # Unified micro: a=74.5, b=70.0, c=67.5.
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

    def test_unified_micro_desc_orders_half_integers(self):
        self._seed()
        r = _get(profile="unified", dimension="micro", direction="desc")
        self.assertEqual(_slugs(r), ["a", "b", "c"])
        self.assertEqual(_scores(r), [74.5, 70, 67.5])

    def test_unified_micro_asc_orders_half_integers(self):
        self._seed()
        r = _get(profile="unified", dimension="micro", direction="asc")
        self.assertEqual(_slugs(r), ["c", "b", "a"])
        self.assertEqual(_scores(r), [67.5, 70, 74.5])

    def test_half_integer_is_serialized_as_float(self):
        self._seed()
        body = _get(profile="unified", dimension="micro").json()
        self.assertIsInstance(body["results"][0]["score"], float)
        self.assertEqual(body["results"][0]["score"], 74.5)


class MultiPagePartitionIntegrityTests(TestCase):
    """Matrix C — pagination is complete, disjoint, and cross-page ordered."""

    def test_pages_are_complete_disjoint_and_ordered(self):
        total = 25
        page_size = 5
        # Strictly descending Challenge Micro scores → 5 clean pages.
        for i in range(total):
            _snapshot(
                _game(f"page-{i}", name=f"Page Game {i:02d}"),
                unified_integer_challenge=[100 - i, 10, 10],
            )

        slugs: list[str] = []
        page_scores: list[list[int | float]] = []
        for page in range(1, 6):
            r = _get(
                profile="challenge",
                dimension="micro",
                direction="desc",
                page=page,
                page_size=page_size,
            )
            body = r.json()
            slugs.extend(item["slug"] for item in body["results"])
            page_scores.append([item["score"] for item in body["results"]])

        # Completeness + disjointness: every game appears exactly once.
        self.assertEqual(len(slugs), total)
        self.assertEqual(len(set(slugs)), total)

        # Cross-page ordering: last of page k >= first of page k+1 (desc).
        for k in range(4):
            self.assertGreaterEqual(page_scores[k][-1], page_scores[k + 1][0])


class DominantConsistencyTests(TestCase):
    """Matrix D — dominant filtering and deterministic secondary tie-breaks."""

    def test_dominant_filter_returns_correct_games_in_order(self):
        _snapshot(
            _game("micro-1", name="Micro One"), unified_integer_challenge=[80, 10, 10]
        )
        _snapshot(
            _game("micro-2", name="Micro Two"), unified_integer_challenge=[70, 20, 10]
        )
        _snapshot(_game("macro", name="Macro"), unified_integer_challenge=[20, 70, 10])
        _snapshot(
            _game("mystiko", name="Mystiko"), unified_integer_challenge=[20, 10, 70]
        )

        r = _get(profile="challenge", dominant="micro")
        self.assertEqual(_slugs(r), ["micro-1", "micro-2"])
        self.assertEqual(_scores(r), [80, 70])

    def test_identical_dominant_scores_break_ties_by_name_then_id(self):
        _snapshot(_game("a", name="Alpha"), unified_integer_challenge=[70, 20, 10])
        _snapshot(_game("b", name="Alpha"), unified_integer_challenge=[70, 25, 5])
        _snapshot(_game("c", name="Beta"), unified_integer_challenge=[70, 15, 15])

        r = _get(profile="challenge", dimension="micro", dominant="micro")
        self.assertEqual(_slugs(r), ["a", "b", "c"])


class EligibilityBoundaryTests(TestCase):
    """Matrix E — non-eligible games do not perturb metadata or ordering."""

    def test_non_eligible_games_do_not_alter_metadata_or_order(self):
        for i in range(5):
            _snapshot(
                _game(f"elig-{i}", name=f"Eligible {i}"),
                unified_integer_challenge=[100 - i, 10, 10],
            )
        _game("draft", listing_status=ListingStatus.DRAFT)
        _game("archived", listing_status=ListingStatus.ARCHIVED)
        _game("dlc", content_type=ContentType.DLC)
        _game("demo", content_type=ContentType.DEMO)
        _game("unclassified")
        _snapshot(_game("in-review"), status="IN_REVIEW")

        r = _get(profile="challenge", dimension="micro")
        body = r.json()
        self.assertEqual(body["count"], 5)
        self.assertEqual(body["total_pages"], 1)
        self.assertEqual(_slugs(r), ["elig-0", "elig-1", "elig-2", "elig-3", "elig-4"])

    def test_stale_ready_snapshot_still_ranks_with_accurate_score(self):
        g = _game("stale-ranked")
        snap = _snapshot(g, is_stale=True, unified_integer_challenge=[88, 6, 6])
        self.assertTrue(snap.is_current)
        self.assertTrue(snap.is_stale)

        r = _get(profile="challenge", dimension="micro")
        self.assertEqual(_slugs(r), ["stale-ranked"])
        self.assertEqual(_scores(r), [88])
