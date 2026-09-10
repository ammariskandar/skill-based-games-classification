"""
Questionnaire precedence engine tests — SBGC-175.

Covers direct promotion, >= 10-day auto-overwrite, < 10-day keep-manual and
overwrite resolutions, staff editorial isolation, and the conflict evaluator.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from games.models import Game, SourceType

from classifications.models import (
    EditorialClassification,
    EditorialGroupProfile,
    QuestionnaireClassification,
    QuestionnaireResult,
    UserGameScoreSubmission,
)
from classifications.services.questionnaire_precedence import (
    evaluate_manual_conflict,
    ingest_questionnaire_submission,
)

MANUAL = UserGameScoreSubmission.SubmissionSource.MANUAL
QUESTIONNAIRE = UserGameScoreSubmission.SubmissionSource.QUESTIONNAIRE


def _game(name: str = "Precedence Game") -> Game:
    return Game.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        source_type=SourceType.MANUAL,
        content_type="game",
        listing_status="published",
    )


def _payload(**overrides) -> dict:
    payload = {
        "version": "v1.0.0",
        "dominant_aesthetic": "SENSORY",
        "secondary_aesthetic": None,
        "is_true_aesthetic": True,
        "answers": {"Q3": "Q3_huge"},
        "q15_rating": 7,
        "raw": {
            "challenge": {"micro": 40, "macro": 30, "mystiko": 30},
            "reward": {"micro": 35, "macro": 35, "mystiko": 30},
        },
        "normalized": {
            "challenge": {"micro": 40, "macro": 30, "mystiko": 30},
            "reward": {"micro": 35, "macro": 35, "mystiko": 30},
        },
        "adjusted": {
            "challenge": {"micro": 40, "macro": 30, "mystiko": 30},
            "reward": {"micro": 35, "macro": 35, "mystiko": 30},
        },
    }
    payload.update(overrides)
    return payload


def _manual_sub(user: User, game: Game, created_at) -> UserGameScoreSubmission:
    sub = UserGameScoreSubmission.objects.create(
        user=user,
        game=game,
        source=MANUAL,
        challenge_micro=50,
        challenge_mystiko=25,
        challenge_macro=25,
        reward_micro=40,
        reward_mystiko=30,
        reward_macro=30,
    )
    UserGameScoreSubmission.objects.filter(pk=sub.pk).update(created_at=created_at)
    sub.refresh_from_db()
    return sub


def _moderator_user(username: str) -> User:
    user = User.objects.create_user(username=username, password="pw")
    group = Group.objects.create(name=f"{username}-mod")
    EditorialGroupProfile.objects.create(group=group, is_moderator=True)
    user.groups.add(group)
    return user


class ConflictEvaluationTests(TestCase):
    def test_no_manual_submission_has_no_conflict(self):
        user = User.objects.create_user(username="gamer", password="pw")
        game = _game()
        evaluation = evaluate_manual_conflict(user, game)
        self.assertFalse(evaluation.has_conflict)
        self.assertFalse(evaluation.requires_user_choice)

    def test_recent_manual_requires_user_choice(self):
        user = User.objects.create_user(username="gamer", password="pw")
        game = _game()
        _manual_sub(user, game, timezone.now() - timedelta(days=3))
        evaluation = evaluate_manual_conflict(user, game)
        self.assertTrue(evaluation.has_conflict)
        self.assertTrue(evaluation.requires_user_choice)
        self.assertEqual(evaluation.age_days, 3)

    def test_old_manual_does_not_require_choice(self):
        user = User.objects.create_user(username="gamer", password="pw")
        game = _game()
        _manual_sub(user, game, timezone.now() - timedelta(days=12))
        evaluation = evaluate_manual_conflict(user, game)
        self.assertTrue(evaluation.has_conflict)
        self.assertFalse(evaluation.requires_user_choice)


class PrecedenceStateMachineTests(TestCase):
    def test_direct_promotion(self):
        user = User.objects.create_user(username="gamer", password="pw")
        game = _game()
        outcome = ingest_questionnaire_submission(user, game, _payload())

        sub = UserGameScoreSubmission.objects.get(user=user, game=game)
        self.assertEqual(outcome.classification_status, "ACTIVE_IN_CALCULATION")
        self.assertTrue(outcome.is_active_in_calculation)
        self.assertEqual(sub.source, QUESTIONNAIRE)
        self.assertIsNotNone(sub.questionnaire_result)
        self.assertEqual(sub.challenge_micro, 40)
        self.assertEqual(
            QuestionnaireClassification.objects.get(user=user, game=game).status,
            "ACTIVE_IN_CALCULATION",
        )

    def test_ten_day_manual_is_auto_overwritten_in_place(self):
        user = User.objects.create_user(username="gamer", password="pw")
        game = _game()
        manual = _manual_sub(user, game, timezone.now() - timedelta(days=12))

        outcome = ingest_questionnaire_submission(user, game, _payload())

        self.assertEqual(outcome.classification_status, "ACTIVE_IN_CALCULATION")
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(user=user, game=game).count(), 1
        )
        manual.refresh_from_db()
        self.assertEqual(manual.source, QUESTIONNAIRE)
        self.assertEqual(manual.challenge_micro, 40)
        # created_at anchor is preserved on an in-place overwrite.
        self.assertLess(manual.created_at, timezone.now() - timedelta(days=11))

    def test_recent_manual_keep_manual_preserves_submission(self):
        user = User.objects.create_user(username="gamer", password="pw")
        game = _game()
        manual = _manual_sub(user, game, timezone.now() - timedelta(days=3))

        outcome = ingest_questionnaire_submission(
            user, game, _payload(), conflict_resolution="KEEP_MANUAL"
        )

        self.assertEqual(outcome.classification_status, "ARCHIVED_KEPT_MANUAL")
        self.assertFalse(outcome.is_active_in_calculation)
        self.assertEqual(
            QuestionnaireResult.objects.filter(user=user, game=game).count(), 1
        )
        manual.refresh_from_db()
        self.assertEqual(manual.source, MANUAL)
        self.assertEqual(manual.challenge_micro, 50)
        self.assertEqual(
            QuestionnaireClassification.objects.get(user=user, game=game).status,
            "ARCHIVED_KEPT_MANUAL",
        )

    def test_recent_manual_overwrite_replaces_submission(self):
        user = User.objects.create_user(username="gamer", password="pw")
        game = _game()
        manual = _manual_sub(user, game, timezone.now() - timedelta(days=3))

        outcome = ingest_questionnaire_submission(
            user, game, _payload(), conflict_resolution="OVERWRITE"
        )

        self.assertEqual(outcome.classification_status, "ACTIVE_IN_CALCULATION")
        manual.refresh_from_db()
        self.assertEqual(manual.source, QUESTIONNAIRE)
        self.assertEqual(manual.challenge_micro, 40)
        self.assertEqual(manual.challenge_mystiko, 30)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(user=user, game=game).count(), 1
        )

    def test_recent_manual_without_resolution_is_rejected(self):
        user = User.objects.create_user(username="gamer", password="pw")
        game = _game()
        _manual_sub(user, game, timezone.now() - timedelta(days=3))
        with self.assertRaises(ValueError):
            ingest_questionnaire_submission(user, game, _payload())

    def test_superuser_routes_to_editorial_without_community_rows(self):
        superuser = User.objects.create_superuser("root", password="pw")
        game = _game()
        outcome = ingest_questionnaire_submission(superuser, game, _payload())

        self.assertTrue(outcome.routed_to_editorial)
        self.assertEqual(outcome.classification_status, "STAFF_EDITORIAL_ROUTED")
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(user=superuser, game=game).count(),
            0,
        )
        self.assertTrue(
            EditorialClassification.objects.filter(
                game=game, submitted_by=superuser
            ).exists()
        )

    def test_moderator_routes_to_editorial_without_community_rows(self):
        moderator = _moderator_user("moderator")
        game = _game()
        outcome = ingest_questionnaire_submission(moderator, game, _payload())

        self.assertTrue(outcome.routed_to_editorial)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(user=moderator, game=game).count(),
            0,
        )
        self.assertTrue(
            EditorialClassification.objects.filter(
                game=game, submitted_by=moderator
            ).exists()
        )
