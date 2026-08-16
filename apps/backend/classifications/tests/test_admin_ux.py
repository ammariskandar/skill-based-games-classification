"""
Editorial classification Admin UX tests — SBGC-63 polish.
"""

from __future__ import annotations

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from games.models import Game, SourceType

from classifications.models import EditorialClassification
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

    def test_duplicate_submission_shows_friendly_message(self):
        data = _post_data(self.game.pk, submitted_by=self.user.pk)
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
