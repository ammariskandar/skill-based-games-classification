"""
Duplicate & multi-submission handling engine tests — SBGC-216.

Covers the temporal ingestion state machine (chained duplicate rejection,
rapid revision, 15-day in-place supersession, 15-day branching), editorial
routing isolation for staff/mod/superuser accounts, calculation-engine
parity for pooled community rows, the Django Ninja submit-score endpoint,
and the read-only Django Admin registry.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone
from games.models import Game, SourceType

from classifications.models import (
    EditorialClassification,
    EditorialGroupProfile,
    UserGameScoreSubmission,
)
from classifications.roles import EditorialRole
from classifications.services.calculations import freeze_population
from classifications.services.submission_ingestion import (
    CACHE_ATTEMPT_KEY,
    ingest_score_submission,
)
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
)

SUBMIT_URL = "/api/v1/classifications/games/{slug}/submit-score"


def _community_game(name: str = "Community Test Game") -> Game:
    return Game.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        source_type=SourceType.MANUAL,
        content_type="game",
        listing_status="published",
    )


def _payload(challenge=(40, 30, 30), reward=(35, 35, 30)) -> dict:
    """Build a payload with (micro, mystiko, macro) triples summing to 100."""
    return {
        "challenge": {
            "micro": challenge[0],
            "mystiko": challenge[1],
            "macro": challenge[2],
        },
        "reward": {
            "micro": reward[0],
            "mystiko": reward[1],
            "macro": reward[2],
        },
    }


def _moderator_user(username: str) -> User:
    user = User.objects.create_user(username=username, password="pw")
    group = Group.objects.create(name=f"{username}-mod-group")
    EditorialGroupProfile.objects.create(group=group, is_moderator=True)
    user.groups.add(group)
    return user


def _attempt_key(user: User, game: Game) -> str:
    return CACHE_ATTEMPT_KEY.format(user_id=user.pk, game_id=game.pk)


class SubmissionIngestionTests(TestCase):
    """Temporal rules for the community pipeline."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="gamer", password="pw")
        self.game = _community_game()
        self.key = _attempt_key(self.user, self.game)

    def _latest(self) -> UserGameScoreSubmission | None:
        return (
            UserGameScoreSubmission.objects.filter(user=self.user, game=self.game)
            .order_by("-created_at", "-id")
            .first()
        )

    def test_first_submission_creates_standalone_row(self):
        result = ingest_score_submission(
            user=self.user,
            game=self.game,
            payload=_payload(),
        )
        self.assertTrue(result.is_created)
        self.assertFalse(result.is_duplicate)
        self.assertFalse(result.is_updated)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=self.user, game=self.game
            ).count(),
            1,
        )

    def test_chained_duplicate_rejected_within_two_minutes(self):
        first = ingest_score_submission(
            user=self.user, game=self.game, payload=_payload()
        )
        second = ingest_score_submission(
            user=self.user, game=self.game, payload=_payload()
        )
        self.assertTrue(second.is_duplicate)
        self.assertFalse(second.is_created)
        self.assertFalse(second.is_updated)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.submission.pk, first.submission.pk)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=self.user, game=self.game
            ).count(),
            1,
        )

    def test_rapid_revision_overwrites_latest_in_place(self):
        first = ingest_score_submission(
            user=self.user, game=self.game, payload=_payload()
        )
        revised = _payload(challenge=(50, 20, 30), reward=(10, 40, 50))
        second = ingest_score_submission(
            user=self.user, game=self.game, payload=revised
        )
        self.assertTrue(second.is_updated)
        self.assertFalse(second.is_duplicate)
        self.assertFalse(second.is_created)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.submission.pk, first.submission.pk)
        row = self._latest()
        assert row is not None
        self.assertEqual(row.challenge_micro, 50)
        self.assertEqual(row.reward_macro, 50)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=self.user, game=self.game
            ).count(),
            1,
        )

    def test_window_update_within_15_days_preserves_created_at(self):
        # Day-1 record superseded on Day 5 and Day 14 stays one row, and the
        # 15-day anchor (created_at) never moves.
        original = ingest_score_submission(
            user=self.user, game=self.game, payload=_payload()
        ).submission
        anchor = timezone.now() - timedelta(days=14)
        UserGameScoreSubmission.objects.filter(pk=original.pk).update(created_at=anchor)
        # A fresh attempt >= 2 minutes later (cache aged out) reaches the
        # temporal-evaluation branch anchored on created_at.
        cache.delete(self.key)

        day_five = _payload(challenge=(45, 30, 25), reward=(40, 30, 30))
        result_five = ingest_score_submission(
            user=self.user, game=self.game, payload=day_five
        )
        self.assertTrue(result_five.is_updated)
        self.assertEqual(result_five.submission.pk, original.pk)
        cache.delete(self.key)

        day_fourteen = _payload(challenge=(60, 20, 20), reward=(50, 25, 25))
        result_fourteen = ingest_score_submission(
            user=self.user, game=self.game, payload=day_fourteen
        )
        self.assertTrue(result_fourteen.is_updated)
        self.assertEqual(result_fourteen.submission.pk, original.pk)

        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=self.user, game=self.game
            ).count(),
            1,
        )
        row = self._latest()
        assert row is not None
        self.assertEqual(row.challenge_micro, 60)
        self.assertAlmostEqual((anchor - row.created_at).total_seconds(), 0, places=1)
        self.assertGreaterEqual(row.updated_at, row.created_at)

    def test_15_day_branch_creates_new_row_and_isolates_prior(self):
        first = ingest_score_submission(
            user=self.user, game=self.game, payload=_payload()
        ).submission
        UserGameScoreSubmission.objects.filter(pk=first.pk).update(
            created_at=timezone.now() - timedelta(days=16)
        )
        cache.delete(self.key)

        # Day 16: >= 15 days since the first record -> branch to record #2.
        branched = ingest_score_submission(
            user=self.user, game=self.game, payload=_payload(challenge=(10, 40, 50))
        )
        self.assertTrue(branched.is_created)
        self.assertEqual(branched.status_code, 201)
        self.assertNotEqual(branched.submission.pk, first.pk)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=self.user, game=self.game
            ).count(),
            2,
        )

        # A follow-up within 15 days of record #2 supersedes record #2 in
        # place, leaving record #1 untouched.
        third = ingest_score_submission(
            user=self.user,
            game=self.game,
            payload=_payload(challenge=(70, 10, 20), reward=(20, 40, 40)),
        )
        self.assertTrue(third.is_updated)
        self.assertEqual(third.submission.pk, branched.submission.pk)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=self.user, game=self.game
            ).count(),
            2,
        )

        # Record #1 must be untouched; record #2 carries the latest values.
        rows = list(
            UserGameScoreSubmission.objects.filter(user=self.user, game=self.game)
            .order_by("created_at", "id")
            .values_list("id", "challenge_micro")
        )
        self.assertEqual(rows[0], (first.pk, 40))
        self.assertEqual(rows[1], (branched.submission.pk, 70))


