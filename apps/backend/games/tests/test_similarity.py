"""Similar-games math & engine tests — SBGC-227."""

from __future__ import annotations

from datetime import timedelta

from classifications.models import (
    CalculationEpoch,
    ClassificationSnapshot,
    QuestionnaireResult,
)
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from games.models import (
    Aesthetic,
    ContentType,
    Game,
    GameSimilarity,
    ListingStatus,
    SourceType,
)
from games.services.similarity import (
    AestheticLabel,
    ProfileVector,
    aesthetic_similarity,
    base_similarity,
    challenge_similarity,
    final_similarity,
    get_similar_games,
    quantize_confidence,
    reward_similarity,
    run_similarity_engine,
    weighted_confidence,
)

S = "SENSORY"
F = "FANTASY"
N = "NARRATIVE"
C = "CHALLENGE"

VECTOR = ProfileVector(micro=40, macro=30, mystiko=30)


class ProfileSimilarityTests(SimpleTestCase):
    def test_identical_profile_scores_full_weight(self):
        self.assertEqual(challenge_similarity(VECTOR, VECTOR), 50.0)
        self.assertEqual(reward_similarity(VECTOR, VECTOR), 40.0)

    def test_missing_profile_scores_zero(self):
        self.assertEqual(challenge_similarity(None, VECTOR), 0.0)
        self.assertEqual(reward_similarity(VECTOR, None), 0.0)

    def test_maximum_distance_scores_zero(self):
        a = ProfileVector(micro=100, macro=0, mystiko=0)
        b = ProfileVector(micro=0, macro=0, mystiko=100)
        # L1 = 200 → 50 × (1 − 1) = 0
        self.assertEqual(challenge_similarity(a, b), 0.0)

    def test_from_unified_reads_canonical_order(self):
        self.assertEqual(
            ProfileVector.from_unified([40, 30, 30]),
            ProfileVector(micro=40, macro=30, mystiko=30),
        )
        self.assertIsNone(ProfileVector.from_unified(None))


class AestheticCompatibilityTests(SimpleTestCase):
    def test_matrix(self):
        a = AestheticLabel(F, S)
        self.assertEqual(aesthetic_similarity(a, AestheticLabel(F, S)), 10)
        self.assertEqual(aesthetic_similarity(a, AestheticLabel(F, N)), 6)
        self.assertEqual(aesthetic_similarity(a, AestheticLabel(S, F)), 4)
        self.assertEqual(aesthetic_similarity(a, AestheticLabel(N, S)), 2)
        self.assertEqual(aesthetic_similarity(a, AestheticLabel(N, F)), 1)
        self.assertEqual(aesthetic_similarity(a, AestheticLabel(N, C)), 0)

    def test_unclassified_scores_zero(self):
        self.assertEqual(
            aesthetic_similarity(AestheticLabel(F, S), AestheticLabel(None, None)),
            0,
        )
        self.assertEqual(
            aesthetic_similarity(AestheticLabel(F, None), AestheticLabel(F, S)),
            0,
        )


class BaseSimilarityTests(SimpleTestCase):
    def test_identical_profiles_and_aesthetic_score_one_hundred(self):
        base = base_similarity(
            challenge_a=VECTOR,
            challenge_b=VECTOR,
            reward_a=VECTOR,
            reward_b=VECTOR,
            aesthetic_a=AestheticLabel(F, S),
            aesthetic_b=AestheticLabel(F, S),
        )
        self.assertEqual(base, 100.0)


class ConfidenceTests(SimpleTestCase):
    def test_asymmetric_weighting(self):
        self.assertEqual(weighted_confidence(100.0, 100.0), 100.0)
        self.assertAlmostEqual(weighted_confidence(100.0, 0.0), 30.0)

    def test_floor_quantization_to_ten_percent_steps(self):
        self.assertEqual(quantize_confidence(78.0), 0.70)
        self.assertEqual(quantize_confidence(74.0), 0.70)
        self.assertEqual(quantize_confidence(100.0), 1.0)
        self.assertEqual(quantize_confidence(59.0), 0.50)

    def test_minimum_floor_is_ten_percent(self):
        self.assertEqual(quantize_confidence(0.0), 0.10)
        self.assertEqual(quantize_confidence(9.0), 0.10)

    def test_spec_example_rounds_base_by_quantized_confidence(self):
        # S_base 85, C_final 74 → F_conf 0.70 → round(85 × 0.70) = 60.
        self.assertEqual(final_similarity(85.0, 74.0, 74.0), 60)


# ---------------------------------------------------------------------------
# DB engine & read service
# ---------------------------------------------------------------------------


def _make_game(
    slug: str,
    *,
    listing_status: str = ListingStatus.PUBLISHED,
    aesthetic: str | None = None,
) -> Game:
    return Game.objects.create(
        source_type=SourceType.MANUAL,
        name=slug.replace("-", " ").title(),
        slug=slug,
        content_type=ContentType.GAME,
        listing_status=listing_status,
        aesthetic=aesthetic,
    )


def _publish(
    game: Game,
    challenge: list[int],
    reward: list[int],
    *,
    confidence: float = 100.0,
    calculated_at=None,
) -> ClassificationSnapshot:
    epoch = CalculationEpoch.objects.create(
        epoch_id=f"epoch-{game.slug}",
        cutoff_at=timezone.now(),
        master_version="STATISTICAL_MODEL_V1.0.0",
    )
    kwargs = {}
    if calculated_at is not None:
        kwargs["calculated_at"] = calculated_at
    return ClassificationSnapshot.objects.create(
        game=game,
        epoch=epoch,
        regime="unified",
        status="READY",
        cutoff_at=timezone.now(),
        confidence_final=f"{confidence:.2f}",
        confidence_label="High",
        validated_count=10,
        unified_integer_challenge=challenge,
        unified_integer_reward=reward,
        is_current=True,
        **kwargs,
    )


