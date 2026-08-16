"""
Game deletion Admin tests — SBGC-182.
"""

from __future__ import annotations

from classifications.services.editorial import (
    ScoreDistribution,
    set_editorial_classification,
)
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from games.models import Game, ListingStatus
from games.services.manual import create_manual_game


class GameDeletionAdminTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="delete-admin", password="pw"
        )
        self.game = create_manual_game(
            name="SBGC 182 Deletion Test",
            slug="sbgc-182-deletion-test",
            listing_status=ListingStatus.DRAFT,
        )
        set_editorial_classification(
            game=self.game,
            updated_by=self.superuser,
            challenge=ScoreDistribution(micro=50, mystiko=30, macro=20),
            reward=ScoreDistribution(micro=20, mystiko=30, macro=50),
            notes="SBGC-182 deletion cascade validation",
        )

    def _delete_url(self, game=None):
        return reverse("admin:games_game_delete", args=((game or self.game).pk,))

    def test_delete_confirmation_lists_cascade_summary(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self._delete_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SBGC 182 Deletion Test")
        self.assertContains(response, "Editorial classification")

    def test_superuser_can_delete_via_admin(self):
        self.client.force_login(self.superuser)
        game_id = self.game.pk
        response = self.client.post(self._delete_url(), {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Game.objects.filter(pk=game_id).exists())

    def test_staff_without_delete_permission_denied(self):
        staff = User.objects.create_user(
            username="no-delete-staff", password="pw", is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.get(self._delete_url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())

    def test_bulk_delete_action_disabled(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:games_game_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "delete_selected")
