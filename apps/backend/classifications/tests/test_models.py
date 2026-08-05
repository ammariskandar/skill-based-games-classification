"""
Editorial classification model tests — SBGC-46.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from games.models import Game, SourceType

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game(slug: str) -> Game:
    return Game.objects.create(source_type=SourceType.MANUAL, name=slug, slug=slug)


def _make_user(username: str) -> User:
    return User.objects.create_user(username=username, password="test")


def _valid_challenge_kwargs() -> dict:
    return {"micro_score": 50, "mystiko_score": 20, "macro_score": 30}


def _valid_reward_kwargs() -> dict:
    return {"micro_score": 10, "mystiko_score": 30, "macro_score": 60}


# ---------------------------------------------------------------------------
# Parent model
# ---------------------------------------------------------------------------


class EditorialClassificationTests(TestCase):
    def test_one_per_game(self):
        game = _make_game("parent-test")
        user = _make_user("editor1")
        c1 = EditorialClassification.objects.create(game=game, updated_by=user)
        self.assertEqual(c1.game, game)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                EditorialClassification.objects.create(game=game, updated_by=user)

    def test_game_is_required(self):
        user = _make_user("editor2")
        with self.assertRaises(IntegrityError):
            EditorialClassification.objects.create(updated_by=user)

    def test_updated_by_is_required(self):
        game = _make_game("parent-user-req")
        with self.assertRaises(IntegrityError):
            EditorialClassification.objects.create(game=game)

    def test_notes_blank_by_default(self):
        game = _make_game("parent-notes")
        user = _make_user("editor3")
        c = EditorialClassification.objects.create(game=game, updated_by=user)
        self.assertEqual(c.notes, "")

    def test_timestamps_populated(self):
        game = _make_game("parent-ts")
        user = _make_user("editor4")
        c = EditorialClassification.objects.create(game=game, updated_by=user)
        self.assertIsNotNone(c.created_at)
        self.assertIsNotNone(c.updated_at)

    def test_game_cascade_delete(self):
        game = _make_game("parent-cascade")
        user = _make_user("editor5")
        EditorialClassification.objects.create(game=game, updated_by=user)
        game.delete()
        self.assertEqual(EditorialClassification.objects.count(), 0)

    def test_user_protect(self):
        game = _make_game("parent-protect")
        user = _make_user("editor6")
        EditorialClassification.objects.create(game=game, updated_by=user)
        with self.assertRaises(IntegrityError):
            user.delete()

    def test_related_name(self):
        game = _make_game("parent-related")
        user = _make_user("editor7")
        c = EditorialClassification.objects.create(game=game, updated_by=user)
        self.assertEqual(game.editorial_classification, c)

    def test_str(self):
        game = _make_game("parent-str")
        user = _make_user("editor8")
        c = EditorialClassification.objects.create(game=game, updated_by=user)
        self.assertIn("parent-str", str(c))


# ---------------------------------------------------------------------------
# Challenge profile
# ---------------------------------------------------------------------------


class ChallengeProfileTests(TestCase):
    def setUp(self):
        self.game = _make_game("challenge-game")
        self.user = _make_user("challenge-editor")
        self.parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )

    def test_valid_scores(self):
        cp = ChallengeProfile.objects.create(
            classification=self.parent, **_valid_challenge_kwargs()
        )
        self.assertEqual(cp.micro_score, 50)
        self.assertEqual(cp.mystiko_score, 20)
        self.assertEqual(cp.macro_score, 30)

    def test_zero_heavy_valid_distribution(self):
        cp = ChallengeProfile.objects.create(
            classification=self.parent, micro_score=100, mystiko_score=0, macro_score=0
        )
        self.assertEqual(cp.micro_score + cp.mystiko_score + cp.macro_score, 100)

    def test_total_99_rejected(self):
        cp = ChallengeProfile(
            classification=self.parent, micro_score=50, mystiko_score=20, macro_score=29
        )
        with self.assertRaises(ValidationError):
            cp.full_clean()

    def test_total_101_rejected(self):
        cp = ChallengeProfile(
            classification=self.parent, micro_score=50, mystiko_score=21, macro_score=30
        )
        with self.assertRaises(ValidationError):
            cp.full_clean()

    def test_negative_rejected(self):
        cp = ChallengeProfile(
            classification=self.parent, micro_score=-1, mystiko_score=50, macro_score=51
        )
        with self.assertRaises(ValidationError):
            cp.full_clean()

    def test_above_100_rejected(self):
        cp = ChallengeProfile(
            classification=self.parent,
            micro_score=101,
            mystiko_score=0,
            macro_score=-1,
        )
        with self.assertRaises(ValidationError):
            cp.full_clean()

    def test_duplicate_profile_rejected(self):
        ChallengeProfile.objects.create(
            classification=self.parent, **_valid_challenge_kwargs()
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent, **_valid_challenge_kwargs()
                )

    def test_range_constraint_db(self):
        """DB-level range constraint rejects out-of-range score without clean()."""
        self.parent.delete()  # need fresh parent with new profile
        game2 = _make_game("challenge-db-range")
        user2 = _make_user("challenge-db-editor")
        parent2 = EditorialClassification.objects.create(game=game2, updated_by=user2)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=parent2,
                    micro_score=101,
                    mystiko_score=0,
                    macro_score=-1,
                )


# ---------------------------------------------------------------------------
# Reward profile
# ---------------------------------------------------------------------------


class RewardProfileTests(TestCase):
    def setUp(self):
        self.game = _make_game("reward-game")
        self.user = _make_user("reward-editor")
        self.parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )

    def test_valid_scores(self):
        rp = RewardProfile.objects.create(
            classification=self.parent, **_valid_reward_kwargs()
        )
        self.assertEqual(rp.micro_score, 10)
        self.assertEqual(rp.macro_score, 60)

    def test_zero_heavy_valid_distribution(self):
        rp = RewardProfile.objects.create(
            classification=self.parent, micro_score=0, mystiko_score=100, macro_score=0
        )
        self.assertEqual(rp.micro_score + rp.mystiko_score + rp.macro_score, 100)

    def test_total_99_rejected(self):
        rp = RewardProfile(
            classification=self.parent, micro_score=10, mystiko_score=30, macro_score=59
        )
        with self.assertRaises(ValidationError):
            rp.full_clean()

    def test_total_101_rejected(self):
        rp = RewardProfile(
            classification=self.parent, micro_score=10, mystiko_score=31, macro_score=60
        )
        with self.assertRaises(ValidationError):
            rp.full_clean()

    def test_negative_rejected(self):
        rp = RewardProfile(
            classification=self.parent, micro_score=-5, mystiko_score=50, macro_score=55
        )
        with self.assertRaises(ValidationError):
            rp.full_clean()

    def test_duplicate_profile_rejected(self):
        RewardProfile.objects.create(
            classification=self.parent, **_valid_reward_kwargs()
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=self.parent, **_valid_reward_kwargs()
                )

    def test_range_constraint_db(self):
        """DB-level range constraint rejects out-of-range score without clean()."""
        self.parent.delete()
        game2 = _make_game("reward-db-range")
        user2 = _make_user("reward-db-editor")
        parent2 = EditorialClassification.objects.create(game=game2, updated_by=user2)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=parent2,
                    micro_score=200,
                    mystiko_score=-50,
                    macro_score=-50,
                )
