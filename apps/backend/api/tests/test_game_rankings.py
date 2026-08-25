"""
Game rankings endpoint tests — SBGC-81.

Exercises ``GET /api/v1/rankings/`` eligibility, Challenge/Reward/Unified score
semantics, direction, dominant-category filtering, deterministic ties,
pagination, effective Hero URL, and query-count boundedness.  All vectors are
asymmetric so index/order mistakes cannot pass; Unified is verified to be
(Challenge + Reward) / 2 including integer and .5 results.
"""

from __future__ import annotations

from classifications.models import CalculationEpoch, ClassificationSnapshot
from django.test import Client, TestCase
from django.utils import timezone
from games.models import ContentType, Game, ListingStatus, SourceType
from games.services.rankings import RankingQuery, get_rankings

_app_id = 4_000_000


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


def _epoch(epoch_id: str = "rankings-epoch") -> CalculationEpoch:
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


class RankingEligibilityTests(TestCase):
    def test_only_published_base_games_with_ready_snapshot_rank(self):
        steam = _game("steam-ranked")
        _snapshot(steam)
        manual = _manual("manual-ranked")
        _snapshot(manual)
        _game("draft", listing_status=ListingStatus.DRAFT)
        _game("archived", listing_status=ListingStatus.ARCHIVED)
        _game("dlc", content_type=ContentType.DLC)
        _game("no-snapshot")
        no_submissions = _game("no-submissions")
        _snapshot(
            no_submissions, status="NO_SUBMISSIONS", unified_integer_challenge=None
        )

        r = _get()
        self.assertEqual(r.status_code, 200)
        slugs = {item["slug"] for item in r.json()["results"]}
        self.assertEqual(slugs, {"steam-ranked", "manual-ranked"})
        self.assertEqual(r.json()["count"], 2)

    def test_missing_hero_still_ranks_with_empty_hero(self):
        g = _game("no-hero")  # no hero URLs at all
        _snapshot(g)
        r = _get()
        self.assertEqual(r.json()["results"][0]["hero_url"], "")

    def test_hero_uses_effective_hero_semantics(self):
        steam_hero = _game(
            "steam-hero", library_hero_url="https://cdn.example.com/steam-hero.jpg"
        )
        _snapshot(steam_hero)
        overridden = _game(
            "overridden",
            library_hero_url="https://cdn.example.com/steam-hero.jpg",
            manual_hero_url="https://example.com/manual-hero.jpg",
        )
        _snapshot(overridden)
        manual_hero = _manual(
            "manual-hero", manual_hero_url="https://example.com/manual-hero.jpg"
        )
        _snapshot(manual_hero)

        by_slug = {item["slug"]: item["hero_url"] for item in _get().json()["results"]}
        self.assertEqual(
            by_slug["steam-hero"], "https://cdn.example.com/steam-hero.jpg"
        )
        self.assertEqual(by_slug["overridden"], "https://example.com/manual-hero.jpg")
        self.assertEqual(by_slug["manual-hero"], "https://example.com/manual-hero.jpg")


