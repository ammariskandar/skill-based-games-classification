"""
Database-level constraint tests — SBGC-177.

Every assertion inserts through the raw ORM (``objects.create``) *without*
``full_clean()``, so a passing test proves the database engine itself rejects
the row.  Violations must raise ``django.db.utils.IntegrityError``.

Each failing insert runs inside a nested ``transaction.atomic()`` so the outer
test transaction stays usable for further assertions.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from games.models import Game, SourceType

from classifications.models import (
    QuestionnaireClassification,
    QuestionnaireResult,
    UserGameScoreSubmission,
)


def _game(name: str = "Constraint Game") -> Game:
    return Game.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        source_type=SourceType.MANUAL,
        content_type="game",
        listing_status="published",
    )


def _result(user: User, game: Game, **overrides) -> QuestionnaireResult:
    defaults = {
        "user": user,
        "game": game,
        "dominant_aesthetic": "SENSORY",
        "secondary_aesthetic": None,
        "is_true_aesthetic": True,
        "answers": {"Q3": "Q3_huge_effect"},
        "q15_rating": 7,
        "raw_challenge_micro": 40,
        "raw_challenge_macro": 30,
        "raw_challenge_mystiko": 30,
        "raw_reward_micro": 35,
        "raw_reward_macro": 35,
        "raw_reward_mystiko": 30,
        "normalized_challenge_micro": 40,
        "normalized_challenge_macro": 30,
        "normalized_challenge_mystiko": 30,
        "normalized_reward_micro": 35,
        "normalized_reward_macro": 35,
        "normalized_reward_mystiko": 30,
        "adjusted_challenge_micro": 40,
        "adjusted_challenge_macro": 30,
        "adjusted_challenge_mystiko": 30,
        "adjusted_reward_micro": 35,
        "adjusted_reward_macro": 35,
        "adjusted_reward_mystiko": 30,
    }
    defaults.update(overrides)
    return QuestionnaireResult.objects.create(**defaults)


class _ConstraintTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gamer", password="pw")
        self.game = _game()

    def assert_result_rejected(self, **overrides) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                _result(self.user, self.game, **overrides)


class QuestionnaireResultConstraintTests(_ConstraintTestCase):
    def test_q15_rating_bounds_are_enforced(self):
        for rating in (0, 11, -1):
            with self.subTest(rating=rating):
                self.assert_result_rejected(q15_rating=rating)

    def test_q15_rating_valid_bounds_succeed(self):
        for rating in (1, 10):
            with self.subTest(rating=rating):
                result = _result(self.user, _game(f"Game {rating}"), q15_rating=rating)
                self.assertIsNotNone(result.pk)

    def test_dimension_upper_bounds_are_enforced(self):
        self.assert_result_rejected(normalized_challenge_micro=101)
        self.assert_result_rejected(adjusted_reward_mystiko=120)

    def test_negative_scores_are_rejected(self):
        # Sum-preserving but negative: only the database ``>= 0`` check (from
        # PositiveSmallIntegerField) can reject this row.
        self.assert_result_rejected(
            normalized_reward_micro=-5,
            normalized_reward_macro=55,
            normalized_reward_mystiko=50,
        )

    def test_normalized_challenge_sum_is_enforced(self):
        self.assert_result_rejected(
            normalized_challenge_micro=39,
            normalized_challenge_macro=30,
            normalized_challenge_mystiko=30,  # 99
        )
        self.assert_result_rejected(
            normalized_challenge_micro=41,
            normalized_challenge_macro=30,
            normalized_challenge_mystiko=30,  # 101
        )

    def test_adjusted_reward_sum_is_enforced(self):
        self.assert_result_rejected(
            adjusted_reward_micro=34,
            adjusted_reward_macro=35,
            adjusted_reward_mystiko=30,  # 99
        )
        self.assert_result_rejected(
            adjusted_reward_micro=36,
            adjusted_reward_macro=35,
            adjusted_reward_mystiko=30,  # 101
        )

    def test_valid_profile_persists(self):
        self.assertIsNotNone(_result(self.user, self.game).pk)


class QuestionnaireClassificationConstraintTests(_ConstraintTestCase):
    def test_user_game_is_unique(self):
        result = _result(self.user, self.game)
        QuestionnaireClassification.objects.create(
            user=self.user, game=self.game, latest_result=result
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QuestionnaireClassification.objects.create(
                    user=self.user, game=self.game, latest_result=result
                )

    def test_different_games_are_allowed(self):
        first = _result(self.user, self.game)
        other_game = _game("Other Game")
        second = _result(self.user, other_game)
        QuestionnaireClassification.objects.create(
            user=self.user, game=self.game, latest_result=first
        )
        classification = QuestionnaireClassification.objects.create(
            user=self.user, game=other_game, latest_result=second
        )
        self.assertIsNotNone(classification.pk)


class ForeignKeyActionTests(_ConstraintTestCase):
    def test_deleting_result_nullifies_score_submission_link(self):
        result = _result(self.user, self.game)
        submission = UserGameScoreSubmission.objects.create(
            user=self.user,
            game=self.game,
            source=UserGameScoreSubmission.SubmissionSource.QUESTIONNAIRE,
            questionnaire_result=result,
            challenge_micro=40,
            challenge_mystiko=30,
            challenge_macro=30,
            reward_micro=35,
            reward_mystiko=35,
            reward_macro=30,
        )
        result.delete()
        submission.refresh_from_db()
        self.assertIsNone(
            submission.questionnaire_result_id  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
        )
        self.assertTrue(
            UserGameScoreSubmission.objects.filter(pk=submission.pk).exists()
        )

    def test_deleting_result_cascades_classification(self):
        result = _result(self.user, self.game)
        classification = QuestionnaireClassification.objects.create(
            user=self.user, game=self.game, latest_result=result
        )
        result.delete()
        self.assertFalse(
            QuestionnaireClassification.objects.filter(pk=classification.pk).exists()
        )

    def test_deleting_game_cascades_results(self):
        result = _result(self.user, self.game)
        self.game.delete()
        self.assertFalse(QuestionnaireResult.objects.filter(pk=result.pk).exists())
