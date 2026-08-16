"""
Game deletion service tests — SBGC-182.
"""

from __future__ import annotations

from unittest.mock import patch

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
)
from classifications.services.editorial import (
    ScoreDistribution,
    set_editorial_classification,
)
from django.contrib.auth.models import User
from django.test import TestCase

from games.models import Game, ListingStatus, SourceType
from games.services.deletion import GameDeletionError, delete_game
from games.services.manual import create_manual_game


def _classification_for(game: Game, user: User) -> EditorialClassification:
    return set_editorial_classification(
        game=game,
        updated_by=user,
        challenge=ScoreDistribution(micro=50, mystiko=30, macro=20),
        reward=ScoreDistribution(micro=20, mystiko=30, macro=50),
        notes="SBGC-182 deletion cascade validation",
    )


class GameDeletionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="deletion-editor", password="pw")

    def test_delete_manual_game_cascades_classification_and_profiles(self):
        game = create_manual_game(name="Delete Me")
        classification = _classification_for(game, self.user)

        game_id = game.pk
        classification_id = classification.pk
        challenge_id = classification.challenge_profile.pk
        reward_id = classification.reward_profile.pk

        result = delete_game(game)

        self.assertEqual(result.game_id, game_id)
        self.assertEqual(result.source_type, SourceType.MANUAL)
        self.assertEqual(result.slug, "delete-me")
        self.assertFalse(Game.objects.filter(pk=game_id).exists())
        self.assertFalse(
            EditorialClassification.objects.filter(pk=classification_id).exists()
        )
        self.assertFalse(ChallengeProfile.objects.filter(pk=challenge_id).exists())
        self.assertFalse(RewardProfile.objects.filter(pk=reward_id).exists())

    def test_unrelated_game_and_metadata_survive(self):
        target = create_manual_game(name="Target", slug="target")
        control = create_manual_game(name="Control", slug="control")
        target_classification = _classification_for(target, self.user)
        control_classification = _classification_for(control, self.user)

        delete_game(target)

        control.refresh_from_db()
        self.assertEqual(control.name, "Control")
        self.assertTrue(
            EditorialClassification.objects.filter(
                pk=control_classification.pk
            ).exists()
        )
        self.assertTrue(
            ChallengeProfile.objects.filter(
                pk=control_classification.challenge_profile.pk
            ).exists()
        )
        self.assertTrue(
            RewardProfile.objects.filter(
                pk=control_classification.reward_profile.pk
            ).exists()
        )
        self.assertFalse(
            EditorialClassification.objects.filter(pk=target_classification.pk).exists()
        )

    def test_user_survives_deletion(self):
        game = create_manual_game(name="Delete Me")
        _classification_for(game, self.user)

        delete_game(game)

        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_published_manual_game_is_deletable(self):
        game = create_manual_game(
            name="Published", listing_status=ListingStatus.PUBLISHED
        )
        delete_game(game)
        self.assertFalse(Game.objects.filter(pk=game.pk).exists())

    def test_slug_reusable_after_delete(self):
        game = create_manual_game(name="First", slug="reusable-slug")
        delete_game(game)
        recreate = create_manual_game(name="Second", slug="reusable-slug")
        self.assertEqual(recreate.slug, "reusable-slug")

    def test_steam_game_delete_and_identity_reusable(self):
        game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
        )
        result = delete_game(game)

        self.assertEqual(result.source_type, SourceType.STEAM)
        self.assertFalse(Game.objects.filter(pk=result.game_id).exists())

        recreate = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
        )
        self.assertEqual(recreate.external_id, "620")

    def test_unsaved_game_rejected(self):
        unsaved = Game(source_type=SourceType.MANUAL, name="X", slug="x")
        with self.assertRaises(GameDeletionError):
            delete_game(unsaved)

    def test_deletion_does_not_touch_steam(self):
        game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
        )
        with patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("SteamClient must not be called"),
        ):
            delete_game(game)
        self.assertFalse(Game.objects.filter(pk=game.pk).exists())
