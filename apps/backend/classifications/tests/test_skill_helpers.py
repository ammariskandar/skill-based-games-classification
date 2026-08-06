"""
Skill helper tests — SBGC-49.

Pure dominant-skill-category logic and model properties.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase
from games.models import Game, SourceType

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
)
from classifications.skills import (
    EditorialProfile,
    SkillCategory,
    dominant_skill_category,
)

# ---------------------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------------------


class DominantSkillCategoryTests(TestCase):
    def test_unique_micro_wins(self):
        self.assertEqual(
            dominant_skill_category(micro_score=60, mystiko_score=20, macro_score=20),
            SkillCategory.MICRO,
        )

    def test_unique_mystiko_wins(self):
        self.assertEqual(
            dominant_skill_category(micro_score=20, mystiko_score=60, macro_score=20),
            SkillCategory.MYSTIKO,
        )

    def test_unique_macro_wins(self):
        self.assertEqual(
            dominant_skill_category(micro_score=20, mystiko_score=20, macro_score=60),
            SkillCategory.MACRO,
        )

    def test_two_way_tie_returns_none(self):
        self.assertIsNone(
            dominant_skill_category(micro_score=50, mystiko_score=50, macro_score=0)
        )

    def test_three_way_tie_returns_none(self):
        # 34/34/32 has a two-way tie at 34 — no unique winner.
        self.assertIsNone(
            dominant_skill_category(micro_score=34, mystiko_score=34, macro_score=32)
        )

    def test_all_zero_not_valid(self):
        """0/0/0 does not total 100 — rejected by validator."""
        with self.assertRaises(ValidationError):
            dominant_skill_category(micro_score=0, mystiko_score=0, macro_score=0)

    def test_bool_rejected(self):
        with self.assertRaises(ValidationError):
            dominant_skill_category(micro_score=True, mystiko_score=50, macro_score=49)

    def test_float_rejected(self):
        with self.assertRaises(ValidationError):
            dominant_skill_category(
                micro_score=50.5, mystiko_score=25, macro_score=24.5
            )

    def test_out_of_range_rejected(self):
        with self.assertRaises(ValidationError):
            dominant_skill_category(micro_score=101, mystiko_score=0, macro_score=-1)

    def test_wrong_total_rejected(self):
        with self.assertRaises(ValidationError):
            dominant_skill_category(micro_score=50, mystiko_score=20, macro_score=20)

    def test_extreme_100_0_0(self):
        self.assertEqual(
            dominant_skill_category(micro_score=100, mystiko_score=0, macro_score=0),
            SkillCategory.MICRO,
        )


# ---------------------------------------------------------------------------
# Model properties
# ---------------------------------------------------------------------------


class ModelPropertyTests(TestCase):
    def setUp(self):
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="Prop", slug="prop"
        )
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(username="prop_u", password="p")
        self.parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )

    def test_challenge_unique_micro(self):
        cp = ChallengeProfile.objects.create(
            classification=self.parent, micro_score=70, mystiko_score=20, macro_score=10
        )
        self.assertEqual(cp.dominant_skill_category, SkillCategory.MICRO)

    def test_challenge_tie_returns_none(self):
        cp = ChallengeProfile.objects.create(
            classification=self.parent, micro_score=50, mystiko_score=50, macro_score=0
        )
        self.assertIsNone(cp.dominant_skill_category)

    def test_reward_unique_macro(self):
        rp = RewardProfile.objects.create(
            classification=self.parent, micro_score=10, mystiko_score=20, macro_score=70
        )
        self.assertEqual(rp.dominant_skill_category, SkillCategory.MACRO)

    def test_reward_tie_returns_none(self):
        # 34/34/32 — micro and mystiko tie at 34.
        rp = RewardProfile.objects.create(
            classification=self.parent, micro_score=34, mystiko_score=34, macro_score=32
        )
        self.assertIsNone(rp.dominant_skill_category)

    def test_challenge_and_reward_independent(self):
        cp = ChallengeProfile.objects.create(
            classification=self.parent, micro_score=70, mystiko_score=20, macro_score=10
        )
        rp = RewardProfile.objects.create(
            classification=self.parent, micro_score=10, mystiko_score=20, macro_score=70
        )
        self.assertEqual(cp.dominant_skill_category, SkillCategory.MICRO)
        self.assertEqual(rp.dominant_skill_category, SkillCategory.MACRO)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class EnumTests(TestCase):
    def test_skill_category_values(self):
        self.assertEqual(
            set(SkillCategory.values),
            {"micro", "mystiko", "macro"},
        )

    def test_editorial_profile_values(self):
        self.assertEqual(
            set(EditorialProfile.values),
            {"challenge", "reward"},
        )
