"""
Editorial classification submission + role tests — SBGC-63.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from games.models import Game, SourceType

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    EditorialGroupProfile,
    RewardProfile,
)
from classifications.roles import BASE_WEIGHTS, EditorialRole
from classifications.services.submissions import (
    EditorialRoleError,
    EditorialSubmissionError,
    ScoreDistribution,
    create_submission,
    resolve_editorial_role,
    update_submission,
)


def _game(slug: str) -> Game:
    return Game.objects.create(source_type=SourceType.MANUAL, name=slug, slug=slug)


def _user(username: str) -> User:
    return User.objects.create_user(username=username, password="p")


def _dist(micro=50, mystiko=20, macro=30):
    return ScoreDistribution(micro=micro, mystiko=mystiko, macro=macro)


class RoleResolutionTests(TestCase):
    def test_superuser_resolves_superuser(self):
        u = User.objects.create_superuser(username="su", password="p")
        self.assertEqual(resolve_editorial_role(u), EditorialRole.SUPERUSER)

    def test_moderator_group(self):
        u = _user("mod")
        g = Group.objects.create(name="moderators")
        EditorialGroupProfile.objects.create(group=g, is_moderator=True)
        u.groups.add(g)
        self.assertEqual(resolve_editorial_role(u), EditorialRole.MODERATOR)

    def test_community_leader_group(self):
        u = _user("cl")
        g = Group.objects.create(name="leaders")
        EditorialGroupProfile.objects.create(group=g, is_community_leader=True)
        u.groups.add(g)
        self.assertEqual(resolve_editorial_role(u), EditorialRole.COMMUNITY_LEADER)

    def test_community_default(self):
        u = _user("community")
        self.assertEqual(resolve_editorial_role(u), EditorialRole.COMMUNITY)

    def test_conflicting_groups_rejected(self):
        u = _user("conflict")
        m = Group.objects.create(name="m")
        c = Group.objects.create(name="c")
        EditorialGroupProfile.objects.create(group=m, is_moderator=True)
        EditorialGroupProfile.objects.create(group=c, is_community_leader=True)
        u.groups.add(m, c)
        with self.assertRaises(EditorialRoleError):
            resolve_editorial_role(u)

    def test_conflicting_groups_create_leaves_no_partial(self):
        game = _game("conflict-game")
        u = _user("conflict-create")
        m = Group.objects.create(name="mc")
        c = Group.objects.create(name="cc")
        EditorialGroupProfile.objects.create(group=m, is_moderator=True)
        EditorialGroupProfile.objects.create(group=c, is_community_leader=True)
        u.groups.add(m, c)
        with self.assertRaises(EditorialRoleError):
            create_submission(
                game=game,
                submitted_by=u,
                updated_by=u,
                challenge=_dist(),
                reward=_dist(micro=10, mystiko=30, macro=60),
            )
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_group_mutual_exclusion_clean(self):
        g = Group.objects.create(name="exclusive")
        profile = EditorialGroupProfile(
            group=g, is_moderator=True, is_community_leader=True
        )
        with self.assertRaises(ValidationError):
            profile.full_clean()


class SubmissionWorkflowTests(TestCase):
    def setUp(self):
        self.game = _game("sub-game")
        self.user1 = _user("sub-user1")
        self.user2 = _user("sub-user2")

    def test_two_users_submit_same_game(self):
        create_submission(
            game=self.game,
            submitted_by=self.user1,
            updated_by=self.user1,
            challenge=_dist(),
            reward=_dist(micro=10, mystiko=30, macro=60),
        )
        create_submission(
            game=self.game,
            submitted_by=self.user2,
            updated_by=self.user2,
            challenge=_dist(micro=30, mystiko=40, macro=30),
            reward=_dist(micro=20, mystiko=20, macro=60),
        )
        self.assertEqual(
            EditorialClassification.objects.filter(game=self.game).count(), 2
        )

    def test_same_user_cannot_submit_twice(self):
        create_submission(
            game=self.game,
            submitted_by=self.user1,
            updated_by=self.user1,
            challenge=_dist(),
            reward=_dist(micro=10, mystiko=30, macro=60),
        )
        with self.assertRaises(EditorialSubmissionError):
            create_submission(
                game=self.game,
                submitted_by=self.user1,
                updated_by=self.user1,
                challenge=_dist(),
                reward=_dist(micro=10, mystiko=30, macro=60),
            )

    def test_same_user_can_submit_another_game(self):
        other = _game("sub-other")
        create_submission(
            game=self.game,
            submitted_by=self.user1,
            updated_by=self.user1,
            challenge=_dist(),
            reward=_dist(micro=10, mystiko=30, macro=60),
        )
        create_submission(
            game=other,
            submitted_by=self.user1,
            updated_by=self.user1,
            challenge=_dist(),
            reward=_dist(micro=10, mystiko=30, macro=60),
        )
        self.assertEqual(
            EditorialClassification.objects.filter(submitted_by=self.user1).count(), 2
        )

    def test_profiles_attached_per_submission(self):
        s1 = create_submission(
            game=self.game,
            submitted_by=self.user1,
            updated_by=self.user1,
            challenge=_dist(),
            reward=_dist(micro=10, mystiko=30, macro=60),
        )
        s2 = create_submission(
            game=self.game,
            submitted_by=self.user2,
            updated_by=self.user2,
            challenge=_dist(micro=30, mystiko=40, macro=30),
            reward=_dist(micro=20, mystiko=20, macro=60),
        )
        self.assertIsNotNone(s1.challenge_profile)
        self.assertIsNotNone(s1.reward_profile)
        self.assertIsNotNone(s2.challenge_profile)
        self.assertIsNotNone(s2.reward_profile)

    def test_snapshot_superuser_weight(self):
        su = User.objects.create_superuser(username="sub-su", password="p")
        s = create_submission(
            game=self.game,
            submitted_by=su,
            updated_by=su,
            challenge=_dist(),
            reward=_dist(micro=10, mystiko=30, macro=60),
        )
        self.assertEqual(s.submitted_role, EditorialRole.SUPERUSER)
        self.assertEqual(s.submitted_base_weight, BASE_WEIGHTS[EditorialRole.SUPERUSER])

    def test_edit_preserves_identity_and_snapshot(self):
        s = create_submission(
            game=self.game,
            submitted_by=self.user1,
            updated_by=self.user1,
            challenge=_dist(),
            reward=_dist(micro=10, mystiko=30, macro=60),
        )
        original_game = s.game_id  # type: ignore[reportAttributeAccessIssue]
        original_submitter = s.submitted_by_id  # type: ignore[reportAttributeAccessIssue]
        original_role = s.submitted_role
        original_weight = s.submitted_base_weight

        update_submission(
            s,
            updated_by=self.user2,
            challenge=_dist(micro=40, mystiko=30, macro=30),
            reward=_dist(micro=20, mystiko=20, macro=60),
            notes="edited",
        )

        s.refresh_from_db()
        self.assertEqual(s.game_id, original_game)  # type: ignore[reportAttributeAccessIssue]
        self.assertEqual(s.submitted_by_id, original_submitter)  # type: ignore[reportAttributeAccessIssue]
        self.assertEqual(s.submitted_role, original_role)
        self.assertEqual(s.submitted_base_weight, original_weight)
        self.assertEqual(s.updated_by_id, self.user2.pk)  # type: ignore[reportAttributeAccessIssue]

    def test_create_rollback_leaves_no_partial_records(self):
        with self.assertRaises(ValidationError):
            create_submission(
                game=self.game,
                submitted_by=self.user1,
                updated_by=self.user1,
                challenge=_dist(micro=99, mystiko=0, macro=0),
                reward=_dist(micro=10, mystiko=30, macro=60),
            )
        self.assertFalse(
            EditorialClassification.objects.filter(game=self.game).exists()
        )
        self.assertFalse(ChallengeProfile.objects.exists())
        self.assertFalse(RewardProfile.objects.exists())

    def test_direct_create_requires_explicit_submitter(self):
        """Runtime ORM creation must not infer submitted_by from updated_by."""
        with self.assertRaises(IntegrityError):
            EditorialClassification.objects.create(
                game=self.game, updated_by=self.user1
            )
