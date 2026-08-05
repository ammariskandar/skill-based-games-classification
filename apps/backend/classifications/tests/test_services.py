"""
Editorial classification service tests — SBGC-46.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from games.models import Game, SourceType

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
)
from classifications.services.editorial import (
    ScoreDistribution,
    set_editorial_classification,
)


def _game(slug: str) -> Game:
    return Game.objects.create(source_type=SourceType.MANUAL, name=slug, slug=slug)


def _user(username: str) -> User:
    return User.objects.create_user(username=username, password="test")


def _challenge(micro=50, mystiko=20, macro=30):
    return ScoreDistribution(micro=micro, mystiko=mystiko, macro=macro)


def _reward(micro=10, mystiko=30, macro=60):
    return ScoreDistribution(micro=micro, mystiko=mystiko, macro=macro)


class ServiceCreationTests(TestCase):
    def test_creates_parent_and_both_profiles(self):
        result = set_editorial_classification(
            game=_game("svc-create"),
            updated_by=_user("svc-user1"),
            challenge=_challenge(),
            reward=_reward(),
        )
        self.assertEqual(result.game.slug, "svc-create")
        self.assertEqual(result.challenge_profile.micro_score, 50)
        self.assertEqual(result.reward_profile.micro_score, 10)

    def test_notes_persisted(self):
        result = set_editorial_classification(
            game=_game("svc-notes"),
            updated_by=_user("svc-user2"),
            challenge=_challenge(),
            reward=_reward(),
            notes="Draft notes.",
        )
        self.assertEqual(result.notes, "Draft notes.")

    def test_updated_by_persisted(self):
        user = _user("svc-user3")
        result = set_editorial_classification(
            game=_game("svc-by"),
            updated_by=user,
            challenge=_challenge(),
            reward=_reward(),
        )
        self.assertEqual(result.updated_by, user)

    def test_independent_profiles(self):
        result = set_editorial_classification(
            game=_game("svc-indep"),
            updated_by=_user("svc-user4"),
            challenge=_challenge(micro=70, mystiko=10, macro=20),
            reward=_reward(micro=0, mystiko=50, macro=50),
        )
        self.assertEqual(result.challenge_profile.micro_score, 70)
        self.assertEqual(result.reward_profile.micro_score, 0)

    def test_complete_classification_has_both_profiles(self):
        result = set_editorial_classification(
            game=_game("svc-complete"),
            updated_by=_user("svc-user5"),
            challenge=_challenge(),
            reward=_reward(),
        )
        self.assertIsNotNone(result.challenge_profile)
        self.assertIsNotNone(result.reward_profile)


class ServiceUpdateTests(TestCase):
    def setUp(self):
        self.game = _game("svc-update")
        self.user = _user("svc-update-user")
        self.original = set_editorial_classification(
            game=self.game,
            updated_by=self.user,
            challenge=_challenge(),
            reward=_reward(),
            notes="Original notes.",
        )

    def test_updates_existing(self):
        user2 = _user("svc-update-user2")
        result = set_editorial_classification(
            game=self.game,
            updated_by=user2,
            challenge=_challenge(micro=30, mystiko=40, macro=30),
            reward=_reward(micro=20, mystiko=20, macro=60),
            notes="Updated notes.",
        )
        self.assertEqual(result.pk, self.original.pk)
        self.assertEqual(result.notes, "Updated notes.")
        self.assertEqual(result.updated_by, user2)
        self.assertEqual(result.challenge_profile.micro_score, 30)
        self.assertEqual(result.reward_profile.micro_score, 20)

    def test_no_duplicate_rows(self):
        set_editorial_classification(
            game=self.game,
            updated_by=self.user,
            challenge=_challenge(),
            reward=_reward(),
        )
        self.assertEqual(EditorialClassification.objects.count(), 1)
        self.assertEqual(ChallengeProfile.objects.count(), 1)
        self.assertEqual(RewardProfile.objects.count(), 1)


class ServiceValidationTests(TestCase):
    def test_rejects_unsaved_game(self):
        g = Game(source_type=SourceType.MANUAL, name="Unsaved", slug="unsaved")
        with self.assertRaises(TypeError):
            set_editorial_classification(
                game=g,
                updated_by=_user("svc-v1"),
                challenge=_challenge(),
                reward=_reward(),
            )

    def test_rejects_unsaved_user(self):
        u = User(username="unsaved")
        with self.assertRaises(TypeError):
            set_editorial_classification(
                game=_game("svc-v2"),
                updated_by=u,
                challenge=_challenge(),
                reward=_reward(),
            )

    def test_rejects_non_game(self):
        with self.assertRaises(TypeError):
            set_editorial_classification(
                game="not a game",  # type: ignore[arg-type]
                updated_by=_user("svc-v3"),
                challenge=_challenge(),
                reward=_reward(),
            )

    def test_invalid_challenge_creates_nothing(self):
        game = _game("svc-atomic")
        user = _user("svc-atomic-user")
        with self.assertRaises(ValidationError):
            set_editorial_classification(
                game=game,
                updated_by=user,
                challenge=_challenge(micro=200, mystiko=0, macro=-100),
                reward=_reward(),
            )
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_invalid_reward_creates_nothing(self):
        game = _game("svc-atomic2")
        user = _user("svc-atomic-user2")
        with self.assertRaises(ValidationError):
            set_editorial_classification(
                game=game,
                updated_by=user,
                challenge=_challenge(),
                reward=_reward(micro=10, mystiko=10, macro=10),
            )
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_invalid_reward_does_not_leave_challenge_row(self):
        game = _game("svc-atomic3")
        user = _user("svc-atomic-user3")
        with self.assertRaises(ValidationError):
            set_editorial_classification(
                game=game,
                updated_by=user,
                challenge=_challenge(),
                reward=_reward(micro=99, mystiko=0, macro=0),
            )
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())
        self.assertFalse(
            ChallengeProfile.objects.filter(classification__game=game).exists()
        )

    def test_invalid_update_preserves_existing(self):
        game = _game("svc-preserve")
        user = _user("svc-preserve-user")
        set_editorial_classification(
            game=game,
            updated_by=user,
            challenge=_challenge(),
            reward=_reward(),
            notes="Keep me.",
        )
        with self.assertRaises(ValidationError):
            set_editorial_classification(
                game=game,
                updated_by=user,
                challenge=_challenge(micro=200, mystiko=-50, macro=-50),
                reward=_reward(),
            )
        c = EditorialClassification.objects.get(game=game)
        self.assertEqual(c.notes, "Keep me.")
        self.assertEqual(c.challenge_profile.micro_score, 50)


class ScoreDistributionTests(TestCase):
    def test_rejects_bool_micro(self):
        with self.assertRaises(TypeError):
            ScoreDistribution(micro=True, mystiko=50, macro=50)

    def test_rejects_bool_macro(self):
        with self.assertRaises(TypeError):
            ScoreDistribution(micro=50, mystiko=50, macro=False)