def _vote(user, game: Game, primary: str, secondary: str) -> QuestionnaireResult:
    """One questionnaire aesthetic vote with valid 100-point profiles."""
    return QuestionnaireResult.objects.create(
        user=user,
        game=game,
        dominant_aesthetic=primary,
        secondary_aesthetic=secondary,
        answers={"Q1": "1_opt", "Q2": "2_opt"},
        q15_rating=8,
        raw_challenge_micro=34,
        raw_challenge_macro=33,
        raw_challenge_mystiko=33,
        raw_reward_micro=34,
        raw_reward_macro=33,
        raw_reward_mystiko=33,
        normalized_challenge_micro=34,
        normalized_challenge_macro=33,
        normalized_challenge_mystiko=33,
        normalized_reward_micro=34,
        normalized_reward_macro=33,
        normalized_reward_mystiko=33,
        adjusted_challenge_micro=34,
        adjusted_challenge_macro=33,
        adjusted_challenge_mystiko=33,
        adjusted_reward_micro=34,
        adjusted_reward_macro=33,
        adjusted_reward_mystiko=33,
    )


class SimilarityEngineTests(TestCase):
    def test_full_run_writes_every_directed_pair(self):
        user = User.objects.create_user(username="voter")
        alpha = _make_game("alpha")
        bravo = _make_game("bravo")
        for game in (alpha, bravo):
            _publish(game, [40, 30, 30], [30, 30, 40])
            _vote(user, game, Aesthetic.FANTASY, Aesthetic.SENSORY)

        report = run_similarity_engine(delta=False)

        self.assertEqual(report.games_considered, 2)
        self.assertEqual(report.pairs_written, 2)
        self.assertEqual(GameSimilarity.objects.count(), 2)
        # Identical profiles and identical canonical pairs score 100 both ways.
        self.assertEqual(
            GameSimilarity.objects.get(source_game=alpha, target_game=bravo).score, 100
        )
        self.assertEqual(
            GameSimilarity.objects.get(source_game=bravo, target_game=alpha).score, 100
        )

    def test_run_syncs_canonical_aesthetic_primary_from_votes(self):
        user = User.objects.create_user(username="aesthetic-voter")
        game = _make_game("gamma")
        _publish(game, [40, 30, 30], [30, 30, 40])
        _vote(user, game, Aesthetic.NARRATIVE, Aesthetic.FANTASY)

        run_similarity_engine(delta=False)

        game.refresh_from_db()
        self.assertEqual(game.aesthetic, Aesthetic.NARRATIVE)

    def test_delta_only_rewrites_pairs_touching_a_changed_game(self):
        for index in range(3):
            game = _make_game(f"g{index}")
            _publish(game, [40, 30, 30], [30, 30, 40])

        run_similarity_engine(delta=False)

        unchanged = run_similarity_engine(delta=True)
        self.assertEqual(unchanged.changed_games, 0)
        self.assertEqual(unchanged.pairs_written, 0)

        changed = Game.objects.get(slug="g1")
        ClassificationSnapshot.objects.filter(game=changed).update(
            calculated_at=timezone.now() + timedelta(days=1)
        )
        report = run_similarity_engine(delta=True)

        self.assertEqual(report.changed_games, 1)
        # Both directions to each of the two other games.
        self.assertEqual(report.pairs_written, 4)

    def test_unpublished_games_are_excluded(self):
        hidden = _make_game("hidden", listing_status=ListingStatus.DRAFT)
        _publish(hidden, [40, 30, 30], [30, 30, 40])
        visible = _make_game("visible")
        _publish(visible, [40, 30, 30], [30, 30, 40])

        report = run_similarity_engine(delta=False)

        self.assertEqual(report.games_considered, 1)
        self.assertEqual(GameSimilarity.objects.count(), 0)


class SimilarGameReadTests(TestCase):
    def test_get_similar_games_orders_and_filters_ineligible_targets(self):
        source = _make_game("source")
        high = _make_game("high")
        low = _make_game("low")
        hidden = _make_game("hidden-target", listing_status=ListingStatus.DRAFT)
        GameSimilarity.objects.create(source_game=source, target_game=high, score=80)
        GameSimilarity.objects.create(source_game=source, target_game=low, score=40)
        GameSimilarity.objects.create(source_game=source, target_game=hidden, score=95)

        results = get_similar_games(source, limit=6)

        self.assertEqual([item.slug for item in results], ["high", "low"])
        self.assertEqual(results[0].score, 80)

    def test_get_similar_games_respects_limit(self):
        source = _make_game("limit-source")
        for index in range(3):
            target = _make_game(f"limit-target-{index}")
            GameSimilarity.objects.create(
                source_game=source, target_game=target, score=50 + index
            )

        results = get_similar_games(source, limit=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].slug, "limit-target-2")


class SimilarGamesApiTests(TestCase):
    def test_endpoint_returns_ranked_results(self):
        source = _make_game("api-source")
        target = _make_game("api-target")
        GameSimilarity.objects.create(source_game=source, target_game=target, score=75)

        response = self.client.get("/api/v1/games/api-source/similar")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["slug"], "api-target")
        self.assertEqual(payload["results"][0]["similarity_score"], 75)

    def test_endpoint_404s_for_unknown_slug(self):
        response = self.client.get("/api/v1/games/does-not-exist/similar")
        self.assertEqual(response.status_code, 404)

    def test_limit_above_maximum_is_rejected(self):
        _make_game("api-limit")
        response = self.client.get("/api/v1/games/api-limit/similar?limit=99")
        self.assertEqual(response.status_code, 422)