class StaffRoutingTests(TestCase):
    """Superusers / moderators must never write community rows."""

    def setUp(self):
        cache.clear()
        self.game = _community_game()

    def test_superuser_routed_to_editorial_with_zero_community_rows(self):
        superuser = User.objects.create_superuser("root", password="pw")
        result = ingest_score_submission(
            user=superuser,
            game=self.game,
            payload=_payload(),
        )
        self.assertTrue(result.is_created)
        self.assertIsInstance(result.submission, EditorialClassification)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=superuser, game=self.game
            ).count(),
            0,
        )
        editorial = EditorialClassification.objects.get(
            game=self.game, submitted_by=superuser
        )
        self.assertEqual(editorial.submitted_role, EditorialRole.SUPERUSER)

        # A second, different submission supersedes the editorial record —
        # still zero community rows.
        second = ingest_score_submission(
            user=superuser,
            game=self.game,
            payload=_payload(challenge=(60, 25, 15)),
        )
        self.assertTrue(second.is_updated)
        self.assertFalse(second.is_created)
        self.assertEqual(
            EditorialClassification.objects.filter(
                game=self.game, submitted_by=superuser
            ).count(),
            1,
        )
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=superuser, game=self.game
            ).count(),
            0,
        )

    def test_moderator_routed_to_editorial(self):
        moderator = _moderator_user("moderator-1")
        result = ingest_score_submission(
            user=moderator,
            game=self.game,
            payload=_payload(),
        )
        self.assertTrue(result.is_created)
        editorial = EditorialClassification.objects.get(
            game=self.game, submitted_by=moderator
        )
        self.assertEqual(editorial.submitted_role, EditorialRole.MODERATOR)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=moderator, game=self.game
            ).count(),
            0,
        )

    def test_plain_community_user_never_routes_to_editorial(self):
        community = User.objects.create_user(username="plain", password="pw")
        result = ingest_score_submission(
            user=community,
            game=self.game,
            payload=_payload(),
        )
        self.assertTrue(result.is_created)
        self.assertIsInstance(result.submission, UserGameScoreSubmission)
        self.assertEqual(
            EditorialClassification.objects.filter(
                game=self.game, submitted_by=community
            ).count(),
            0,
        )
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(
                user=community, game=self.game
            ).count(),
            1,
        )


