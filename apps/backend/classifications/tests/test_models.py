"""
Editorial classification model tests — SBGC-46.
"""

from __future__ import annotations

from unittest.mock import patch

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


def _valid_challenge_kwargs(micro=50, mystiko=20, macro=30):
    return {"micro_score": micro, "mystiko_score": mystiko, "macro_score": macro}


def _valid_reward_kwargs(micro=10, mystiko=30, macro=60):
    return {"micro_score": micro, "mystiko_score": mystiko, "macro_score": macro}


# ---------------------------------------------------------------------------
# Parent model
# ---------------------------------------------------------------------------


class EditorialClassificationTests(TestCase):
    def test_one_per_game(self):
        game = _make_game("parent-test")
        user = _make_user("editor1")
        EditorialClassification.objects.create(game=game, updated_by=user)
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
        self.assertEqual(game.editorial_classification, c)  # pyright: ignore[reportAttributeAccessIssue]

    def test_str(self):
        game = _make_game("parent-str")
        user = _make_user("editor8")
        c = EditorialClassification.objects.create(game=game, updated_by=user)
        self.assertIn("parent-str", str(c))


# ---------------------------------------------------------------------------
# Challenge profile — validation
# ---------------------------------------------------------------------------


class ChallengeProfileValidationTests(TestCase):
    def setUp(self):
        self.game = _make_game("ch-val-game")
        self.user = _make_user("ch-val-editor")
        self.parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )

    def test_valid_scores(self):
        cp = ChallengeProfile.objects.create(
            classification=self.parent, **_valid_challenge_kwargs()
        )
        self.assertEqual(cp.micro_score, 50)

    def test_zero_heavy_valid(self):
        cp = ChallengeProfile.objects.create(
            classification=self.parent, micro_score=100, mystiko_score=0, macro_score=0
        )
        self.assertEqual(cp.micro_score + cp.mystiko_score + cp.macro_score, 100)

    def test_total_99_rejected(self):
        cp = ChallengeProfile(
            classification=self.parent, **_valid_challenge_kwargs(macro=29)
        )
        with self.assertRaises(ValidationError):
            cp.full_clean()

    def test_total_101_rejected(self):
        cp = ChallengeProfile(
            classification=self.parent, **_valid_challenge_kwargs(mystiko=21)
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
            classification=self.parent, micro_score=101, mystiko_score=0, macro_score=-1
        )
        with self.assertRaises(ValidationError):
            cp.full_clean()

    def test_boolean_micro_rejected(self):
        cp = ChallengeProfile(
            classification=self.parent,
            micro_score=True,
            mystiko_score=50,
            macro_score=49,
        )
        with self.assertRaises(ValidationError) as cm:
            cp.full_clean()
        self.assertIn("Challenge Micro", str(cm.exception))

    def test_boolean_mystiko_rejected(self):
        cp = ChallengeProfile(
            classification=self.parent,
            micro_score=50,
            mystiko_score=False,
            macro_score=50,
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


# ---------------------------------------------------------------------------
# Challenge profile — database totals
# ---------------------------------------------------------------------------


class ChallengeProfileDbTotalsTests(TestCase):
    """Persist without full_clean() — DB total constraint enforced."""

    def setUp(self):
        self.game = _make_game("ch-db-game")
        self.user = _make_user("ch-db-user")
        self.parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )

    def test_total_99_db_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent,
                    micro_score=50,
                    mystiko_score=20,
                    macro_score=29,
                )

    def test_total_101_db_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent,
                    micro_score=50,
                    mystiko_score=21,
                    macro_score=30,
                )

    def test_range_valid_but_wrong_total_40_40_40_db_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent,
                    micro_score=40,
                    mystiko_score=40,
                    macro_score=40,
                )

    def test_valid_100_0_0_db_accepted(self):
        ChallengeProfile.objects.create(
            classification=self.parent, micro_score=100, mystiko_score=0, macro_score=0
        )
        self.assertEqual(ChallengeProfile.objects.count(), 1)

    def test_valid_33_33_34_db_accepted(self):
        ChallengeProfile.objects.create(
            classification=self.parent, micro_score=33, mystiko_score=33, macro_score=34
        )
        self.assertEqual(ChallengeProfile.objects.count(), 1)

    def test_range_violation_db_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent,
                    micro_score=101,
                    mystiko_score=0,
                    macro_score=-1,
                )


