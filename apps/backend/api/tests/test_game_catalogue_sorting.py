"""
Game catalogue sorting/filtering tests — SBGC-79.

Exercises the primary sorts (name A–Z/Z–A, recently added, Challenge/Reward
Micro/Mystiko/Macro score), dominant-category filtering against the published
current READY snapshot, and the cover-last outer partition (before pagination)
across pages.  All vectors are asymmetric so index/order mistakes cannot pass.
"""

from __future__ import annotations

from datetime import timedelta

from classifications.models import CalculationEpoch, ClassificationSnapshot
from django.test import Client, TestCase
from django.utils import timezone
from games.models import ContentType, Game, ListingStatus, SourceType
from games.services.catalogue import CatalogueQuery, get_game_catalogue

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


def _epoch() -> CalculationEpoch:
    epoch, _ = CalculationEpoch.objects.get_or_create(
        epoch_id="catalogue-sort-epoch",
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
    url = f"/api/v1/games/?{qs}" if qs else "/api/v1/games/"
    return Client().get(url)


def _slugs(response) -> list[str]:
    return [item["slug"] for item in response.json()["results"]]


def _all_slugs(page_size: int, **params) -> list[str]:
    """Fetch every page and return the concatenated slug order."""
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


def _set_created(game: Game, when) -> None:
    Game.objects.filter(pk=game.pk).update(created_at=when)


class PrimarySortTests(TestCase):
    def test_name_asc_is_default(self):
        _game("beta", name="Beta")
        _game("alpha", name="Alpha")
        _game("gamma", name="Gamma")
        self.assertEqual(_slugs(_get()), ["alpha", "beta", "gamma"])

    def test_name_desc(self):
        _game("beta", name="Beta")
        _game("alpha", name="Alpha")
        _game("gamma", name="Gamma")
        self.assertEqual(_slugs(_get(sort="name_desc")), ["gamma", "beta", "alpha"])

    def test_name_asc_duplicate_names_stable_by_id(self):
        a = _game("dup-a", name="Same")
        b = _game("dup-b", name="Same")
        self.assertEqual(_slugs(_get()), [a.slug, b.slug])

    def test_recent_uses_created_at_desc_not_release_date(self):
        now = timezone.now()
        # release_date intentionally opposite to created_at to prove `recent`
        # keys off created_at (Game.created_at), never release_date.
        newest = _game("newest", name="Newest", release_date="2001-01-01")
        middle = _game("middle", name="Middle", release_date="2010-01-01")
        oldest = _game("oldest", name="Oldest", release_date="2020-01-01")
        _set_created(newest, now - timedelta(days=1))
        _set_created(middle, now - timedelta(days=2))
        _set_created(oldest, now - timedelta(days=3))

        self.assertEqual(_slugs(_get(sort="recent")), ["newest", "middle", "oldest"])

    def test_invalid_sort_rejected(self):
        self.assertEqual(_get(sort="bogus").status_code, 422)

    def test_invalid_profile_rejected(self):
        self.assertEqual(_get(sort="micro", profile="bogus").status_code, 422)


class SkillSortTests(TestCase):
    """Asymmetric vectors catch any index/order drift."""

    def test_challenge_micro_highest_first(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        _snapshot(a, unified_integer_challenge=[90, 5, 5])
        _snapshot(b, unified_integer_challenge=[50, 30, 20])
        _snapshot(c, unified_integer_challenge=[10, 80, 10])
        self.assertEqual(
            _slugs(_get(sort="micro", profile="challenge")), ["a", "b", "c"]
        )

    def test_challenge_macro_highest_first(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        _snapshot(a, unified_integer_challenge=[5, 90, 5])
        _snapshot(b, unified_integer_challenge=[30, 50, 20])
        _snapshot(c, unified_integer_challenge=[80, 10, 10])
        self.assertEqual(
            _slugs(_get(sort="macro", profile="challenge")), ["a", "b", "c"]
        )

    def test_challenge_mystiko_highest_first(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        _snapshot(a, unified_integer_challenge=[5, 5, 90])
        _snapshot(b, unified_integer_challenge=[20, 30, 50])
        _snapshot(c, unified_integer_challenge=[10, 80, 10])
        self.assertEqual(
            _slugs(_get(sort="mystiko", profile="challenge")), ["a", "b", "c"]
        )

    def test_reward_micro_highest_first(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        _snapshot(a, unified_integer_reward=[90, 5, 5])
        _snapshot(b, unified_integer_reward=[50, 30, 20])
        _snapshot(c, unified_integer_reward=[10, 80, 10])
        self.assertEqual(_slugs(_get(sort="micro", profile="reward")), ["a", "b", "c"])

    def test_reward_macro_highest_first(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        _snapshot(a, unified_integer_reward=[5, 90, 5])
        _snapshot(b, unified_integer_reward=[30, 50, 20])
        _snapshot(c, unified_integer_reward=[80, 10, 10])
        self.assertEqual(_slugs(_get(sort="macro", profile="reward")), ["a", "b", "c"])

    def test_reward_mystiko_highest_first(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        _snapshot(a, unified_integer_reward=[5, 5, 90])
        _snapshot(b, unified_integer_reward=[20, 30, 50])
        _snapshot(c, unified_integer_reward=[10, 80, 10])
        self.assertEqual(
            _slugs(_get(sort="mystiko", profile="reward")), ["a", "b", "c"]
        )

    def test_unclassified_and_non_ready_sort_after_scored(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        c = _game("c", name="C")
        _game("d", name="D")
        _snapshot(a, unified_integer_challenge=[90, 5, 5])
        _snapshot(b, unified_integer_challenge=[50, 30, 20])
        _snapshot(c, status="NO_SUBMISSIONS", unified_integer_challenge=None)
        # d has no snapshot at all.

        # Scored A/B first (highest→lowest), then C/D (no usable score) by name.
        self.assertEqual(
            _slugs(_get(sort="micro", profile="challenge")),
            ["a", "b", "c", "d"],
        )

    def test_skill_sort_ties_break_by_name_id(self):
        a = _game("a", name="A")
        b = _game("b", name="B")
        _snapshot(a, unified_integer_challenge=[50, 30, 20])
        _snapshot(b, unified_integer_challenge=[50, 25, 25])
        # Equal micro (50); name ASC breaks the tie.
        self.assertEqual(_slugs(_get(sort="micro", profile="challenge")), ["a", "b"])


class DominantFilterTests(TestCase):
    def test_challenge_micro_dominant(self):
        micro = _game("micro", name="Micro")
        macro = _game("macro", name="Macro")
        mystiko = _game("mystiko", name="Mystiko")
        _snapshot(micro, unified_integer_challenge=[70, 20, 10])
        _snapshot(macro, unified_integer_challenge=[20, 70, 10])
        _snapshot(mystiko, unified_integer_challenge=[20, 10, 70])
        self.assertEqual(_slugs(_get(dominant="micro", profile="challenge")), ["micro"])
        self.assertEqual(_slugs(_get(dominant="macro", profile="challenge")), ["macro"])
        self.assertEqual(
            _slugs(_get(dominant="mystiko", profile="challenge")), ["mystiko"]
        )

    def test_reward_dominant(self):
        micro = _game("micro", name="Micro")
        macro = _game("macro", name="Macro")
        mystiko = _game("mystiko", name="Mystiko")
        _snapshot(micro, unified_integer_reward=[70, 20, 10])
        _snapshot(macro, unified_integer_reward=[20, 70, 10])
        _snapshot(mystiko, unified_integer_reward=[20, 10, 70])
        self.assertEqual(_slugs(_get(dominant="micro", profile="reward")), ["micro"])
        self.assertEqual(
            _slugs(_get(dominant="mystiko", profile="reward")), ["mystiko"]
        )

    def test_top_score_tie_matches_no_dominant(self):
        tied = _game("tied", name="Tied")
        _snapshot(tied, unified_integer_challenge=[50, 50, 0])
        for category in ("micro", "macro", "mystiko"):
            self.assertEqual(
                _get(dominant=category, profile="challenge").json()["count"], 0
            )

    def test_unclassified_matches_no_dominant(self):
        _game("bare", name="Bare")
        self.assertEqual(_get(dominant="micro", profile="challenge").json()["count"], 0)

    def test_invalid_dominant_rejected(self):
        self.assertEqual(_get(dominant="bogus").status_code, 422)


class CompositionTests(TestCase):
    def test_q_source_classified_dominant_sort(self):
        a = _game("persona-4-golden", name="Persona 4 Golden")
        _snapshot(a, unified_integer_challenge=[70, 20, 10])
        b = _manual("persona-manual", name="Persona Manual")
        _snapshot(b, unified_integer_challenge=[90, 5, 5])
        c = _game("portal-2", name="Portal 2")
        _snapshot(c, unified_integer_challenge=[10, 80, 10])

        r = _get(
            q="persona",
            source="steam",
            classified="true",
            dominant="micro",
            profile="challenge",
            sort="micro",
        )
        self.assertEqual(_slugs(r), ["persona-4-golden"])

    def test_q_plus_skill_sort(self):
        # portal-2 has the highest Micro but must be excluded by `q`.
        a = _game("elden-ring-2", name="Elden Ring 2")
        _snapshot(a, unified_integer_challenge=[90, 5, 5])
        b = _game("elden-ring", name="ELDEN RING")
        _snapshot(b, unified_integer_challenge=[70, 20, 10])
        c = _game("portal-2", name="Portal 2")
        _snapshot(c, unified_integer_challenge=[99, 0, 1])

        r = _get(q="elden", sort="micro", profile="challenge")
        self.assertEqual(_slugs(r), ["elden-ring-2", "elden-ring"])

    def test_source_plus_skill_sort_plus_profile(self):
        a = _game("steam-high", name="Steam High")
        _snapshot(a, unified_integer_reward=[90, 5, 5])
        b = _manual("manual-higher", name="Manual Higher")
        _snapshot(b, unified_integer_reward=[95, 2, 3])
        c = _game("steam-low", name="Steam Low")
        _snapshot(c, unified_integer_reward=[10, 80, 10])

        r = _get(source="steam", sort="micro", profile="reward")
        self.assertEqual(_slugs(r), ["steam-high", "steam-low"])

    def test_classified_plus_dominant_plus_profile(self):
        micro = _game("micro", name="Micro")
        _snapshot(micro, unified_integer_reward=[70, 20, 10])
        macro = _game("macro", name="Macro")
        _snapshot(macro, unified_integer_reward=[20, 70, 10])
        _game("bare", name="Bare")

        r = _get(classified="true", dominant="micro", profile="reward")
        self.assertEqual(_slugs(r), ["micro"])

    def test_combination_paginates_correctly(self):
        for slug, vec in [
            ("p-0", [50, 30, 20]),
            ("p-1", [60, 20, 20]),
            ("p-2", [70, 20, 10]),
            ("p-3", [80, 10, 10]),
        ]:
            g = _game(slug, name=slug.replace("-", " ").title())
            _snapshot(g, unified_integer_challenge=vec)
        m = _manual("manual-extra", name="Manual Extra")
        _snapshot(m, unified_integer_challenge=[99, 0, 1])

        slugs = _all_slugs(
            page_size=2,
            source="steam",
            classified="true",
            dominant="micro",
            profile="challenge",
            sort="micro",
        )
        # Micro high→low: p-3 (80), p-2 (70), p-1 (60), p-0 (50); manual excluded.
        self.assertEqual(slugs, ["p-3", "p-2", "p-1", "p-0"])


class CatalogueQueryCountSortingTests(TestCase):
    def test_skill_sort_dominant_coverless_stay_bounded(self):
        for i in range(6):
            g = _game(f"qc-{i}", name=f"QC {i}")
            _snapshot(g, unified_integer_challenge=[51, 31, 18])

        with self.assertNumQueries(3):
            result = get_game_catalogue(
                CatalogueQuery(
                    page=1,
                    page_size=5,
                    sort="micro",
                    profile="challenge",
                    dominant="micro",
                    coverless_last=True,
                )
            )

        self.assertEqual(len(result.games), 5)


class CoverLastTests(TestCase):
    def test_covered_before_coverless_across_pages_name_asc(self):
        # Names A..E; A/C/E covered, B/D coverless.  Alphabetical covered group
        # A,C,E then coverless B,D — across a page boundary.
        _game("a", name="A", library_capsule_url="https://cdn.example.com/a.jpg")
        _game("b", name="B")
        _game("c", name="C", library_capsule_url="https://cdn.example.com/c.jpg")
        _game("d", name="D")
        _game("e", name="E", library_capsule_url="https://cdn.example.com/e.jpg")

        self.assertEqual(
            _all_slugs(page_size=2, sort="name_asc"),
            ["a", "c", "e", "b", "d"],
        )

    def test_covered_before_coverless_recent(self):
        now = timezone.now()
        a = _game("a", name="A", library_capsule_url="https://cdn.example.com/a.jpg")
        b = _game("b", name="B")
        c = _game("c", name="C", library_capsule_url="https://cdn.example.com/c.jpg")
        d = _game("d", name="D")
        e = _game("e", name="E", library_capsule_url="https://cdn.example.com/e.jpg")
        _set_created(a, now - timedelta(days=5))
        _set_created(b, now - timedelta(days=4))
        _set_created(c, now - timedelta(days=3))
        _set_created(d, now - timedelta(days=2))
        _set_created(e, now - timedelta(days=1))

        # recent = newest→oldest; covered first (e,c,a newest→oldest) then
        # coverless (d,b newest→oldest).
        self.assertEqual(
            _all_slugs(page_size=2, sort="recent"),
            ["e", "c", "a", "d", "b"],
        )

    def test_covered_before_coverless_skill_sort(self):
        a = _game("a", name="A", library_capsule_url="https://cdn.example.com/a.jpg")
        b = _game("b", name="B")
        c = _game("c", name="C", library_capsule_url="https://cdn.example.com/c.jpg")
        _snapshot(a, unified_integer_challenge=[90, 5, 5])
        _snapshot(b, unified_integer_challenge=[50, 30, 20])
        _snapshot(c, unified_integer_challenge=[10, 80, 10])

        # challenge micro high→low within each group: covered (a=90, c=10) then
        # coverless (b=50).
        self.assertEqual(
            _all_slugs(page_size=2, sort="micro", profile="challenge"),
            ["a", "c", "b"],
        )

    def test_covered_before_coverless_reward_skill_sort(self):
        a = _game("a", name="A", library_capsule_url="https://cdn.example.com/a.jpg")
        b = _game("b", name="B")
        c = _game("c", name="C", library_capsule_url="https://cdn.example.com/c.jpg")
        _snapshot(a, unified_integer_reward=[90, 5, 5])
        _snapshot(b, unified_integer_reward=[50, 30, 20])
        _snapshot(c, unified_integer_reward=[10, 80, 10])

        # reward micro high→low within each group: covered (a=90, c=10) then
        # coverless (b=50).
        self.assertEqual(
            _all_slugs(page_size=2, sort="micro", profile="reward"),
            ["a", "c", "b"],
        )

    def test_coverless_last_disabled_intermixes(self):
        _game("a", name="A", library_capsule_url="https://cdn.example.com/a.jpg")
        _game("b", name="B")
        _game("c", name="C", library_capsule_url="https://cdn.example.com/c.jpg")
        self.assertEqual(
            _slugs(_get(sort="name_asc", coverless_last="false")),
            ["a", "b", "c"],
        )

    def test_coverless_last_defaults_checked(self):
        _game("a", name="A", library_capsule_url="https://cdn.example.com/a.jpg")
        _game("b", name="B")
        self.assertEqual(_slugs(_get(sort="name_asc")), ["a", "b"])

    def test_manual_capsule_override_counts_as_cover(self):
        _game(
            "override",
            name="Override",
            library_capsule_url="https://cdn.example.com/steam.jpg",
            manual_capsule_url="https://example.com/manual.jpg",
        )
        _game("bare", name="Bare")
        self.assertEqual(_slugs(_get()), ["override", "bare"])

    def test_manual_game_with_capsule_counts_as_cover(self):
        _manual(
            "manual-cover",
            name="Manual Cover",
            manual_capsule_url="https://example.com/m.jpg",
        )
        _manual("manual-bare", name="Manual Bare")
        self.assertEqual(_slugs(_get()), ["manual-cover", "manual-bare"])

    def test_general_image_without_capsule_still_coverless(self):
        # A general Steam header image is NOT a Capsule: it must count as
        # coverless even though an image URL exists.
        _game(
            "image-only",
            name="Image Only",
            steam_image_url="https://cdn.example.com/header.jpg",
        )
        _game(
            "covered",
            name="Covered",
            library_capsule_url="https://cdn.example.com/c.jpg",
        )
        self.assertEqual(_slugs(_get()), ["covered", "image-only"])
