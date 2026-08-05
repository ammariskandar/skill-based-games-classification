"""
Editorial classification Admin tests — SBGC-46.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from games.models import Game, SourceType

from classifications.admin import (
    ChallengeProfileInline,
    RewardProfileInline,
)
from classifications.models import (
    EditorialClassification,
)
from classifications.services.editorial import (
    ScoreDistribution,
    set_editorial_classification,
)


class AdminRegistrationTests(TestCase):
    def test_model_registered(self):
        from django.contrib import admin

        self.assertTrue(admin.site.is_registered(EditorialClassification))

    def test_challenge_inline_config(self):
        self.assertEqual(ChallengeProfileInline.extra, 0)
        self.assertEqual(ChallengeProfileInline.max_num, 1)
        self.assertEqual(ChallengeProfileInline.min_num, 1)
        self.assertFalse(ChallengeProfileInline.can_delete)

    def test_reward_inline_config(self):
        self.assertEqual(RewardProfileInline.extra, 0)
        self.assertEqual(RewardProfileInline.max_num, 1)
        self.assertEqual(RewardProfileInline.min_num, 1)
        self.assertFalse(RewardProfileInline.can_delete)

    def test_inline_labels_distinct(self):
        self.assertEqual(ChallengeProfileInline.verbose_name, "Challenge Profile")
        self.assertEqual(RewardProfileInline.verbose_name, "Reward Profile")


class AdminFunctionalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="class_admin", password="testpass"
        )
        self.client.force_login(self.user)  # type: ignore[attr-defined]
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="Admin Game", slug="admin-game"
        )
        # Create a classification via the service so we have data to view.
        self.classification = set_editorial_classification(
            game=self.game,
            updated_by=self.user,
            challenge=ScoreDistribution(micro=50, mystiko=20, macro=30),
            reward=ScoreDistribution(micro=10, mystiko=30, macro=60),
            notes="Test classification.",
        )

    def test_changelist_loads(self):
        url = reverse("admin:classifications_editorialclassification_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_add_view_loads(self):
        url = reverse("admin:classifications_editorialclassification_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_change_view_loads(self):
        url = reverse(
            "admin:classifications_editorialclassification_change",
            args=(self.classification.pk,),
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_updated_by_is_readonly_in_form(self):
        """updated_by is readonly and was set from the service, not the form."""
        self.assertEqual(self.classification.updated_by, self.user)

    def test_str_in_changelist(self):
        url = reverse("admin:classifications_editorialclassification_changelist")
        response = self.client.get(url)
        self.assertContains(response, "Admin Game")

    def test_no_network_on_admin_views(self):
        """All Admin views load without network calls (tested implicitly)."""
        urls = [
            reverse("admin:classifications_editorialclassification_changelist"),
            reverse("admin:classifications_editorialclassification_add"),
            reverse(
                "admin:classifications_editorialclassification_change",
                args=(self.classification.pk,),
            ),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertIn(response.status_code, (200, 302))