# ---------------------------------------------------------------------------
# Reward profile — validation
# ---------------------------------------------------------------------------


class RewardProfileValidationTests(TestCase):
    def setUp(self):
        self.game = _make_game("rw-val-game")
        self.user = _make_user("rw-val-editor")
        self.parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )

    def test_valid_scores(self):
        rp = RewardProfile.objects.create(
            classification=self.parent, **_valid_reward_kwargs()
        )
        self.assertEqual(rp.micro_score, 10)

    def test_zero_heavy_valid(self):
        rp = RewardProfile.objects.create(
            classification=self.parent, micro_score=0, mystiko_score=100, macro_score=0
        )
        self.assertEqual(rp.micro_score + rp.mystiko_score + rp.macro_score, 100)

    def test_total_99_rejected(self):
        rp = RewardProfile(classification=self.parent, **_valid_reward_kwargs(macro=59))
        with self.assertRaises(ValidationError):
            rp.full_clean()

    def test_total_101_rejected(self):
        rp = RewardProfile(
            classification=self.parent, **_valid_reward_kwargs(mystiko=31)
        )
        with self.assertRaises(ValidationError):
            rp.full_clean()

    def test_negative_rejected(self):
        rp = RewardProfile(
            classification=self.parent, micro_score=-5, mystiko_score=50, macro_score=55
        )
        with self.assertRaises(ValidationError):
            rp.full_clean()

    def test_boolean_micro_rejected(self):
        rp = RewardProfile(
            classification=self.parent,
            micro_score=True,
            mystiko_score=0,
            macro_score=99,
        )
        with self.assertRaises(ValidationError) as cm:
            rp.full_clean()
        self.assertIn("Reward Micro", str(cm.exception))

    def test_boolean_macro_rejected(self):
        rp = RewardProfile(
            classification=self.parent,
            micro_score=50,
            mystiko_score=50,
            macro_score=False,
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


# ---------------------------------------------------------------------------
# Reward profile — database totals
# ---------------------------------------------------------------------------


class RewardProfileDbTotalsTests(TestCase):
    """Persist without full_clean() — DB total constraint enforced."""

    def setUp(self):
        self.game = _make_game("rw-db-game")
        self.user = _make_user("rw-db-user")
        self.parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )

    def test_total_99_db_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=self.parent,
                    micro_score=10,
                    mystiko_score=30,
                    macro_score=59,
                )

    def test_total_101_db_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=self.parent,
                    micro_score=10,
                    mystiko_score=31,
                    macro_score=60,
                )

    def test_range_valid_but_wrong_total_40_40_40_db_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=self.parent,
                    micro_score=40,
                    mystiko_score=40,
                    macro_score=40,
                )

    def test_valid_100_0_0_db_accepted(self):
        RewardProfile.objects.create(
            classification=self.parent, micro_score=100, mystiko_score=0, macro_score=0
        )
        self.assertEqual(RewardProfile.objects.count(), 1)

    def test_valid_33_33_34_db_accepted(self):
        RewardProfile.objects.create(
            classification=self.parent, micro_score=33, mystiko_score=33, macro_score=34
        )
        self.assertEqual(RewardProfile.objects.count(), 1)


# ---------------------------------------------------------------------------
# Boolean rejection — post-construction assignment
# ---------------------------------------------------------------------------


