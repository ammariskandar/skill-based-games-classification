"""
Questionnaire session/submission API tests — SBGC-176.

Covers access control, session retrieval (conflict metadata + previous
result), server-side traversal/scoring/delta validation, the 409 conflict
gate, and staff editorial routing.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from games.models import Game, SourceType

from classifications.models import (
    EditorialClassification,
    QuestionnaireClassification,
    QuestionnaireResult,
    UserGameScoreSubmission,
)
from classifications.questionnaire.aesthetic_resolver import resolve_from_options
from classifications.questionnaire.registry.v1.assembler import assemble_questionnaire
from classifications.questionnaire.registry.v1.types import ProfileTarget
from classifications.questionnaire.scoring.engine import (
    compute_raw_profile,
    normalize_profile,
)

SESSION_URL = "/api/v1/questionnaire/{slug}/session"
SUBMIT_URL = "/api/v1/questionnaire/{slug}/submit"


def _game(name: str = "API Game", *, published: bool = True) -> Game:
    return Game.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        source_type=SourceType.MANUAL,
        content_type="game",
        listing_status="published" if published else "draft",
    )


def _valid_payload(
    q1: str = "OPT_S1", q2: str = "OPT_NONE", q15_rating: int = 7
) -> dict:
    resolution = resolve_from_options(q1, q2)
    assembled = assemble_questionnaire(resolution)
    nodes = (*assembled.part1_challenge_nodes, *assembled.part2_reward_nodes)
    answers = {node.id: node.options[0].id for node in nodes}
    raw_challenge = compute_raw_profile(
        answers, assembled.part1_challenge_nodes, ProfileTarget.CHALLENGE
    )
    raw_reward = compute_raw_profile(
        answers, assembled.part2_reward_nodes, ProfileTarget.REWARD
    )
    return {
        "version": "v1.0.0",
        "q1_option_id": q1,
        "q2_option_id": q2,
        "answers": answers,
        "q15_rating": q15_rating,
        "adjusted_challenge": normalize_profile(raw_challenge).to_dict(),
        "adjusted_reward": normalize_profile(raw_reward).to_dict(),
    }


def _manual_sub(user: User, game: Game, created_at) -> UserGameScoreSubmission:
    sub = UserGameScoreSubmission.objects.create(
        user=user,
        game=game,
        source=UserGameScoreSubmission.SubmissionSource.MANUAL,
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


class _ApiTestCase(TestCase):
    def _get_session(self, slug: str):
        return self.client.get(SESSION_URL.format(slug=slug))

    def _post_submit(self, slug: str, payload: dict):
        return self.client.post(
            SUBMIT_URL.format(slug=slug),
            data=json.dumps(payload),
            content_type="application/json",
        )


class AccessControlTests(_ApiTestCase):
    def test_session_requires_authentication(self):
        game = _game()
        response = self._get_session(game.slug)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTHENTICATION_ERROR")

    def test_submit_requires_authentication(self):
        game = _game()
        response = self._post_submit(game.slug, _valid_payload())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTHENTICATION_ERROR")

    def test_session_unknown_game_is_404(self):
        self.client.force_login(
            User.objects.create_user(username="gamer", password="pw")
        )
        response = self._get_session("does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_session_unpublished_game_is_404(self):
        self.client.force_login(
            User.objects.create_user(username="gamer", password="pw")
        )
        game = _game("Draft Game", published=False)
        response = self._get_session(game.slug)
        self.assertEqual(response.status_code, 404)


class SessionRetrievalTests(_ApiTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gamer", password="pw")
        self.game = _game()
        self.client.force_login(self.user)

    def test_no_submissions_reports_no_conflict(self):
        response = self._get_session(self.game.slug)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["game_slug"], self.game.slug)
        self.assertEqual(body["game_name"], self.game.name)
        self.assertIsNone(body["canonical_aesthetic"])
        self.assertFalse(body["precedence"]["has_conflict"])
        self.assertFalse(body["precedence"]["requires_user_choice"])
        self.assertIsNone(body["previous_result"])

    def test_recent_manual_requires_choice(self):
        _manual_sub(self.user, self.game, timezone.now() - timedelta(days=4))
        body = self._get_session(self.game.slug).json()
        self.assertTrue(body["precedence"]["has_conflict"])
        self.assertTrue(body["precedence"]["requires_user_choice"])
        self.assertEqual(body["precedence"]["age_days"], 4)

    def test_old_manual_does_not_require_choice(self):
        _manual_sub(self.user, self.game, timezone.now() - timedelta(days=15))
        body = self._get_session(self.game.slug).json()
        self.assertTrue(body["precedence"]["has_conflict"])
        self.assertFalse(body["precedence"]["requires_user_choice"])
        self.assertEqual(body["precedence"]["age_days"], 15)

    def test_previous_result_is_returned(self):
        submit = self._post_submit(self.game.slug, _valid_payload())
        self.assertIn(submit.status_code, (200, 201))
        body = self._get_session(self.game.slug).json()
        self.assertIsNotNone(body["previous_result"])
        previous = body["previous_result"]
        self.assertEqual(
            previous["result_id"], submit.json()["questionnaire_result_id"]
        )
        self.assertEqual(previous["status"], "ACTIVE_IN_CALCULATION")
        self.assertEqual(
            previous["adjusted_challenge"]["micro"]
            + previous["adjusted_challenge"]["macro"]
            + previous["adjusted_challenge"]["mystiko"],
            100,
        )


class SubmissionValidationTests(_ApiTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gamer", password="pw")
        self.game = _game()
        self.client.force_login(self.user)

    def test_invalid_aesthetic_options_are_rejected(self):
        payload = _valid_payload()
        payload["q1_option_id"] = "OPT_NONE"
        response = self._post_submit(self.game.slug, payload)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_unknown_question_node_is_rejected(self):
        payload = _valid_payload()
        payload["answers"]["Q99"] = "Q99_nope"
        response = self._post_submit(self.game.slug, payload)
        self.assertEqual(response.status_code, 422)

    def test_invalid_answer_option_is_rejected(self):
        payload = _valid_payload()
        payload["answers"]["Q3"] = "Q3_not_an_option"
        response = self._post_submit(self.game.slug, payload)
        self.assertEqual(response.status_code, 422)

    def test_adjusted_profile_must_sum_to_100(self):
        payload = _valid_payload()
        payload["adjusted_challenge"] = {"micro": 40, "macro": 30, "mystiko": 25}
        response = self._post_submit(self.game.slug, payload)
        self.assertEqual(response.status_code, 422)

    def test_q15_delta_bound_is_enforced(self):
        payload = _valid_payload(q15_rating=10)  # PERFECT: ±1
        adjusted = dict(payload["adjusted_challenge"])
        adjusted["micro"] += 5
        adjusted["macro"] -= 5
        payload["adjusted_challenge"] = adjusted
        response = self._post_submit(self.game.slug, payload)
        self.assertEqual(response.status_code, 422)

    def test_valid_submission_creates_active_row(self):
        response = self._post_submit(self.game.slug, _valid_payload())
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["classification_status"], "ACTIVE_IN_CALCULATION")
        self.assertTrue(body["is_active_in_calculation"])
        self.assertFalse(body["routed_to_editorial"])
        submission = UserGameScoreSubmission.objects.get(user=self.user, game=self.game)
        self.assertEqual(
            submission.source, UserGameScoreSubmission.SubmissionSource.QUESTIONNAIRE
        )


class ConflictStateFlowTests(_ApiTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gamer", password="pw")
        self.game = _game()
        self.client.force_login(self.user)
        self.manual = _manual_sub(
            self.user, self.game, timezone.now() - timedelta(days=3)
        )

    def test_missing_resolution_returns_409_without_writing(self):
        response = self._post_submit(self.game.slug, _valid_payload())
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["error"], "conflict_resolution_required")
        self.assertTrue(body["precedence"]["requires_user_choice"])
        self.assertEqual(body["precedence"]["age_days"], 3)
        self.assertEqual(QuestionnaireResult.objects.count(), 0)

    def test_keep_manual_archives_without_touching_submission(self):
        payload = _valid_payload()
        payload["conflict_resolution"] = "KEEP_MANUAL"
        response = self._post_submit(self.game.slug, payload)
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["classification_status"], "ARCHIVED_KEPT_MANUAL")
        self.assertFalse(body["is_active_in_calculation"])

        self.manual.refresh_from_db()
        self.assertEqual(
            self.manual.source, UserGameScoreSubmission.SubmissionSource.MANUAL
        )
        self.assertEqual(self.manual.challenge_micro, 50)
        self.assertEqual(QuestionnaireResult.objects.count(), 1)

    def test_overwrite_replaces_submission(self):
        payload = _valid_payload()
        payload["conflict_resolution"] = "OVERWRITE"
        response = self._post_submit(self.game.slug, payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["classification_status"], "ACTIVE_IN_CALCULATION")
        self.assertTrue(body["is_active_in_calculation"])

        self.manual.refresh_from_db()
        self.assertEqual(
            self.manual.source, UserGameScoreSubmission.SubmissionSource.QUESTIONNAIRE
        )
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=self.user, game=self.game
            ).count(),
            1,
        )


class StaffRoutingTests(_ApiTestCase):
    def test_staff_submission_routes_to_editorial(self):
        staff = User.objects.create_superuser("root", password="pw")
        game = _game()
        self.client.force_login(staff)

        response = self._post_submit(game.slug, _valid_payload())
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["routed_to_editorial"])
        self.assertEqual(body["classification_status"], "STAFF_EDITORIAL_ROUTED")

        self.assertEqual(
            UserGameScoreSubmission.objects.filter(user=staff, game=game).count(), 0
        )
        self.assertEqual(
            EditorialClassification.objects.filter(
                game=game, submitted_by=staff
            ).count(),
            1,
        )
        self.assertEqual(
            QuestionnaireClassification.objects.get(user=staff, game=game).status,
            "STAFF_EDITORIAL_ROUTED",
        )