class ChallengeRankingTests(TestCase):
    def test_micro_high_to_low(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        _snapshot(a, unified_integer_challenge=[90, 10, 10])
        _snapshot(b, unified_integer_challenge=[50, 40, 10])
        _snapshot(c, unified_integer_challenge=[10, 80, 10])
        r = _get(profile="challenge", dimension="micro")
        self.assertEqual(_slugs(r), ["a", "b", "c"])
        self.assertEqual(_scores(r), [90, 50, 10])

    def test_micro_low_to_high(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        _snapshot(a, unified_integer_challenge=[90, 10, 10])
        _snapshot(b, unified_integer_challenge=[50, 40, 10])
        _snapshot(c, unified_integer_challenge=[10, 80, 10])
        r = _get(profile="challenge", dimension="micro", direction="asc")
        self.assertEqual(_slugs(r), ["c", "b", "a"])
        self.assertEqual(_scores(r), [10, 50, 90])

    def test_selected_index_is_correct(self):
        # canonical order [micro, macro, mystiko]; the same game must expose the
        # correct element for each dimension, proving the index mapping.
        g = _game("shape", name="Shape")
        _snapshot(g, unified_integer_challenge=[11, 22, 33])
        self.assertEqual(
            _get(profile="challenge", dimension="micro").json()["results"][0]["score"],
            11,
        )
        self.assertEqual(
            _get(profile="challenge", dimension="macro").json()["results"][0]["score"],
            22,
        )
        self.assertEqual(
            _get(profile="challenge", dimension="mystiko").json()["results"][0][
                "score"
            ],
            33,
        )

    def test_macro_and_mystiko_desc(self):
        macro_top = _game("macro-top", name="Macro Top")
        mystiko_top = _game("mystiko-top", name="Mystiko Top")
        _snapshot(macro_top, unified_integer_challenge=[10, 90, 10])
        _snapshot(mystiko_top, unified_integer_challenge=[10, 10, 90])
        self.assertEqual(
            _slugs(_get(profile="challenge", dimension="macro")),
            ["macro-top", "mystiko-top"],
        )
        self.assertEqual(
            _slugs(_get(profile="challenge", dimension="mystiko")),
            ["mystiko-top", "macro-top"],
        )


class RewardRankingTests(TestCase):
    def test_reward_micro_desc_asc(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        # Asymmetric so Reward order differs from any Challenge order.
        _snapshot(a, unified_integer_reward=[10, 10, 90])
        _snapshot(b, unified_integer_reward=[50, 40, 10])
        _snapshot(c, unified_integer_reward=[90, 5, 5])
        self.assertEqual(
            _slugs(_get(profile="reward", dimension="micro")), ["c", "b", "a"]
        )
        self.assertEqual(
            _slugs(_get(profile="reward", dimension="micro", direction="asc")),
            ["a", "b", "c"],
        )

    def test_reward_mystiko_desc(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        _snapshot(a, unified_integer_reward=[10, 10, 90])
        _snapshot(b, unified_integer_reward=[10, 90, 10])
        self.assertEqual(
            _slugs(_get(profile="reward", dimension="mystiko")), ["a", "b"]
        )


class UnifiedRankingTests(TestCase):
    def test_unified_equals_average_and_differs_from_both(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        # challenge/reward micro: A=80/60→70, B=70/65→67.5, C=50/90→70.
        _snapshot(
            a,
            unified_integer_challenge=[80, 10, 10],
            unified_integer_reward=[60, 20, 20],
        )
        _snapshot(
            b,
            unified_integer_challenge=[70, 10, 20],
            unified_integer_reward=[65, 20, 15],
        )
        _snapshot(
            c, unified_integer_challenge=[50, 30, 20], unified_integer_reward=[90, 5, 5]
        )

        unified = _get(profile="unified", dimension="micro")
        self.assertEqual(_slugs(unified), ["a", "c", "b"])
        self.assertEqual(_scores(unified), [70, 70, 67.5])

        # Challenge-only and Reward-only order differently.
        self.assertEqual(
            _slugs(_get(profile="challenge", dimension="micro")), ["a", "b", "c"]
        )
        self.assertEqual(
            _slugs(_get(profile="reward", dimension="micro")), ["c", "b", "a"]
        )

    def test_unified_integer_result(self):
        g = _game("even", name="Even")
        _snapshot(
            g,
            unified_integer_challenge=[80, 10, 10],
            unified_integer_reward=[60, 20, 20],
        )
        self.assertEqual(
            _get(profile="unified", dimension="micro").json()["results"][0]["score"], 70
        )

    def test_unified_half_result(self):
        g = _game("odd", name="Odd")
        _snapshot(
            g,
            unified_integer_challenge=[80, 10, 10],
            unified_integer_reward=[55, 20, 25],
        )
        self.assertEqual(
            _get(profile="unified", dimension="micro").json()["results"][0]["score"],
            67.5,
        )


class TieBreakingTests(TestCase):
    def test_equal_score_ties_by_name_then_id(self):
        a = _game("a", name="Same")
        b = _game("b", name="Same")
        c = _game("c", name="Other")
        _snapshot(a, unified_integer_challenge=[50, 30, 20])
        _snapshot(b, unified_integer_challenge=[50, 25, 25])
        _snapshot(c, unified_integer_challenge=[80, 10, 10])
        # c highest, then a/b tie at 50 (same name) broken by id ASC.
        self.assertEqual(
            _slugs(_get(profile="challenge", dimension="micro")), ["c", "a", "b"]
        )

    def test_tied_pagination_stable(self):
        a = _game("a", name="Same")
        b = _game("b", name="Same")
        _snapshot(a, unified_integer_challenge=[50, 30, 20])
        _snapshot(b, unified_integer_challenge=[50, 25, 25])
        self.assertEqual(
            _all_slugs(1, profile="challenge", dimension="micro"), ["a", "b"]
        )


class DominantFilterTests(TestCase):
    def test_challenge_dominant(self):
        micro = _game("micro", name="Micro")
        macro = _game("macro", name="Macro")
        mystiko = _game("mystiko", name="Mystiko")
        _snapshot(micro, unified_integer_challenge=[70, 20, 10])
        _snapshot(macro, unified_integer_challenge=[20, 70, 10])
        _snapshot(mystiko, unified_integer_challenge=[20, 10, 70])
        self.assertEqual(_slugs(_get(profile="challenge", dominant="micro")), ["micro"])
        self.assertEqual(_slugs(_get(profile="challenge", dominant="macro")), ["macro"])
        self.assertEqual(
            _slugs(_get(profile="challenge", dominant="mystiko")), ["mystiko"]
        )

    def test_reward_dominant(self):
        micro = _game("micro", name="Micro")
        mystiko = _game("mystiko", name="Mystiko")
        _snapshot(micro, unified_integer_reward=[70, 20, 10])
        _snapshot(mystiko, unified_integer_reward=[20, 10, 70])
        self.assertEqual(_slugs(_get(profile="reward", dominant="micro")), ["micro"])
        self.assertEqual(
            _slugs(_get(profile="reward", dominant="mystiko")), ["mystiko"]
        )

    def test_unified_dominant(self):
        micro = _game("micro", name="Micro")
        mystiko = _game("mystiko", name="Mystiko")
        # Unified dominant = summed Challenge + Reward (strict-highest).
        _snapshot(
            micro,
            unified_integer_challenge=[70, 20, 10],
            unified_integer_reward=[60, 30, 10],
        )
        _snapshot(
            mystiko,
            unified_integer_challenge=[20, 10, 70],
            unified_integer_reward=[10, 20, 70],
        )
        self.assertEqual(_slugs(_get(profile="unified", dominant="micro")), ["micro"])
        self.assertEqual(
            _slugs(_get(profile="unified", dominant="mystiko")), ["mystiko"]
        )

    def test_top_score_tie_matches_no_dominant(self):
        tied = _game("tied", name="Tied")
        _snapshot(tied, unified_integer_challenge=[50, 50, 0])
        for category in ("micro", "macro", "mystiko"):
            self.assertEqual(
                _get(profile="challenge", dominant=category).json()["count"], 0
            )

    def test_unified_top_tie_matches_no_dominant(self):
        tied = _game("tied", name="Tied")
        # Unified micro = 80, macro = 80, mystiko = 10 → micro/macro tie.
        _snapshot(
            tied,
            unified_integer_challenge=[50, 50, 5],
            unified_integer_reward=[30, 30, 5],
        )
        for category in ("micro", "macro", "mystiko"):
            self.assertEqual(
                _get(profile="unified", dominant=category).json()["count"], 0
            )


class RankingPaginationTests(TestCase):
    def _make(self, n: int) -> None:
        for i in range(n):
            g = _game(f"g-{i}", name=f"Game {i:03d}")
            # Descending micro score so page order is non-trivial.
            _snapshot(g, unified_integer_challenge=[100 - i, 10, 10])

    def test_order_before_pagination(self):
        self._make(10)
        r = _get(profile="challenge", dimension="micro", page=2, page_size=3)
        self.assertEqual(r.json()["count"], 10)
        self.assertEqual(r.json()["total_pages"], 4)
        # Page 2 should hold ranks 4–6 in score-desc order (Game 003, 004, 005).
        self.assertEqual(_slugs(r), ["g-3", "g-4", "g-5"])

    def test_invalid_page_and_size_rejected(self):
        self.assertEqual(_get(page=0).status_code, 422)
        self.assertEqual(_get(page_size=0).status_code, 422)
        self.assertEqual(_get(page_size=101).status_code, 422)

    def test_invalid_enum_rejected(self):
        self.assertEqual(_get(profile="bogus").status_code, 422)
        self.assertEqual(_get(dimension="bogus").status_code, 422)
        self.assertEqual(_get(direction="bogus").status_code, 422)
        self.assertEqual(_get(dominant="bogus").status_code, 422)


class RankingQueryCountTests(TestCase):
    def test_ranking_stays_bounded(self):
        for i in range(6):
            g = _game(f"qc-{i}", name=f"QC {i}")
            _snapshot(g, unified_integer_challenge=[51, 31, 18])

        with self.assertNumQueries(2):
            result = get_rankings(
                RankingQuery(
                    profile="challenge", dimension="micro", page=1, page_size=5
                )
            )

        self.assertEqual(len(result.results), 5)
        self.assertTrue(all(isinstance(r.score, int) for r in result.results))


class RankingResponseShapeTests(TestCase):
    def test_item_shape(self):
        g = _game("shape", name="Shape")
        _snapshot(g, unified_integer_challenge=[51, 31, 18])
        r = _get(profile="challenge", dimension="micro")
        item = r.json()["results"][0]
        self.assertEqual(set(item.keys()), {"slug", "name", "hero_url", "score"})
        self.assertEqual(item["slug"], "shape")
        self.assertEqual(item["score"], 51)
