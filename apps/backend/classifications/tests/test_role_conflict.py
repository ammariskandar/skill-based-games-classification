"""
SBGC-64 conflicting editorial-role Group membership tests.

Covers the per-User invariant: a non-superuser must not resolve to both
Moderator and Community Leader through two different Groups.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from games.models import Game, SourceType

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    EditorialGroupProfile,
    RewardProfile,
)
from classifications.services.submissions import (
    EditorialRoleError,
    ScoreDistribution,
    create_submission,
    group_set_has_role_conflict,
)

CH = "challenge_profile"
RW = "reward_profile"


def _game(slug="conflict-game"):
    return Game.objects.create(source_type=SourceType.MANUAL, name=slug, slug=slug)


def _user(username, *, is_staff=False):
    return User.objects.create_user(username=username, password="p", is_staff=is_staff)


def _mod_group(name):
    group = Group.objects.create(name=name)
    EditorialGroupProfile.objects.create(group=group, is_moderator=True)
    return group


def _cl_group(name):
    group = Group.objects.create(name=name)
    EditorialGroupProfile.objects.create(group=group, is_community_leader=True)
    return group


def _ordinary_group(name):
    return Group.objects.create(name=name)


def _conflicted_user(username, *, is_staff=False):
    user = _user(username, is_staff=is_staff)
    user.groups.add(_mod_group(f"{username}-mod"), _cl_group(f"{username}-cl"))
    return user


def _inline(prefix):
    return {
        f"{prefix}-TOTAL_FORMS": "1",
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "1",
        f"{prefix}-MAX_NUM_FORMS": "1",
    }


def _scores(prefix, micro="50", mystiko="20", macro="30"):
    return {
        f"{prefix}-0-micro_score": micro,
        f"{prefix}-0-mystiko_score": mystiko,
        f"{prefix}-0-macro_score": macro,
    }


def _post_data(game_pk, *, submitted_by=None):
    data = {
        "game": str(game_pk),
        "notes": "",
        **_inline(CH),
        **_inline(RW),
        **_scores(CH),
        **_scores(RW, micro="10", mystiko="30", macro="60"),
    }
    if submitted_by is not None:
        data["submitted_by"] = str(submitted_by)
    return data


class GroupRoleConflictValidatorTests(TestCase):
    def test_valid_combinations(self):
        mod = _mod_group("valid-mod")
        cl = _cl_group("valid-cl")
        ordinary = _ordinary_group("valid-ordinary")
        ordinary2 = _ordinary_group("valid-ordinary-2")

        self.assertFalse(group_set_has_role_conflict([mod]))
        self.assertFalse(group_set_has_role_conflict([cl]))
        self.assertFalse(group_set_has_role_conflict([mod, ordinary]))
        self.assertFalse(group_set_has_role_conflict([cl, ordinary]))
        self.assertFalse(group_set_has_role_conflict([ordinary, ordinary2]))
        self.assertFalse(group_set_has_role_conflict([]))

    def test_conflicting_combination(self):
        mod = _mod_group("conflict-mod")
        cl = _cl_group("conflict-cl")
        self.assertTrue(group_set_has_role_conflict([mod, cl]))

    def test_accepts_queryset(self):
        mod = _mod_group("qs-mod")
        cl = _cl_group("qs-cl")
        self.assertTrue(
            group_set_has_role_conflict(Group.objects.filter(pk__in=[mod.pk, cl.pk]))
        )


class UserAdminGroupValidationTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="conflict_admin", password="p"
        )
        self.client.force_login(self.superuser)

    def _change_url(self, user):
        return reverse("admin:auth_user_change", args=(user.pk,))

    def _data(self, user, *, groups):
        return {
            "username": user.username,
            "password": "",
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "is_active": "on" if user.is_active else "",
            "is_staff": "on" if user.is_staff else "",
            "is_superuser": "on" if user.is_superuser else "",
            "groups": [str(g.pk) for g in groups],
            "user_permissions": [],
            "last_login_0": "",
            "last_login_1": "",
            "date_joined_0": user.date_joined.strftime("%Y-%m-%d"),
            "date_joined_1": user.date_joined.strftime("%H:%M:%S"),
        }

    def test_moderator_plus_cl_rejected_and_membership_unchanged(self):
        user = _user("conflict_target", is_staff=True)
        mod = _mod_group("target-mod")
        cl = _cl_group("target-cl")
        user.groups.add(mod)

        response = self.client.post(
            self._change_url(user), self._data(user, groups=[mod, cl])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "This user cannot belong to both Moderator and Community Leader "
            "classification roles.",
        )
        user.refresh_from_db()
        self.assertEqual(set(user.groups.values_list("pk", flat=True)), {mod.pk})

    def test_moderator_only_is_valid(self):
        user = _user("mod_only", is_staff=True)
        mod = _mod_group("mod-only-group")
        response = self.client.post(
            self._change_url(user), self._data(user, groups=[mod])
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(set(user.groups.values_list("pk", flat=True)), {mod.pk})

    def test_moderator_plus_ordinary_is_valid(self):
        user = _user("mod_ordinary", is_staff=True)
        mod = _mod_group("mod-ordinary-mod")
        ordinary = _ordinary_group("mod-ordinary-ordinary")
        response = self.client.post(
            self._change_url(user), self._data(user, groups=[mod, ordinary])
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(
            set(user.groups.values_list("pk", flat=True)), {mod.pk, ordinary.pk}
        )


class ClassificationAdminConflictTests(TestCase):
    def setUp(self):
        self.add_url = reverse("admin:classifications_editorialclassification_add")
        ct = ContentType.objects.get_for_model(EditorialClassification)
        self.add_perm = Permission.objects.get(
            codename="add_editorialclassification", content_type=ct
        )
        self.view_perm = Permission.objects.get(
            codename="view_editorialclassification", content_type=ct
        )

    def test_conflicted_operator_add_page_redirects_with_message(self):
        user = _conflicted_user("conflicted_op", is_staff=True)
        user.user_permissions.add(self.add_perm, self.view_perm)
        self.client.force_login(user)
        response = self.client.get(self.add_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "conflicting classification roles")

    def test_superuser_add_page_loads_with_conflicted_candidate(self):
        _conflicted_user("conflicted_candidate")
        superuser = User.objects.create_superuser(username="conflict_su", password="p")
        self.client.force_login(superuser)
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 200)

    def test_superuser_cannot_submit_on_behalf_of_conflicted_user(self):
        conflicted = _conflicted_user("conflicted_candidate2")
        game = _game("on-behalf-conflict")
        superuser = User.objects.create_superuser(username="conflict_su2", password="p")
        self.client.force_login(superuser)
        response = self.client.post(
            self.add_url, _post_data(game.pk, submitted_by=conflicted.pk)
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "conflicting classification roles and cannot be selected"
        )
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())


class GroupProfileMessageTests(TestCase):
    def test_group_conflict_message_is_friendly_only(self):
        group = Group.objects.create(name="exclusive-group")
        profile = EditorialGroupProfile(
            group=group, is_moderator=True, is_community_leader=True
        )
        with self.assertRaises(ValidationError) as cm:
            profile.full_clean()
        self.assertIn(
            "A group cannot be both Moderator and Community Leader.",
            str(cm.exception),
        )
        self.assertNotIn("editorial_group_role_exclusive_ck", str(cm.exception))


class ServiceConflictTests(TestCase):
    def test_conflicted_user_create_rejected_no_partial_rows(self):
        conflicted = _conflicted_user("conflicted_svc")
        game = _game("service-conflict")
        with self.assertRaises(EditorialRoleError):
            create_submission(
                game=game,
                submitted_by=conflicted,
                updated_by=conflicted,
                challenge=ScoreDistribution(micro=50, mystiko=20, macro=30),
                reward=ScoreDistribution(micro=10, mystiko=30, macro=60),
            )
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())
        self.assertFalse(ChallengeProfile.objects.exists())
        self.assertFalse(RewardProfile.objects.exists())
