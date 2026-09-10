"""
Questionnaire model & database-integrity tests — SBGC-175.

Verifies the sum-to-100 CheckConstraints on normalized and adjusted profiles
and cascade deletion integrity.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from games.models import Game, SourceType

from classifications.models import (
    QuestionnaireClassification,
    QuestionnaireResult,
)


def _game(name: str = "Questionnaire Game") -> Game:
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
        "answers": {"Q3": "Q3_huge"},
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


class QuestionnaireResultConstraintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gamer", password="pw")
        self.game = _game()

    def test_valid_result_persists(self):
        result = _result(self.user, self.game)
        self.assertIsNotNone(result.pk)

    def test_normalized_challenge_sum_is_enforced(self):
        with self.assertRaises(IntegrityError):
            _result(
                self.user,
                self.game,
                normalized_challenge_micro=50,
                normalized_challenge_macro=30,
                normalized_challenge_mystiko=30,
            )

    def test_normalized_reward_sum_is_enforced(self):
        with self.assertRaises(IntegrityError):
            _result(
                self.user,
                self.game,
                normalized_reward_micro=40,
                normalized_reward_macro=20,
                normalized_reward_mystiko=30,
            )

    def test_adjusted_challenge_sum_is_enforced(self):
        with self.assertRaises(IntegrityError):
            _result(
                self.user,
                self.game,
                adjusted_challenge_micro=50,
                adjusted_challenge_macro=30,
                adjusted_challenge_mystiko=30,
            )

    def test_adjusted_reward_sum_is_enforced(self):
        with self.assertRaises(IntegrityError):
            _result(
                self.user,
                self.game,
                adjusted_reward_micro=40,
                adjusted_reward_macro=20,
                adjusted_reward_mystiko=30,
            )


class QuestionnaireCascadeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gamer", password="pw")
        self.game = _game()
        self.result = _result(self.user, self.game)
        self.classification = QuestionnaireClassification.objects.create(
            user=self.user,
            game=self.game,
            latest_result=self.result,
            status=QuestionnaireClassification.PrecedenceStatus.ACTIVE_IN_CALCULATION,
        )

    def test_deleting_the_game_cascades_cleanly(self):
        self.game.delete()
        self.assertFalse(QuestionnaireResult.objects.filter(pk=self.result.pk).exists())
        self.assertFalse(
            QuestionnaireClassification.objects.filter(
                pk=self.classification.pk
            ).exists()
        )

    def test_deleting_the_user_cascades_cleanly(self):
        self.user.delete()
        self.assertFalse(QuestionnaireResult.objects.filter(pk=self.result.pk).exists())
        self.assertFalse(
            QuestionnaireClassification.objects.filter(
                pk=self.classification.pk
            ).exists()
        )