class PostConstructionBooleanTests(TestCase):
    """Boolean values assigned after construction are rejected in clean_fields."""

    def setUp(self):
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="BoolAssign",
            slug="bool-assign",
        )
        self.user = User.objects.create_user(username="bool_assign_u", password="test")
        self.parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )

    def test_challenge_bool_assigned_after_construction(self):
        cp = ChallengeProfile(
            classification=self.parent, micro_score=50, mystiko_score=50, macro_score=0
        )
        cp.micro_score = True
        with self.assertRaises(ValidationError) as cm:
            cp.full_clean()
        self.assertIn("Challenge Micro", str(cm.exception))

    def test_challenge_bool_each_field(self):
        for attr in ("micro_score", "mystiko_score", "macro_score"):
            cp = ChallengeProfile(
                classification=self.parent,
                micro_score=34,
                mystiko_score=33,
                macro_score=33,
            )
            setattr(cp, attr, False)
            with self.assertRaises(ValidationError, msg=f"{attr} not rejected"):
                cp.full_clean()

    def test_reward_bool_assigned_after_construction(self):
        rp = RewardProfile(
            classification=self.parent, micro_score=50, mystiko_score=50, macro_score=0
        )
        rp.macro_score = False
        with self.assertRaises(ValidationError) as cm:
            rp.full_clean()
        self.assertIn("Reward Macro", str(cm.exception))

    def test_reward_bool_each_field(self):
        for attr in ("micro_score", "mystiko_score", "macro_score"):
            rp = RewardProfile(
                classification=self.parent,
                micro_score=34,
                mystiko_score=33,
                macro_score=33,
            )
            setattr(rp, attr, True)
            with self.assertRaises(ValidationError, msg=f"{attr} not rejected"):
                rp.full_clean()


# ---------------------------------------------------------------------------
# No-network — model and service
# ---------------------------------------------------------------------------


class NoNetworkModelTests(TestCase):
    """Model construction, clean, and save make no Steam calls."""

    def setUp(self):
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="NoNetM", slug="nonet-m"
        )
        self.user = User.objects.create_user(username="nonet_m_u", password="test")
        self.parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )
        self._guard = patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("SteamClient must not be called"),
        )

    def test_construction_no_steam(self):
        with self._guard:
            c = EditorialClassification(game=self.game, updated_by=self.user)
            self.assertIsNotNone(c)

    def test_challenge_full_clean_no_steam(self):
        with self._guard:
            cp = ChallengeProfile(
                classification=self.parent,
                micro_score=50,
                mystiko_score=20,
                macro_score=30,
            )
            cp.full_clean()

    def test_reward_full_clean_no_steam(self):
        with self._guard:
            rp = RewardProfile(
                classification=self.parent,
                micro_score=10,
                mystiko_score=30,
                macro_score=60,
            )
            rp.full_clean()

    def test_profile_save_no_steam(self):
        with self._guard:
            cp = ChallengeProfile.objects.create(
                classification=self.parent,
                micro_score=50,
                mystiko_score=20,
                macro_score=30,
            )
            self.assertIsNotNone(cp.pk)

    def test_str_no_steam(self):
        with self._guard:
            s = str(self.parent)
            self.assertIn("NoNetM", s)

    def test_service_create_no_steam(self):
        from classifications.services.editorial import (
            ScoreDistribution,
            set_editorial_classification,
        )

        with self._guard:
            result = set_editorial_classification(
                game=self.game,
                updated_by=self.user,
                challenge=ScoreDistribution(micro=50, mystiko=20, macro=30),
                reward=ScoreDistribution(micro=10, mystiko=30, macro=60),
            )
            self.assertIsNotNone(result.pk)

    def test_service_update_no_steam(self):
        from classifications.services.editorial import (
            ScoreDistribution,
            set_editorial_classification,
        )

        with self._guard:
            result = set_editorial_classification(
                game=self.game,
                updated_by=self.user,
                challenge=ScoreDistribution(micro=30, mystiko=40, macro=30),
                reward=ScoreDistribution(micro=20, mystiko=20, macro=60),
            )
            self.assertIsNotNone(result.pk)
