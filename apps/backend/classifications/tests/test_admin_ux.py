"""
Editorial classification Admin UX tests — SBGC-63 polish.
"""

from __future__ import annotations

import json
import uuid

from django.contrib import admin
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse
from games.models import Game, SourceType

from classifications.admin import EditorialClassificationAdmin
from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    EditorialGroupProfile,
    RewardProfile,
)
from classifications.roles import EditorialRole

CH = "challenge_profile"
RW = "reward_profile"


def _game(slug="ux-game"):
    return Game.objects.create(source_type=SourceType.MANUAL, name=slug, slug=slug)


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


def _post_data(game_pk, *, submitted_by=None, reward=(10, 30, 60)):
    data = {
        "game": str(game_pk),
        "notes": "UX notes",
        **_inline(CH),
        **_inline(RW),
        **_scores(CH),
        **_scores(
            RW, micro=str(reward[0]), mystiko=str(reward[1]), macro=str(reward[2])
        ),
    }
    if submitted_by is not None:
        data["submitted_by"] = str(submitted_by)
    return data


def _inline_errors(response):
    """Return a {model_name: {field: [messages]}} map for inline form errors."""
    collected = {}
    for inline in response.context["inline_admin_formsets"]:
        model_name = inline.formset.model.__name__
        field_errors = {}
        for form_errors in inline.formset.errors:
            for field, messages in form_errors.items():
                field_errors.setdefault(field, []).extend(messages)
        collected[model_name] = field_errors
    return collected


class SubmittedByOwnershipTests(TestCase):
    def setUp(self):
        self.game = _game()
        self.add_url = reverse("admin:classifications_editorialclassification_add")
        self.superuser = User.objects.create_superuser(username="ux_su", password="p")
        self.staff = User.objects.create_user(
            username="ux_staff", password="p", is_staff=True
        )
        ct = ContentType.objects.get_for_model(EditorialClassification)
        self.staff.user_permissions.add(
            Permission.objects.get(
                codename="add_editorialclassification", content_type=ct
            )
        )

    def test_superuser_can_choose_submitter_and_sees_superuser_role(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.add_url)
        form = response.context["adminform"].form
        self.assertFalse(form.fields["submitted_by"].disabled)
        self.assertFalse(form.fields["submitted_by"].required)
        self.assertEqual(form.fields["submitted_role"].initial, EditorialRole.SUPERUSER)

    def test_ordinary_user_submitter_disabled_and_role_preview(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.add_url)
        form = response.context["adminform"].form
        self.assertTrue(form.fields["submitted_by"].disabled)
        self.assertEqual(form.fields["submitted_role"].initial, EditorialRole.COMMUNITY)

    def test_superuser_role_display_lists_current_superusers(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:auth_group_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Superuser — system-defined")
        self.assertContains(response, "ux_su")

    def test_no_fake_superuser_group_exists(self):
        self.assertFalse(Group.objects.filter(name="Superuser").exists())

    def test_on_behalf_role_map_reflects_selected_submitter(self):
        group = Group.objects.create(name="leaders")
        EditorialGroupProfile.objects.create(group=group, is_community_leader=True)
        leader = User.objects.create_user(username="cl_user", password="p")
        leader.groups.add(group)

        self.client.force_login(self.superuser)
        response = self.client.get(self.add_url)
        form = response.context["adminform"].form
        role_map = json.loads(form.fields["submitted_by"].widget.attrs["data-role-map"])
        entry = role_map[str(leader.pk)]
        self.assertEqual(entry["role"], EditorialRole.COMMUNITY_LEADER)
        self.assertEqual(entry["weight"], "0.65")


class FriendlyValidationTests(TestCase):
    def setUp(self):
        self.game = _game()
        self.user = User.objects.create_superuser(username="ux_val", password="p")
        self.client.force_login(self.user)
        self.add_url = reverse("admin:classifications_editorialclassification_add")

    def test_invalid_reward_total_shows_friendly_message_only(self):
        data = _post_data(self.game.pk, submitted_by=self.user.pk, reward=(60, 30, 30))
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reward scores must total exactly 100")
        self.assertNotContains(response, "reward_scores_total_100_ck")
        self.assertFalse(
            EditorialClassification.objects.filter(game=self.game).exists()
        )

    def test_duplicate_self_submission_shows_friendly_message(self):
        data = _post_data(self.game.pk, submitted_by=self.user.pk)
        self.client.post(self.add_url, data)
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "You have already submitted scores for this game."
        )
        self.assertNotContains(response, "already exists")
        self.assertEqual(
            EditorialClassification.objects.filter(game=self.game).count(), 1
        )

    def test_duplicate_on_behalf_shows_friendly_message(self):
        other = User.objects.create_user(username="ux_other", password="p")
        data = _post_data(self.game.pk, submitted_by=other.pk)
        self.client.post(self.add_url, data)
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "This user has already submitted scores for this game."
        )
        self.assertNotContains(response, "already exists")
        self.assertEqual(
            EditorialClassification.objects.filter(game=self.game).count(), 1
        )


class ScoreFieldValidationMatrixTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="ux_score", password="p")
        self.client.force_login(self.user)
        self.add_url = reverse("admin:classifications_editorialclassification_add")

    def _post(self, overrides):
        game = _game(slug=f"ux-{uuid.uuid4().hex}")
        data = _post_data(game.pk, submitted_by=self.user.pk)
        data.update(overrides)
        response = self.client.post(self.add_url, data)
        return game, response

    def test_each_score_field_above_100_shows_friendly_field_error(self):
        cases = [
            (CH, "micro_score", "Challenge Micro", "ChallengeProfile"),
            (CH, "mystiko_score", "Challenge Mystiko", "ChallengeProfile"),
            (CH, "macro_score", "Challenge Macro", "ChallengeProfile"),
            (RW, "micro_score", "Reward Micro", "RewardProfile"),
            (RW, "mystiko_score", "Reward Mystiko", "RewardProfile"),
            (RW, "macro_score", "Reward Macro", "RewardProfile"),
        ]
        for prefix, field, label, model_name in cases:
            with self.subTest(field=f"{prefix}.{field}"):
                game, response = self._post({f"{prefix}-0-{field}": "200"})
                self.assertEqual(response.status_code, 200)
                errors = _inline_errors(response)
                self.assertIn(field, errors[model_name])
                expected = f"{label} must be between 0 and 100 (got 200)."
                self.assertTrue(
                    any(expected in m for m in errors[model_name][field]),
                    errors[model_name][field],
                )
                self.assertNotContains(response, f"{prefix}_scores_range_ck")
                self.assertNotContains(response, f"{prefix}_scores_total_100_ck")
                self.assertFalse(
                    EditorialClassification.objects.filter(game=game).exists()
                )
                self.assertFalse(
                    ChallengeProfile.objects.filter(classification__game=game).exists()
                )
                self.assertFalse(
                    RewardProfile.objects.filter(classification__game=game).exists()
                )

    def test_below_range_challenge_score_rejected_without_crash(self):
        game, response = self._post({f"{CH}-0-micro_score": "-1"})
        self.assertEqual(response.status_code, 200)
        errors = _inline_errors(response)
        self.assertIn("micro_score", errors["ChallengeProfile"])
        self.assertNotContains(response, "challenge_scores_range_ck")
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_below_range_reward_score_rejected_without_crash(self):
        game, response = self._post({f"{RW}-0-macro_score": "-1"})
        self.assertEqual(response.status_code, 200)
        errors = _inline_errors(response)
        self.assertIn("macro_score", errors["RewardProfile"])
        self.assertNotContains(response, "reward_scores_range_ck")
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())


class TotalValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="ux_total", password="p")
        self.client.force_login(self.user)
        self.add_url = reverse("admin:classifications_editorialclassification_add")

    def _post(self, overrides):
        game = _game(slug=f"ux-total-{uuid.uuid4().hex}")
        data = _post_data(game.pk, submitted_by=self.user.pk)
        data.update(overrides)
        response = self.client.post(self.add_url, data)
        return game, response

    def test_challenge_total_not_100_shows_friendly_total_only(self):
        # 20 + 20 + 30 = 70
        game, response = self._post(
            {
                f"{CH}-0-micro_score": "20",
                f"{CH}-0-mystiko_score": "20",
                f"{CH}-0-macro_score": "30",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Challenge scores must total exactly 100 (got 70)."
        )
        self.assertNotContains(response, "challenge_scores_total_100_ck")
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_reward_total_not_100_shows_friendly_total_only(self):
        # 40 + 30 + 60 = 130
        game, response = self._post(
            {
                f"{RW}-0-micro_score": "40",
                f"{RW}-0-mystiko_score": "30",
                f"{RW}-0-macro_score": "60",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reward scores must total exactly 100 (got 130).")
        self.assertNotContains(response, "reward_scores_total_100_ck")
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())


class EditOwnershipTests(TestCase):
    def setUp(self):
        self.game = _game(slug="edit-own")
        self.admin = EditorialClassificationAdmin(EditorialClassification, admin.site)
        self.owner = User.objects.create_user(
            username="ux_edit_owner", password="p", is_staff=True
        )
        self.other = User.objects.create_user(
            username="ux_edit_other", password="p", is_staff=True
        )
        ct = ContentType.objects.get_for_model(EditorialClassification)
        change_perm = Permission.objects.get(
            codename="change_editorialclassification", content_type=ct
        )
        for u in (self.owner, self.other):
            u.user_permissions.add(change_perm)
        self.submission = EditorialClassification.objects.create(
            game=self.game, submitted_by=self.owner, updated_by=self.owner
        )

    def _request(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return request

    def test_owner_has_change_permission(self):
        self.assertTrue(
            self.admin.has_change_permission(self._request(self.owner), self.submission)
        )

    def test_non_owner_denied_change_permission(self):
        self.assertFalse(
            self.admin.has_change_permission(self._request(self.other), self.submission)
        )

    def test_superuser_has_change_permission(self):
        su = User.objects.create_superuser(username="ux_edit_su", password="p")
        self.assertTrue(
            self.admin.has_change_permission(self._request(su), self.submission)
        )

    def test_non_owner_change_post_denied(self):
        self.client.force_login(self.other)
        url = reverse(
            "admin:classifications_editorialclassification_change",
            args=(self.submission.pk,),
        )
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 403)
