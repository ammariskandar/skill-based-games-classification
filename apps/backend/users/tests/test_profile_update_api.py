"""Profile update API tests — SBGC-222."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase

from users.models import UserProfile


class ProfileUpdateApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="james", password="pass")
        UserProfile.objects.create(user=self.user, avatar_key="male_1")
        self.url = "/api/v1/users/me"

    def _patch(self, **payload):
        return self.client.patch(
            self.url, data=payload, content_type="application/json"
        )

    def test_unauthenticated_update_rejected(self):
        response = self._patch(first_name="James")
        self.assertEqual(response.status_code, 401)

    def test_update_first_and_last_name(self):
        self.client.force_login(self.user)
        response = self._patch(first_name="李", last_name="小龙-O'Connor")
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "李")
        self.assertEqual(self.user.last_name, "小龙-O'Connor")

    def test_invalid_avatar_preset_rejected(self):
        self.client.force_login(self.user)
        response = self._patch(avatar_key="not_a_real_key")
        self.assertEqual(response.status_code, 422)

    def test_preset_border_requires_preset_id(self):
        self.client.force_login(self.user)
        response = self._patch(border_type="PRESET")
        self.assertEqual(response.status_code, 422)

    def test_solid_border_requires_hex_color(self):
        self.client.force_login(self.user)
        response = self._patch(border_type="SOLID", border_color="")
        self.assertEqual(response.status_code, 422)

    def test_bio_mode_persistence(self):
        self.client.force_login(self.user)
        response = self._patch(bio_mode="BBCODE", bio="[b]Hello[/b]")
        self.assertEqual(response.status_code, 200)

        profile = UserProfile.objects.get(user=self.user)
        profile.refresh_from_db()
        self.assertEqual(profile.bio_mode, "BBCODE")
        self.assertEqual(profile.bio, "[b]Hello[/b]")
