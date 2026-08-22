"""
Game Admin Steam override-provenance tests — SBGC-188.

Verifies the per-field override detection and "Resume Steam sync" controls
through the real Admin client.  Manual Games are unaffected.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from games.models import ContentType, Game, ListingStatus, SourceType


def _steam_change_data(**overrides) -> dict:
    data = {
        "source_type": SourceType.STEAM,
        "external_id": "730",
        "name": "Test Steam",
        "slug": "test-steam",
        "content_type": ContentType.GAME,
        "listing_status": ListingStatus.DRAFT,
        "release_date": "",
        "developer": "",
        "description": "",
        "manual_image_url": "",
        "manual_website_url": "",
        "_changelist_filters": "",
    }
    data.update(overrides)
    return data


class SteamOverrideTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="editor", password="p")
        cls.game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Test Steam",
            slug="test-steam",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.DRAFT,
            description="Steam desc",
            developer="Steam dev",
            release_date=date(2020, 1, 1),
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("admin:games_game_change", args=(self.game.pk,))

    def _post(self, **overrides):
        return self.client.post(self.url, _steam_change_data(**overrides))

    def test_save_unchanged_no_new_overrides(self):
        self._post(
            description="Steam desc",
            developer="Steam dev",
            release_date="2020-01-01",
        )
        self.game.refresh_from_db()
        self.assertFalse(self.game.description_overridden)
        self.assertFalse(self.game.developer_overridden)
        self.assertFalse(self.game.release_date_overridden)

    def test_change_description_only(self):
        self._post(
            description="Human desc",
            developer="Steam dev",
            release_date="2020-01-01",
        )
        self.game.refresh_from_db()
        self.assertEqual(self.game.description, "Human desc")
        self.assertTrue(self.game.description_overridden)
        self.assertFalse(self.game.developer_overridden)
        self.assertFalse(self.game.release_date_overridden)

    def test_resume_description(self):
        self.game.description_overridden = True
        self.game.description = "Human desc"
        self.game.save()

        self._post(
            description="Human desc",
            developer="Steam dev",
            release_date="2020-01-01",
            resume_description="on",
        )
        self.game.refresh_from_db()
        self.assertFalse(self.game.description_overridden)

    def test_resume_wins_over_change(self):
        self._post(
            description="Human desc",
            developer="Steam dev",
            release_date="2020-01-01",
            resume_description="on",
        )
        self.game.refresh_from_db()
        # Explicit resume wins: override cleared, typed value may remain until
        # the next Steam refresh repopulates it.
        self.assertFalse(self.game.description_overridden)
        self.assertEqual(self.game.description, "Human desc")


class ManualGameOverrideTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="editor", password="p")
        cls.game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Manual",
            slug="manual",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.DRAFT,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("admin:games_game_change", args=(self.game.pk,))

    def test_manual_change_form_hides_resume_controls(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "Resume Steam sync for description")

    def test_manual_save_does_not_touch_override_flags(self):
        data = {
            "source_type": SourceType.MANUAL,
            "external_id": "",
            "name": "Manual",
            "slug": "manual",
            "content_type": ContentType.GAME,
            "listing_status": ListingStatus.DRAFT,
            "release_date": "",
            "developer": "",
            "description": "Human desc",
            "manual_image_url": "",
            "manual_website_url": "",
            "_changelist_filters": "",
        }
        self.client.post(self.url, data)
        self.game.refresh_from_db()
        self.assertFalse(self.game.description_overridden)
        self.assertFalse(self.game.developer_overridden)
        self.assertFalse(self.game.release_date_overridden)
