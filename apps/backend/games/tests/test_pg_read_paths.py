"""
PostgreSQL published read-path verification — SBGC-81 / SBGC-52.

The rankings and catalogue read paths annotate each Game with the current READY
snapshot's scores.  **Unified** is a presentation profile that *adds* the
Challenge and Reward expressions together, and the scores live in a
``JSONField`` vector, so the arithmetic only works when the extracted element is
an integer expression — PostgreSQL has no ``jsonb + jsonb`` operator.

The default suite runs on SQLite, whose JSON extraction and arithmetic happily
accept a bare element, so a ``jsonb`` regression is invisible there.  These
tests execute the arithmetic against a real PostgreSQL connection instead, and
are skipped whenever the vendor is not PostgreSQL.

Run with::

    POSTGRES_TEST_DATABASE_URL='postgresql://user:pass@host:5432/db' \\
      apps/backend/.venv/bin/python apps/backend/manage.py test \\
      games.tests.test_pg_read_paths \\
      --settings=config.settings.postgresql_test --noinput
"""

from __future__ import annotations

from classifications.calculations.results import READY
from classifications.models import CalculationEpoch, ClassificationSnapshot
from config.pg_testing import PostgreSQLTestCase
from django.utils import timezone

from games.models import ContentType, Game, ListingStatus, SourceType
from games.services.rankings import RankingQuery, get_rankings

EPOCH_ID = "pg-read-paths-epoch"
MODEL_VERSION = "STATISTICAL_MODEL_V1.0.0"

_app_id = 9_100_000


def _game(slug: str) -> Game:
    global _app_id
    _app_id += 1
    return Game.objects.create(
        name=slug.replace("-", " ").title(),
        slug=slug,
        source_type=SourceType.STEAM,
        external_id=str(_app_id),
        content_type=ContentType.GAME,
        listing_status=ListingStatus.PUBLISHED,
    )


def _epoch() -> CalculationEpoch:
    epoch, _created = CalculationEpoch.objects.get_or_create(
        epoch_id=EPOCH_ID,
        defaults={"cutoff_at": timezone.now(), "master_version": MODEL_VERSION},
    )
    return epoch


def _snapshot(game: Game, challenge: list[int], reward: list[int]) -> None:
    """Snapshot vector order is ``[micro, macro, mystiko]``."""
    ClassificationSnapshot.objects.create(
        game=game,
        epoch=_epoch(),
        regime="provisional",
        status=READY,
        cutoff_at=timezone.now(),
        is_current=True,
        is_stale=False,
        calculated_at=timezone.now(),
        master_version=MODEL_VERSION,
        methods_version="METHODS_V1",
        bhpcm_version="BHPCM_V1",
        confidence_final_version="CONFIDENCE_V1",
        unified_integer_challenge=challenge,
        unified_integer_reward=reward,
    )


def _rankings(**overrides):
    query = {"profile": "unified", "dimension": "micro", "page_size": 50}
    query.update(overrides)
    return get_rankings(RankingQuery(**query)).results


class UnifiedRankingArithmeticTests(PostgreSQLTestCase):
    """Unified = (Challenge + Reward) / 2, computed in SQL against PostgreSQL."""

    def test_unified_ranks_by_the_sum_of_both_profiles(self):
        strong = _game("pg-unified-strong")
        weak = _game("pg-unified-weak")
        # Sums: 80 + 60 = 140 -> 70.0, and 90 + 10 = 100 -> 50.0.
        _snapshot(strong, challenge=[80, 10, 10], reward=[60, 20, 20])
        _snapshot(weak, challenge=[90, 5, 5], reward=[10, 5, 85])

        results = _rankings()

        self.assertEqual([row.slug for row in results], [strong.slug, weak.slug])
        self.assertEqual([row.score for row in results], [70, 50])
        self.assertIsInstance(results[0].score, int)

    def test_unified_preserves_half_points(self):
        game = _game("pg-unified-half")
        # 51 + 52 = 103 -> 51.5.
        _snapshot(game, challenge=[51, 20, 29], reward=[52, 30, 18])

        results = _rankings()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].score, 51.5)
        self.assertIsInstance(results[0].score, float)

    def test_unified_dominant_filter_sums_both_profiles(self):
        split = _game("pg-unified-split")
        # Challenge alone reads macro-dominant, Reward alone reads
        # micro-dominant; only the sum is micro-dominant.
        _snapshot(split, challenge=[30, 40, 30], reward=[60, 10, 30])

        micro = {row.slug for row in _rankings(dominant="micro")}
        macro = {row.slug for row in _rankings(dominant="macro")}
        mystiko = {row.slug for row in _rankings(dominant="mystiko")}

        self.assertEqual(micro, {split.slug})
        self.assertEqual(macro, set())
        self.assertEqual(mystiko, set())

    def test_unclassified_game_is_excluded(self):
        ranked = _game("pg-unified-ranked")
        _snapshot(ranked, challenge=[70, 20, 10], reward=[70, 20, 10])
        _game("pg-unified-unclassified")

        results = _rankings()

        self.assertEqual([row.slug for row in results], [ranked.slug])


class SingleProfileRankingTypeTests(PostgreSQLTestCase):
    """A single-profile score is a numeric integer, not a JSON value."""

    def test_challenge_ranking_orders_numerically_and_returns_ints(self):
        high = _game("pg-challenge-high")
        low = _game("pg-challenge-low")
        _snapshot(high, challenge=[90, 5, 5], reward=[10, 5, 85])
        _snapshot(low, challenge=[10, 5, 85], reward=[10, 5, 85])

        results = _rankings(profile="challenge")

        self.assertEqual([row.slug for row in results], [high.slug, low.slug])
        self.assertEqual([row.score for row in results], [90, 10])
        for row in results:
            self.assertIsInstance(row.score, int)
