"""
Manual-submission supersession of questionnaire records — SBGC-225.

When a manual score replaces a community row that originated from a
questionnaire, the row becomes ``MANUAL`` (clearing its questionnaire FK) and the
viewer's ``QuestionnaireClassification`` ledger is transitioned to
``SUPERSEDED_BY_MANUAL``.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from games.models import Game, SourceType

from classifications.models import (
    QuestionnaireClassification,
    UserGameScoreSubmission,
)
from classifications.services.questionnaire_precedence import (
    evaluate_manual_conflict,
    ingest_questionnaire_submission,
)
from classifications.services.submission_ingestion import ingest_score_submission

MANUAL = UserGameScoreSubmission.SubmissionSource.MANUAL
QUESTIONNAIRE = UserGameScoreSubmission.SubmissionSource.QUESTIONNAIRE


def _game(name: str = "Supersession Game") -> Game:
    return Game.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        source_type=SourceType.MANUAL,
        content_type="game",
        listing_status="published",
    )


def _questionnaire_payload() -> dict:
    return {
        "version": "v1.0.0",
        "dominant_aesthetic": "SENSORY",
        "secondary_aesthetic": None,
        "is_true_aesthetic": True,
        "answers": {"Q3": "Q3_huge_effect"},
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


def _manual_payload() -> dict:
    return {
        "challenge": {"micro": 50, "mystiko": 25, "macro": 25},
        "reward": {"micro": 40, "mystiko": 30, "macro": 30},
    }


class ManualSupersedesQuestionnaireTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="gamer", password="pw")
        self.game = _game()
        ingest_questionnaire_submission(self.user, self.game, _questionnaire_payload())
        promoted = UserGameScoreSubmission.objects.get(user=self.user, game=self.game)
        self.assertEqual(promoted.source, QUESTIONNAIRE)

    def test_in_place_manual_rewrite_converts_the_row_and_ledger(self):
        result = ingest_score_submission(
            user=self.user, game=self.game, payload=_manual_payload()
        )

        self.assertTrue(result.is_updated)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=self.user, game=self.game
            ).count(),
            1,
        )
        row = UserGameScoreSubmission.objects.get(user=self.user, game=self.game)
        self.assertEqual(row.source, MANUAL)
        self.assertIsNone(row.questionnaire_result)
        self.assertEqual(row.challenge_micro, 50)

        ledger = QuestionnaireClassification.objects.get(user=self.user, game=self.game)
        self.assertEqual(ledger.status, "SUPERSEDED_BY_MANUAL")

        # The manual row now drives the conflict evaluator.
        evaluation = evaluate_manual_conflict(self.user, self.game)
        self.assertTrue(evaluation.has_conflict)

    def test_branched_manual_supersedes_the_active_ledger(self):
        UserGameScoreSubmission.objects.filter(user=self.user, game=self.game).update(
            created_at=timezone.now() - timedelta(days=16)
        )

        result = ingest_score_submission(
            user=self.user, game=self.game, payload=_manual_payload()
        )

        self.assertTrue(result.is_created)
        rows = list(
            UserGameScoreSubmission.objects.filter(
                user=self.user, game=self.game
            ).order_by("-created_at", "-id")
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].source, MANUAL)
        self.assertEqual(rows[1].source, QUESTIONNAIRE)

        ledger = QuestionnaireClassification.objects.get(user=self.user, game=self.game)
        self.assertEqual(ledger.status, "SUPERSEDED_BY_MANUAL")

    def test_manual_without_a_questionnaire_creates_a_manual_row(self):
        other = User.objects.create_user(username="other", password="pw")
        ingest_score_submission(user=other, game=self.game, payload=_manual_payload())

        row = UserGameScoreSubmission.objects.get(user=other, game=self.game)
        self.assertEqual(row.source, MANUAL)
        self.assertFalse(
            QuestionnaireClassification.objects.filter(
                user=other, game=self.game
            ).exists()
        )