class FreezePopulationCommunityTests(TestCase):
    """Calculation-engine parity for pooled community submissions."""

    def setUp(self):
        cache.clear()
        self.game = _community_game()

    def test_editorial_and_community_rows_pool_together(self):
        superuser = User.objects.create_superuser("root", password="pw")
        create_submission(
            game=self.game,
            submitted_by=superuser,
            updated_by=superuser,
            challenge=ScoreDistribution(45, 30, 25),
            reward=ScoreDistribution(40, 30, 30),
        )
        community_a = User.objects.create_user(username="community-a", password="pw")
        community_b = User.objects.create_user(username="community-b", password="pw")
        UserGameScoreSubmission.objects.create(
            user=community_a,
            game=self.game,
            challenge_micro=40,
            challenge_mystiko=30,
            challenge_macro=30,
            reward_micro=50,
            reward_mystiko=20,
            reward_macro=30,
        )
        UserGameScoreSubmission.objects.create(
            user=community_b,
            game=self.game,
            challenge_micro=20,
            challenge_mystiko=40,
            challenge_macro=40,
            reward_micro=10,
            reward_mystiko=40,
            reward_macro=50,
        )

        population, received, invalid = freeze_population(self.game, timezone.now())
        self.assertEqual(received, 3)
        self.assertEqual(invalid, 0)
        self.assertEqual(population.raw_n, 3)
        counts = population.role_counts()
        self.assertEqual(counts[EditorialRole.SUPERUSER], 1)
        self.assertEqual(counts[EditorialRole.COMMUNITY], 2)

        identifiers = {record.identifier for record in population.submissions}
        community_rows = UserGameScoreSubmission.objects.filter(game=self.game)
        for row in community_rows:
            self.assertIn(f"community-{row.pk}", identifiers)

        community_record = next(
            record
            for record in population.submissions
            if record.identifier.startswith("community-")
        )
        self.assertEqual(community_record.challenge.micro, 40.0)
        self.assertEqual(community_record.challenge.macro, 30.0)
        self.assertEqual(community_record.challenge.mystiko, 30.0)
        self.assertEqual(community_record.reward.micro, 50.0)
        self.assertEqual(community_record.reward.macro, 30.0)
        self.assertEqual(community_record.reward.mystiko, 20.0)

    def test_community_hash_is_deterministic(self):
        community = User.objects.create_user(username="community", password="pw")
        row = UserGameScoreSubmission.objects.create(
            user=community,
            game=self.game,
            challenge_micro=40,
            challenge_mystiko=30,
            challenge_macro=30,
            reward_micro=35,
            reward_mystiko=35,
            reward_macro=30,
        )
        first, received, _ = freeze_population(self.game, timezone.now())
        second, _, _ = freeze_population(self.game, timezone.now())
        self.assertEqual(received, 1)
        self.assertEqual(first.population_hash, second.population_hash)
        self.assertIn(
            f"community-{row.pk}",
            {record.identifier for record in first.submissions},
        )

    def test_community_row_after_cutoff_belongs_to_next_epoch(self):
        community = User.objects.create_user(username="community", password="pw")
        UserGameScoreSubmission.objects.create(
            user=community,
            game=self.game,
            challenge_micro=40,
            challenge_mystiko=30,
            challenge_macro=30,
            reward_micro=35,
            reward_mystiko=35,
            reward_macro=30,
        )
        cutoff = timezone.now() - timedelta(seconds=1)
        population, received, _ = freeze_population(self.game, cutoff)
        self.assertEqual(received, 0)
        self.assertEqual(population.raw_n, 0)

        later_population, later_received, _ = freeze_population(
            self.game, timezone.now()
        )
        self.assertEqual(later_received, 1)
        self.assertEqual(later_population.raw_n, 1)


