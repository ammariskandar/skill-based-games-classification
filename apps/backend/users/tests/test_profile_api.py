"""Public profile API tests — SBGC-221."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from games.models import Game, SourceType

from users.models import UserProfile, UserTopGame


class PublicUserProfileApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="thenamesammaris", password="pass"
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            bio="A sample bio",
            avatar_key="anime_male_4",
            border_type=UserProfile.BorderType.PRESET,
            border_preset_id=1,
            steam_profile_url="https://steamcommunity.com/id/thenamesammaris",
        )
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="Hades", slug="hades"
        )
        UserTopGame.objects.create(profile=self.profile, game=self.game, rank=1)

    def test_profile_returns_public_shape(self):
        response = self.client.get("/api/v1/users/thenamesammaris")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["username"], "thenamesammaris")
        self.assertEqual(data["bio"], "A sample bio")
        self.assertEqual(data["avatar_key"], "anime_male_4")
        self.assertEqual(data["border_type"], "PRESET")
        self.assertEqual(data["border_preset_id"], 1)
        self.assertTrue(data["is_steam_linked"])
        self.assertEqual(data["top_games"][0]["slug"], "hades")
        self.assertFalse(data["is_viewer_owner"])
        # DNA is only stubbed when a Portal 2 snapshot exists.
        self.assertIsNone(data["dna_scores"])

    def test_profile_username_is_case_insensitive(self):
        response = self.client.get("/api/v1/users/THENAMESAMMARIS")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "thenamesammaris")

    def test_missing_user_returns_404(self):
        response = self.client.get("/api/v1/users/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_viewer_owner_flag_is_set_for_authenticated_owner(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/v1/users/thenamesammaris")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_viewer_owner"])
