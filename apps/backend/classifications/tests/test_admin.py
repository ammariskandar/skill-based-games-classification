"""
Editorial classification Admin tests — SBGC-46.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from games.models import Game, SourceType

from classifications.admin import (
    ChallengeProfileInline,
    RewardProfileInline,
)
from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
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


# ---------------------------------------------------------------------------
# Helpers for inline POST data
# ---------------------------------------------------------------------------

CH_PREFIX = "challenge_profile"
RW_PREFIX = "reward_profile"


def _inline_mgmt(prefix, total=1, initial=0):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "1",
        f"{prefix}-MAX_NUM_FORMS": "1",
    }


def _challenge_scores(micro="50", mystiko="20", macro="30"):
    return {
        f"{CH_PREFIX}-0-micro_score": micro,
        f"{CH_PREFIX}-0-mystiko_score": mystiko,
        f"{CH_PREFIX}-0-macro_score": macro,
    }


def _reward_scores(micro="10", mystiko="30", macro="60"):
    return {
        f"{RW_PREFIX}-0-micro_score": micro,
        f"{RW_PREFIX}-0-mystiko_score": mystiko,
        f"{RW_PREFIX}-0-macro_score": macro,
    }


def _valid_post_data(game_pk):
    return {
        "game": str(game_pk),
        "notes": "Admin test notes",
        **_inline_mgmt(CH_PREFIX),
        **_inline_mgmt(RW_PREFIX),
        **_challenge_scores(),
        **_reward_scores(),
    }


# ---------------------------------------------------------------------------
# Admin POST tests
# ---------------------------------------------------------------------------


class AdminPostTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="post_admin", password="testpass"
        )
        self.client.force_login(self.user)  # type: ignore[attr-defined]
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="Post Game", slug="post-game"
        )
        self.url = reverse("admin:classifications_editorialclassification_add")

    # -- valid creation -------------------------------------------------------

    def test_valid_post_creates_parent_and_both_profiles(self):
        response = self.client.post(self.url, _valid_post_data(self.game.pk))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EditorialClassification.objects.filter(game=self.game).exists())
        c = EditorialClassification.objects.get(game=self.game)
        self.assertIsNotNone(c.challenge_profile)
        self.assertIsNotNone(c.reward_profile)

    def test_valid_post_persists_notes(self):
        self.client.post(self.url, _valid_post_data(self.game.pk))
        c = EditorialClassification.objects.get(game=self.game)
        self.assertEqual(c.notes, "Admin test notes")

    def test_valid_post_sets_updated_by_from_request(self):
        self.client.post(self.url, _valid_post_data(self.game.pk))
        c = EditorialClassification.objects.get(game=self.game)
        self.assertEqual(c.updated_by, self.user)

    def test_valid_post_challenge_scores_correct(self):
        self.client.post(self.url, _valid_post_data(self.game.pk))
        c = EditorialClassification.objects.get(game=self.game)
        self.assertEqual(c.challenge_profile.micro_score, 50)
        self.assertEqual(c.challenge_profile.mystiko_score, 20)
        self.assertEqual(c.challenge_profile.macro_score, 30)

    def test_valid_post_reward_scores_correct(self):
        self.client.post(self.url, _valid_post_data(self.game.pk))
        c = EditorialClassification.objects.get(game=self.game)
        self.assertEqual(c.reward_profile.micro_score, 10)
        self.assertEqual(c.reward_profile.macro_score, 60)

    def test_valid_post_profiles_distinct(self):
        data = _valid_post_data(self.game.pk)
        data[f"{CH_PREFIX}-0-micro_score"] = "70"
        data[f"{CH_PREFIX}-0-macro_score"] = "10"  # total still 100
        self.client.post(self.url, data)
        c = EditorialClassification.objects.get(game=self.game)
        self.assertEqual(c.challenge_profile.micro_score, 70)
        self.assertEqual(c.reward_profile.micro_score, 10)

    def test_valid_post_exactly_three_rows(self):
        self.client.post(self.url, _valid_post_data(self.game.pk))
        self.assertEqual(EditorialClassification.objects.count(), 1)
        self.assertEqual(ChallengeProfile.objects.count(), 1)
        self.assertEqual(RewardProfile.objects.count(), 1)

    # -- invalid Challenge ----------------------------------------------------

    def test_invalid_challenge_total_no_persistence(self):
        data = _valid_post_data(self.game.pk)
        data[f"{CH_PREFIX}-0-macro_score"] = "20"  # total = 90
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            EditorialClassification.objects.filter(game=self.game).exists()
        )
        self.assertFalse(
            ChallengeProfile.objects.filter(classification__game=self.game).exists()
        )
        self.assertFalse(
            RewardProfile.objects.filter(classification__game=self.game).exists()
        )

    # -- invalid Reward -------------------------------------------------------

    def test_invalid_reward_total_no_persistence(self):
        data = _valid_post_data(self.game.pk)
        data[f"{RW_PREFIX}-0-macro_score"] = "20"  # total = 60
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            EditorialClassification.objects.filter(game=self.game).exists()
        )

        # Admin inlines with min_num=1 do not enforce presence at form-submit
        # time — Django accepts TOTAL_FORMS=0 and creates the parent without
        # profiles.  The service layer enforces completeness;
        # min_num is an editing convenience.  See docs/editorial-classification.md.


# ---------------------------------------------------------------------------
# View access tests
# ---------------------------------------------------------------------------


class AdminViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="view_admin", password="testpass"
        )
        self.client.force_login(self.user)  # type: ignore[attr-defined]
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="View Game", slug="view-game"
        )
        from classifications.services.editorial import (
            ScoreDistribution,
            set_editorial_classification,
        )

        self.classification = set_editorial_classification(
            game=self.game,
            updated_by=self.user,
            challenge=ScoreDistribution(micro=50, mystiko=20, macro=30),
            reward=ScoreDistribution(micro=10, mystiko=30, macro=60),
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

    def test_changelist_contains_game_name(self):
        url = reverse("admin:classifications_editorialclassification_changelist")
        response = self.client.get(url)
        self.assertContains(response, "View Game")


# ---------------------------------------------------------------------------
# No-network tests
# ---------------------------------------------------------------------------


class NoNetworkTests(TestCase):
    """All classifications Admin and model operations make no Steam calls."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="nonet_admin", password="testpass"
        )
        self.client.force_login(self.user)  # type: ignore[attr-defined]
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="NoNet Game", slug="nonet-game"
        )
        self.add_url = reverse("admin:classifications_editorialclassification_add")

    def _steam_guard(self):
        """Patch SteamClient.__init__ to fail if imported/called."""
        return patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("SteamClient must not be called"),
        )

    def test_changelist_no_steam(self):
        with self._steam_guard():
            url = reverse("admin:classifications_editorialclassification_changelist")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_add_view_no_steam(self):
        with self._steam_guard():
            response = self.client.get(self.add_url)
            self.assertEqual(response.status_code, 200)

    def test_valid_post_no_steam(self):
        with self._steam_guard():
            response = self.client.post(self.add_url, _valid_post_data(self.game.pk))
            self.assertEqual(response.status_code, 302)

    def test_invalid_challenge_post_no_steam(self):
        data = _valid_post_data(self.game.pk)
        data[f"{CH_PREFIX}-0-macro_score"] = "20"
        with self._steam_guard():
            response = self.client.post(self.add_url, data)
            self.assertEqual(response.status_code, 200)

    def test_invalid_reward_post_no_steam(self):
        data = _valid_post_data(self.game.pk)
        data[f"{RW_PREFIX}-0-macro_score"] = "20"
        with self._steam_guard():
            response = self.client.post(self.add_url, data)
            self.assertEqual(response.status_code, 200)

    def test_change_view_no_steam(self):
        from classifications.services.editorial import (
            ScoreDistribution,
            set_editorial_classification,
        )

        c = set_editorial_classification(
            game=self.game,
            updated_by=self.user,
            challenge=ScoreDistribution(micro=50, mystiko=20, macro=30),
            reward=ScoreDistribution(micro=10, mystiko=30, macro=60),
        )
        url = reverse(
            "admin:classifications_editorialclassification_change",
            args=(c.pk,),
        )
        with self._steam_guard():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
