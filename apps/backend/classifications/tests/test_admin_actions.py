"""
Classification Admin recalculate action tests — SBGC-69 / SBGC-70.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from games.models import Game, SourceType

from classifications.models import ClassificationSnapshot
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
)


class RecalculateActionTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="recalc-admin", password="pw"
        )
        self.client.force_login(self.superuser)
        self.url = reverse("admin:classifications_editorialclassification_changelist")

    def _game(self, name):
        return Game.objects.create(
            source_type=SourceType.MANUAL,
            name=name,
            slug=name.lower().replace(" ", "-"),
        )

    def _submit(self, game, user=None):
        user = user or self.superuser
        return create_submission(
            game=game,
            submitted_by=user,
            updated_by=user,
            challenge=ScoreDistribution(micro=50, mystiko=30, macro=20),
            reward=ScoreDistribution(micro=20, mystiko=30, macro=50),
        )

    def _post_action(self, submission_pks):
        return self.client.post(
            self.url,
            {
                "action": "recalculate_classifications",
                "_selected_action": [str(pk) for pk in submission_pks],
                "index": "0",
            },
            follow=True,
        )

    def test_duplicate_submissions_for_same_game_calculate_once(self):
        game = self._game("Dedup Game")
        submission_a = self._submit(game)
        second = User.objects.create_superuser(username="second-author", password="pw")
        submission_b = self._submit(game, user=second)

        with mock.patch(
            "classifications.services.calculations.run_game_calculation",
            return_value=mock.MagicMock(),
        ) as patched:
            self._post_action([submission_a.pk, submission_b.pk])

        self.assertEqual(patched.call_count, 1)
        self.assertEqual(patched.call_args.kwargs["game"].pk, game.pk)

    def test_multiple_games_calculate_separately(self):
        game_a = self._game("Game A")
        game_b = self._game("Game B")
        submission_a = self._submit(game_a)
        submission_b = self._submit(game_b)

        with mock.patch(
            "classifications.services.calculations.run_game_calculation",
            return_value=mock.MagicMock(),
        ) as patched:
            self._post_action([submission_a.pk, submission_b.pk])

        self.assertEqual(patched.call_count, 2)

    def test_engine_failure_is_summarized(self):
        game = self._game("Failing Game")
        submission = self._submit(game)

        with mock.patch(
            "classifications.services.calculations.run_game_calculation",
            side_effect=RuntimeError("boom"),
        ):
            response = self._post_action([submission.pk])

        self.assertContains(response, "1 failed")
        self.assertNotContains(response, "boom")

    def test_legitimate_non_ready_outcome_is_summarized(self):
        # A single community submission (no privileged anchor) recalculates to
        # INSUFFICIENT_ANCHOR — a legitimate domain outcome, not a failure.
        game = self._game("Non-Ready Game")
        community = User.objects.create_user(username="community", password="pw")
        submission = self._submit(game, user=community)

        response = self._post_action([submission.pk])

        self.assertContains(response, "non-ready")
        self.assertNotContains(response, "failed")

    def test_real_recalculation_creates_ready_snapshot(self):
        game = self._game("Real Game")
        submission = self._submit(game)

        self._post_action([submission.pk])

        snapshot = (
            ClassificationSnapshot.objects.filter(game=game, is_current=True)
            .order_by("-calculated_at")
            .first()
        )
        assert snapshot is not None
        self.assertEqual(snapshot.status, "READY")

    def test_derived_values_not_edited_by_action(self):
        game = self._game("Derived Game")
        submission = self._submit(game)

        with mock.patch(
            "classifications.services.calculations.run_game_calculation",
            return_value=mock.MagicMock(),
        ):
            self._post_action([submission.pk])

        # The action must not mutate source submission provenance.
        submission.refresh_from_db()
        self.assertIsNotNone(submission.pk)
        self.assertEqual(submission.submitted_by.username, "recalc-admin")

    def test_delete_selected_absent(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "delete_selected")

    def test_recalculate_action_creates_log_entry(self):
        game = self._game("Audited Recalculate")
        submission = self._submit(game)

        with mock.patch(
            "classifications.services.calculations.run_game_calculation",
            return_value=mock.MagicMock(),
        ):
            self._post_action([submission.pk])

        entry = LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Game),
            object_id=str(game.pk),
            action_flag=CHANGE,
        ).first()
        assert entry is not None
        self.assertEqual(entry.user, self.superuser)
        self.assertIn("recalculated", entry.change_message)