class SubmitScoreEndpointTests(TestCase):
    """HTTP contract for POST /api/v1/classifications/games/{slug}/submit-score."""

    def setUp(self):
        cache.clear()
        self.game = _community_game()
        self.url = SUBMIT_URL.format(slug=self.game.slug)

    def _post(self, url, body: dict):
        return self.client.post(
            url,
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_anonymous_request_is_rejected(self):
        response = self._post(self.url, _payload())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTHENTICATION_ERROR")

    def test_challenge_scores_must_sum_to_100(self):
        user = User.objects.create_user(username="gamer", password="pw")
        self.client.force_login(user)
        response = self._post(self.url, _payload(challenge=(50, 20, 20)))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["message"],
            "Challenge scores must sum to exactly 100.",
        )

    def test_reward_scores_must_sum_to_100(self):
        user = User.objects.create_user(username="gamer", password="pw")
        self.client.force_login(user)
        response = self._post(self.url, _payload(reward=(10, 40, 40)))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["message"],
            "Reward scores must sum to exactly 100.",
        )

    def test_unknown_game_returns_404(self):
        user = User.objects.create_user(username="gamer", password="pw")
        self.client.force_login(user)
        response = self._post(SUBMIT_URL.format(slug="does-not-exist"), _payload())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_community_submission_creates_row(self):
        user = User.objects.create_user(username="gamer", password="pw")
        self.client.force_login(user)
        response = self._post(self.url, _payload())
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["is_created"])
        self.assertFalse(body["is_duplicate"])
        self.assertFalse(body["is_updated"])
        self.assertEqual(body["game_slug"], self.game.slug)
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(user=user, game=self.game).count(),
            1,
        )

    def test_duplicate_replay_returns_200_idempotent(self):
        user = User.objects.create_user(username="gamer", password="pw")
        self.client.force_login(user)
        first = self._post(self.url, _payload())
        self.assertEqual(first.status_code, 201)

        second = self._post(self.url, _payload())
        self.assertEqual(second.status_code, 200)
        body = second.json()
        self.assertTrue(body["is_duplicate"])
        self.assertEqual(body["id"], first.json()["id"])
        self.assertEqual(
            UserGameScoreSubmission.objects.filter(user=user, game=self.game).count(),
            1,
        )


class UserGameScoreSubmissionAdminTests(TestCase):
    """Admin registry is globally visible but strictly read-only."""

    def setUp(self):
        cache.clear()
        self.superuser = User.objects.create_superuser("root", password="pw")
        self.staff = User.objects.create_user(
            username="staff", password="pw", is_staff=True
        )
        self.normal = User.objects.create_user(username="normal", password="pw")
        self.game = _community_game()
        self.obj = UserGameScoreSubmission.objects.create(
            user=self.normal,
            game=self.game,
            challenge_micro=40,
            challenge_mystiko=30,
            challenge_macro=30,
            reward_micro=35,
            reward_mystiko=35,
            reward_macro=30,
        )
        self.model_admin = admin.site._registry[UserGameScoreSubmission]

    def _request_for(self, user):
        request = RequestFactory().get("/")
        request.user = user  # type: ignore[reportAttributeAccessIssue]
        return request

    def test_readonly_fields_cover_every_model_field(self):
        field_names = {f.name for f in UserGameScoreSubmission._meta.fields}
        readonly = set(self.model_admin.readonly_fields)
        self.assertFalse(field_names - readonly)

    def test_no_mutation_permissions_for_any_user(self):
        for user in (self.superuser, self.staff, self.normal):
            request = self._request_for(user)
            self.assertFalse(
                self.model_admin.has_add_permission(request), user.username
            )
            self.assertFalse(
                self.model_admin.has_change_permission(request, self.obj),
                user.username,
            )
            self.assertFalse(
                self.model_admin.has_delete_permission(request, self.obj),
                user.username,
            )

    def test_view_available_to_staff_only(self):
        self.assertTrue(
            self.model_admin.has_view_permission(self._request_for(self.staff))
        )
        self.assertTrue(
            self.model_admin.has_view_permission(self._request_for(self.superuser))
        )
        self.assertFalse(
            self.model_admin.has_view_permission(self._request_for(self.normal))
        )

    def test_module_available_to_staff_only(self):
        self.assertTrue(
            self.model_admin.has_module_permission(self._request_for(self.staff))
        )
        self.assertFalse(
            self.model_admin.has_module_permission(self._request_for(self.normal))
        )

    def test_no_add_change_delete_buttons_in_changelist_context(self):
        # Django Admin hides actions whose permission methods return False.
        for user in (self.superuser, self.staff):
            request = self._request_for(user)
            perms = self.model_admin.get_model_perms(request)
            self.assertFalse(perms["add"], user.username)
            self.assertFalse(perms["change"], user.username)
            self.assertFalse(perms["delete"], user.username)


class CommunitySubmissionModelTests(TestCase):
    """Model-level sum validation for community score rows."""

    def setUp(self):
        self.user = User.objects.create_user(username="gamer", password="pw")
        self.game = _community_game()

    def test_clean_rejects_profiles_not_summing_to_100(self):
        row = UserGameScoreSubmission(
            user=self.user,
            game=self.game,
            challenge_micro=50,
            challenge_mystiko=20,
            challenge_macro=20,
            reward_micro=35,
            reward_mystiko=35,
            reward_macro=30,
        )
        with self.assertRaises(ValidationError):
            row.full_clean()
