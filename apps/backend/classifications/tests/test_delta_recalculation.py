"""
Delta recalculation engine tests — SBGC-174.

Covers stale-game identification (both submission tables + no-snapshot and
no-submission cases), the email completion report, and the endpoint
permission gate (401 / 403 / 202).
"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from games.models import Game, SourceType

from classifications.calculations.constants import MASTER_VERSION
from classifications.models import (
    CalculationEpoch,
    ClassificationSnapshot,
    EditorialClassification,
    EditorialGroupProfile,
    UserGameScoreSubmission,
)
from classifications.services.delta_recalculation import (
    execute_delta_recalculation,
    find_stale_game_ids,
)
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
)

RECALC_URL = "/api/v1/classifications/recalculate-delta"


def _game(name: str) -> Game:
    return Game.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        source_type=SourceType.MANUAL,
        content_type="game",
        listing_status="published",
    )


def _snapshot(game: Game, calculated_at) -> ClassificationSnapshot:
    epoch = CalculationEpoch.objects.create(
        epoch_id=f"epoch-{game.pk}-{calculated_at:%Y%m%d%H%M%S%f}",
        cutoff_at=calculated_at,
        master_version=MASTER_VERSION,
        status=CalculationEpoch.Status.COMPLETED,
        completed_at=calculated_at,
    )
    return ClassificationSnapshot.objects.create(
        game=game,
        epoch=epoch,
        regime="provisional",
        status="NO_SUBMISSIONS",
        cutoff_at=calculated_at,
        calculated_at=calculated_at,
    )


def _community_sub(game: Game, user: User, updated_at) -> UserGameScoreSubmission:
    sub = UserGameScoreSubmission.objects.create(
        user=user,
        game=game,
        challenge_micro=40,
        challenge_mystiko=30,
        challenge_macro=30,
        reward_micro=35,
        reward_mystiko=35,
        reward_macro=30,
    )
    UserGameScoreSubmission.objects.filter(pk=sub.pk).update(updated_at=updated_at)
    return sub


def _editorial_sub(game: Game, user: User, updated_at) -> EditorialClassification:
    sub = create_submission(
        game=game,
        submitted_by=user,
        updated_by=user,
        challenge=ScoreDistribution(40, 30, 30),
        reward=ScoreDistribution(35, 35, 30),
    )
    EditorialClassification.objects.filter(pk=sub.pk).update(updated_at=updated_at)
    return sub


def _moderator_user(username: str) -> User:
    user = User.objects.create_user(username=username, password="pw")
    group = Group.objects.create(name=f"{username}-mod")
    EditorialGroupProfile.objects.create(group=group, is_moderator=True)
    user.groups.add(group)
    return user


class StaleGameIdentificationTests(TestCase):
    def test_stale_game_identification(self):
        user = User.objects.create_user(username="submitter", password="pw")
        superuser = User.objects.create_superuser("root", password="pw")
        now = timezone.now()
        past = now - timedelta(days=5)
        future = now + timedelta(days=5)

        # A: community submission mutated after the last calculation → stale.
        game_a = _game("Game A")
        _snapshot(game_a, now)
        _community_sub(game_a, user, future)

        # B: community submission mutated before the last calculation → fresh.
        game_b = _game("Game B")
        _snapshot(game_b, now)
        _community_sub(game_b, user, past)

        # C: has a submission but no completed calculation → stale.
        game_c = _game("Game C")
        _community_sub(game_c, user, now)

        # D: zero submissions → not stale.
        _game("Game D")

        # E: editorial submission mutated after the last calculation → stale.
        game_e = _game("Game E")
        _snapshot(game_e, now)
        _editorial_sub(game_e, superuser, future)

        stale = find_stale_game_ids()
        self.assertEqual(stale, sorted([game_a.pk, game_c.pk, game_e.pk]))
        self.assertNotIn(game_b.pk, stale)


class DeltaRecalculationReportTests(TestCase):
    def test_recalculation_email_dispatched(self):
        user = User.objects.create_user(username="submitter", password="pw")
        admin = User.objects.create_superuser(
            "admin", email="admin@example.com", password="pw"
        )
        game = _game("Stale Game")
        now = timezone.now()
        _community_sub(game, user, now + timedelta(days=1))

        with patch(
            "classifications.services.delta_recalculation.run_game_calculation"
        ) as engine:
            summary = execute_delta_recalculation(admin)

        self.assertEqual(summary.games_recalculated, [game.name])
        self.assertTrue(summary.total_games_checked >= 1)
        self.assertEqual(engine.call_count, 1)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("Score Delta Recalculation Complete", str(message.subject))
        self.assertEqual(message.to, ["admin@example.com"])
        self.assertIn(game.name, str(message.body))
        self.assertIn("admin", str(message.body))


class DeltaRecalculationPermissionTests(TestCase):
    def _post(self):
        return self.client.post(
            RECALC_URL,
            data=json.dumps({}),
            content_type="application/json",
        )

    @patch("classifications.api.dispatch_delta_recalculation")
    def test_unauthenticated_is_401(self, dispatch):
        response = self._post()
        self.assertEqual(response.status_code, 401)
        dispatch.assert_not_called()

    @patch("classifications.api.dispatch_delta_recalculation")
    def test_regular_user_is_403(self, dispatch):
        self.client.force_login(
            User.objects.create_user(username="plain", password="pw")
        )
        response = self._post()
        self.assertEqual(response.status_code, 403)
        dispatch.assert_not_called()

    @patch("classifications.api.dispatch_delta_recalculation")
    def test_moderator_is_202(self, dispatch):
        moderator = _moderator_user("moderator")
        self.client.force_login(moderator)
        response = self._post()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")
        dispatch.assert_called_once()

    @patch("classifications.api.dispatch_delta_recalculation")
    def test_superuser_is_202(self, dispatch):
        superuser = User.objects.create_superuser(
            "root", email="root@example.com", password="pw"
        )
        self.client.force_login(superuser)
        response = self._post()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["recipient_email"], "root@example.com")
        dispatch.assert_called_once()
