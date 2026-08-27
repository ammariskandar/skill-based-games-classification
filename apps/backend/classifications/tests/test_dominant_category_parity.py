"""
Dominant-category parity tests — SBGC-199.

Proves the pure-Python engine (``dominant_skill_category``) and the SQL ORM
expression (``published_dominant_category``) agree on strict-dominance results
for every valid distribution, and that catalogue/rankings dominant filters
return identical game sets.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from games.models import ContentType, Game, ListingStatus, SourceType
from games.services.catalogue import CatalogueQuery, get_game_catalogue
from games.services.rankings import RankingQuery, get_rankings

from classifications.calculations.results import READY
from classifications.models import CalculationEpoch, ClassificationSnapshot
from classifications.services.published import (
    published_dominant_category,
    published_score,
)
from classifications.skills import SkillCategory, dominant_skill_category

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# (micro, mystiko, macro, expected_dominant) — every triple totals exactly 100.
_VALID_TRUTH_TABLE: list[tuple[int, int, int, str | None]] = [
    (60, 20, 20, SkillCategory.MICRO),
    (20, 60, 20, SkillCategory.MYSTIKO),
    (20, 20, 60, SkillCategory.MACRO),
    (45, 45, 10, None),  # micro/mystiko tie
    (45, 10, 45, None),  # micro/macro tie
    (10, 45, 45, None),  # mystiko/macro tie
    (34, 33, 33, SkillCategory.MICRO),
    (100, 0, 0, SkillCategory.MICRO),
]

_app_id = 8_000_000


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


def _epoch(epoch_id: str = "dominance-parity-epoch") -> CalculationEpoch:
    epoch, _ = CalculationEpoch.objects.get_or_create(
        epoch_id=epoch_id,
        defaults={
            "cutoff_at": timezone.now(),
            "master_version": "STATISTICAL_MODEL_V1.0.0",
        },
    )
    return epoch


def _snapshot(
    game: Game,
    *,
    challenge: list[int] | None = None,
    reward: list[int] | None = None,
) -> ClassificationSnapshot:
    return ClassificationSnapshot.objects.create(
        game=game,
        epoch=_epoch(),
        regime="provisional",
        status=READY,
        cutoff_at=timezone.now(),
        is_current=True,
        is_stale=False,
        calculated_at=timezone.now(),
        master_version="STATISTICAL_MODEL_V1.0.0",
        methods_version="METHODS_V1",
        bhpcm_version="BHPCM_V1",
        confidence_final_version="CONFIDENCE_V1",
        unified_integer_challenge=challenge,
        unified_integer_reward=reward,
    )


def _canonical(micro: int, mystiko: int, macro: int) -> list[int]:
    """Snapshot array order is ``[micro, macro, mystiko]``."""
    return [micro, macro, mystiko]


def _annotated(game: Game, profile: str = "challenge") -> Game:
    """The Game annotated with ``_cat_*`` scores and ``_dominant``."""
    return (
        Game.objects.filter(pk=game.pk)
        .annotate(
            _cat_micro=published_score(profile, SkillCategory.MICRO),
            _cat_macro=published_score(profile, SkillCategory.MACRO),
            _cat_mystiko=published_score(profile, SkillCategory.MYSTIKO),
        )
        .annotate(_dominant=published_dominant_category())
        .get()
    )


# ---------------------------------------------------------------------------
# Pure Python engine
# ---------------------------------------------------------------------------


class DominantSkillCategoryPythonTests(TestCase):
    def test_valid_truth_table(self):
        for micro, mystiko, macro, expected in _VALID_TRUTH_TABLE:
            with self.subTest(micro=micro, mystiko=mystiko, macro=macro):
                self.assertEqual(
                    dominant_skill_category(
                        micro_score=micro,
                        mystiko_score=mystiko,
                        macro_score=macro,
                    ),
                    expected,
                )

    def test_invalid_distributions_rejected(self):
        # 0/0/0 and 33/33/33 do not total 100 — the validator must reject them.
        for micro, mystiko, macro in ((0, 0, 0), (33, 33, 33)):
            with self.subTest(micro=micro, mystiko=mystiko, macro=macro):
                with self.assertRaises(ValidationError):
                    dominant_skill_category(
                        micro_score=micro,
                        mystiko_score=mystiko,
                        macro_score=macro,
                    )


# ---------------------------------------------------------------------------
# SQL expression parity
# ---------------------------------------------------------------------------


class DominantCategorySqlParityTests(TestCase):
    def test_sql_matches_python_truth_table(self):
        for micro, mystiko, macro, expected in _VALID_TRUTH_TABLE:
            with self.subTest(micro=micro, mystiko=mystiko, macro=macro):
                game = _game(f"sql-{micro}-{mystiko}-{macro}")
                _snapshot(game, challenge=_canonical(micro, mystiko, macro))
                self.assertEqual(_annotated(game)._dominant, expected)  # pyright: ignore[reportAttributeAccessIssue]

    def test_sql_reward_profile_parity(self):
        game = _game("sql-reward")
        # reward micro=80, macro=10, mystiko=10 → micro is strictly dominant.
        _snapshot(game, reward=[80, 10, 10])
        annotated = _annotated(game, profile="reward")
        self.assertEqual(
            annotated._dominant,  # pyright: ignore[reportAttributeAccessIssue]
            SkillCategory.MICRO,
        )

    def test_sql_zero_vector_returns_none(self):
        game = _game("sql-zero")
        _snapshot(game, challenge=[0, 0, 0])
        self.assertIsNone(_annotated(game)._dominant)  # pyright: ignore[reportAttributeAccessIssue]

    def test_sql_three_way_tie_returns_none(self):
        game = _game("sql-tie")
        _snapshot(game, challenge=[33, 33, 33])
        self.assertIsNone(_annotated(game)._dominant)  # pyright: ignore[reportAttributeAccessIssue]

    def test_sql_missing_snapshot_returns_none(self):
        game = _game("sql-missing")
        self.assertIsNone(_annotated(game)._dominant)  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# Catalogue / rankings integration
# ---------------------------------------------------------------------------


class DominantCategoryIntegrationTests(TestCase):
    def setUp(self):
        self.micro = _game("int-micro")
        self.macro = _game("int-macro")
        self.mystiko = _game("int-mystiko")
        self.tied = _game("int-tied")
        self.missing = _game("int-missing")  # no snapshot

        _snapshot(self.micro, challenge=[70, 20, 10], reward=[60, 30, 10])
        _snapshot(self.macro, challenge=[20, 70, 10], reward=[10, 70, 20])
        _snapshot(self.mystiko, challenge=[20, 10, 70], reward=[10, 20, 70])
        _snapshot(self.tied, challenge=[50, 50, 0], reward=[50, 50, 0])

    def test_catalogue_and_rankings_agree_on_challenge_dominant(self):
        expected = {
            SkillCategory.MICRO: {self.micro.slug},
            SkillCategory.MACRO: {self.macro.slug},
            SkillCategory.MYSTIKO: {self.mystiko.slug},
        }
        for category, slugs in expected.items():
            with self.subTest(category=category):
                cat_slugs = {
                    g.slug
                    for g in get_game_catalogue(
                        CatalogueQuery(
                            profile="challenge", dominant=category, page_size=100
                        )
                    ).games
                }
                rank_slugs = {
                    r.slug
                    for r in get_rankings(
                        RankingQuery(
                            profile="challenge", dominant=category, page_size=100
                        )
                    ).results
                }
                self.assertEqual(cat_slugs, slugs)
                self.assertEqual(rank_slugs, slugs)

    def test_catalogue_and_rankings_agree_on_reward_dominant(self):
        # Reward micro: micro=60 vs others 30/10 → micro dominant only.
        cat_slugs = {
            g.slug
            for g in get_game_catalogue(
                CatalogueQuery(profile="reward", dominant="micro", page_size=100)
            ).games
        }
        rank_slugs = {
            r.slug
            for r in get_rankings(
                RankingQuery(profile="reward", dominant="micro", page_size=100)
            ).results
        }
        self.assertEqual(cat_slugs, {self.micro.slug})
        self.assertEqual(rank_slugs, {self.micro.slug})

    def test_tied_and_missing_games_are_never_dominant(self):
        for category in SkillCategory.values:
            with self.subTest(category=category):
                cat_slugs = {
                    g.slug
                    for g in get_game_catalogue(
                        CatalogueQuery(
                            profile="challenge", dominant=category, page_size=100
                        )
                    ).games
                }
                self.assertNotIn(self.tied.slug, cat_slugs)
                self.assertNotIn(self.missing.slug, cat_slugs)
