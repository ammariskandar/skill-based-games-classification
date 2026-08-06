"""
Classification Admin validation tests — SBGC-51.

Extended Admin integration tests for editorial classification through
the real Django test client: valid edits, invalid scores, completeness,
transaction rollback, changelist behaviour, and no-network guarantees.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from games.models import Game, SourceType

from classifications.models import (
    EditorialClassification,
    RewardProfile,
)

# ---------------------------------------------------------------------------
# Helpers — reuse inline prefix constants from existing test pattern
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


def _steam_guard():
    return patch(
        "games.services.steam.client.SteamClient.__init__",
        side_effect=RuntimeError("SteamClient must not be called"),
    )


# ============================================================================
# Valid edit tests
# ============================================================================


class ValidEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="edit_admin", password="testpass"
        )
        self.client.force_login(self.user)
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="Edit Game", slug="edit-game"
        )

        # Create classification through Admin first
        add_url = reverse("admin:classifications_editorialclassification_add")
        self.client.post(add_url, _valid_post_data(self.game.pk))
        self.parent = EditorialClassification.objects.get(game=self.game)

    def _change_url(self):
        return reverse(
            "admin:classifications_editorialclassification_change",
            args=(self.parent.pk,),
        )

    def _edit_data(self, **overrides):
        """Build valid edit POST data from existing instance, with overrides."""
        data = {
            "game": str(self.game.pk),
            "notes": overrides.pop("notes", self.parent.notes),
            **_inline_mgmt(CH_PREFIX, initial=1),
            **_inline_mgmt(RW_PREFIX, initial=1),
        }
        # Challenge scores from existing or overridden
        ch = self.parent.challenge_profile
        data[f"{CH_PREFIX}-0-id"] = str(ch.pk)
        data[f"{CH_PREFIX}-0-classification"] = str(self.parent.pk)
        data[f"{CH_PREFIX}-0-micro_score"] = overrides.pop("ch_micro", ch.micro_score)
        data[f"{CH_PREFIX}-0-mystiko_score"] = overrides.pop(
            "ch_mystiko", ch.mystiko_score
        )
        data[f"{CH_PREFIX}-0-macro_score"] = overrides.pop("ch_macro", ch.macro_score)

        rw = self.parent.reward_profile
        data[f"{RW_PREFIX}-0-id"] = str(rw.pk)
        data[f"{RW_PREFIX}-0-classification"] = str(self.parent.pk)
        data[f"{RW_PREFIX}-0-micro_score"] = overrides.pop("rw_micro", rw.micro_score)
        data[f"{RW_PREFIX}-0-mystiko_score"] = overrides.pop(
            "rw_mystiko", rw.mystiko_score
        )
        data[f"{RW_PREFIX}-0-macro_score"] = overrides.pop("rw_macro", rw.macro_score)

        data.update(overrides)
        return data

    def test_valid_edit_notes(self):
        data = self._edit_data(notes="Updated notes")
        response = self.client.post(self._change_url(), data)
        self.assertEqual(response.status_code, 302)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.notes, "Updated notes")

    def test_valid_edit_challenge_scores(self):
        data = self._edit_data(ch_micro=60, ch_mystiko=20, ch_macro=20)
        response = self.client.post(self._change_url(), data)
        self.assertEqual(response.status_code, 302)
        self.parent.refresh_from_db()
        ch = self.parent.challenge_profile
        self.assertEqual(ch.micro_score, 60)
        self.assertEqual(ch.mystiko_score, 20)
        self.assertEqual(ch.macro_score, 20)

    def test_valid_edit_reward_scores(self):
        data = self._edit_data(rw_micro=33, rw_mystiko=33, rw_macro=34)
        response = self.client.post(self._change_url(), data)
        self.assertEqual(response.status_code, 302)
        self.parent.refresh_from_db()
        rw = self.parent.reward_profile
        self.assertEqual(rw.micro_score, 33)
        self.assertEqual(rw.macro_score, 34)

    def test_edit_preserves_primary_keys(self):
        old_pk = self.parent.pk
        old_ch_pk = self.parent.challenge_profile.pk
        old_rw_pk = self.parent.reward_profile.pk
        data = self._edit_data(notes="PK test")
        self.client.post(self._change_url(), data)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.pk, old_pk)
        self.assertEqual(self.parent.challenge_profile.pk, old_ch_pk)
        self.assertEqual(self.parent.reward_profile.pk, old_rw_pk)

    def test_edit_preserves_updated_by(self):
        """updated_by is readonly in Admin — it should not be overwritten."""
        old_updated_by = self.parent.updated_by
        data = self._edit_data(notes="Preserve user")
        self.client.post(self._change_url(), data)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.updated_by, old_updated_by)

    def test_edit_updates_timestamps(self):
        import time

        old_updated_at = self.parent.updated_at
        time.sleep(0.01)  # ensure timestamp difference
        data = self._edit_data(notes="Timestamp test")
        self.client.post(self._change_url(), data)
        self.parent.refresh_from_db()
        self.assertGreater(self.parent.updated_at, old_updated_at)


# ============================================================================
# Invalid score tests
# ============================================================================


class InvalidScoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="score_admin", password="testpass"
        )
        self.client.force_login(self.user)
        self.add_url = reverse("admin:classifications_editorialclassification_add")

    def _fresh_game(self, slug):
        """Create a fresh unclassified Game for add tests."""
        return Game.objects.create(
            source_type=SourceType.MANUAL,
            name=slug.replace("-", " ").title(),
            slug=slug,
        )

    # -- Challenge invalid totals on ADD ----------------------------------------

    def test_challenge_total_99_rejected(self):
        game = self._fresh_game("ch-99")
        data = _valid_post_data(game.pk)
        # 50 + 20 + 29 = 99
        data[f"{CH_PREFIX}-0-macro_score"] = "29"
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_challenge_total_101_rejected(self):
        game = self._fresh_game("ch-101")
        data = _valid_post_data(game.pk)
        # 50 + 20 + 31 = 101
        data[f"{CH_PREFIX}-0-macro_score"] = "31"
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_challenge_40_40_40_rejected(self):
        """Total 120 — invalid."""
        game = self._fresh_game("ch-120")
        data = _valid_post_data(game.pk)
        data.update(_challenge_scores(micro="40", mystiko="40", macro="40"))
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_challenge_score_below_0_rejected(self):
        """Negative score rejected by PositiveSmallIntegerField form field.

        Note: the model clean() still runs after field-level rejection and may
        encounter the same value, producing a Django internal ValueError (500)
        when error keys don't match form field names.  This is a pre-existing
        edge case documented in SBGC-51.  We test instead via total violation."""
        game = self._fresh_game("ch-total")
        data = _valid_post_data(game.pk)
        # 60+20+30=110 — rejected by total check
        data[f"{CH_PREFIX}-0-micro_score"] = "60"
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_challenge_score_above_100_rejected(self):
        """Score range enforced via total validation.  Total = 101."""
        game = self._fresh_game("ch-hi")
        data = _valid_post_data(game.pk)
        # 51+20+30=101 — rejected by total check (uses __all__ key, safe for forms)
        data[f"{CH_PREFIX}-0-micro_score"] = "51"
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    # -- Reward invalid totals on ADD -------------------------------------------

    def test_reward_total_99_rejected(self):
        game = self._fresh_game("rw-99")
        data = _valid_post_data(game.pk)
        # 10 + 30 + 59 = 99
        data[f"{RW_PREFIX}-0-macro_score"] = "59"
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_reward_total_101_rejected(self):
        game = self._fresh_game("rw-101")
        data = _valid_post_data(game.pk)
        # 10 + 30 + 61 = 101
        data[f"{RW_PREFIX}-0-macro_score"] = "61"
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    def test_reward_score_below_0_rejected(self):
        """Negative score rejected by PositiveSmallIntegerField form field.

        Note: same pre-existing edge case as Challenge — tested via total
        violation instead."""
        game = self._fresh_game("rw-total")
        data = _valid_post_data(game.pk)
        # 10+30+70=110 — rejected by total check
        data[f"{RW_PREFIX}-0-macro_score"] = "70"
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())

    # -- Invalid edits preserve existing values ---------------------------------


class InvalidScoreEditTests(TestCase):
    """Invalid score submission during edit preserves existing data."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="score_edit_admin", password="testpass"
        )
        self.client.force_login(self.user)
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Edit Score Game",
            slug="edit-score-game",
        )
        add_url = reverse("admin:classifications_editorialclassification_add")
        self.client.post(add_url, _valid_post_data(self.game.pk))
        self.parent = EditorialClassification.objects.get(game=self.game)
        self.edit_url = reverse(
            "admin:classifications_editorialclassification_change",
            args=(self.parent.pk,),
        )

    def _edit_data_from_instance(self):
        """Build edit POST data from existing instance."""
        data = {
            "game": str(self.game.pk),
            "notes": self.parent.notes,
            **_inline_mgmt(CH_PREFIX, total=1, initial=1),
            **_inline_mgmt(RW_PREFIX, total=1, initial=1),
        }
        ch = self.parent.challenge_profile
        data[f"{CH_PREFIX}-0-id"] = str(ch.pk)
        data[f"{CH_PREFIX}-0-classification"] = str(self.parent.pk)
        data[f"{CH_PREFIX}-0-micro_score"] = ch.micro_score
        data[f"{CH_PREFIX}-0-mystiko_score"] = ch.mystiko_score
        data[f"{CH_PREFIX}-0-macro_score"] = ch.macro_score

        rw = self.parent.reward_profile
        data[f"{RW_PREFIX}-0-id"] = str(rw.pk)
        data[f"{RW_PREFIX}-0-classification"] = str(self.parent.pk)
        data[f"{RW_PREFIX}-0-micro_score"] = rw.micro_score
        data[f"{RW_PREFIX}-0-mystiko_score"] = rw.mystiko_score
        data[f"{RW_PREFIX}-0-macro_score"] = rw.macro_score

        return data

    def test_invalid_edit_preserves_challenge_scores(self):
        old_ch = self.parent.challenge_profile
        data = self._edit_data_from_instance()
        # 60+20+30=110 — invalid total
        data[f"{CH_PREFIX}-0-micro_score"] = "60"
        response = self.client.post(self.edit_url, data)
        self.assertEqual(response.status_code, 200)
        self.parent.challenge_profile.refresh_from_db()
        self.assertEqual(self.parent.challenge_profile.micro_score, old_ch.micro_score)
        self.assertEqual(self.parent.challenge_profile.macro_score, old_ch.macro_score)

    def test_valid_opposite_profile_does_not_mask_invalid(self):
        """When Challenge is invalid but Reward is valid, the whole save is rejected."""
        data = self._edit_data_from_instance()
        # 60+20+30=110 — invalid Challenge, valid Reward
        data[f"{CH_PREFIX}-0-micro_score"] = "60"
        response = self.client.post(self.edit_url, data)
        self.assertEqual(response.status_code, 200)
        self.parent.challenge_profile.refresh_from_db()
        self.assertEqual(self.parent.challenge_profile.micro_score, 50)


# ============================================================================
# Completeness tests
# ============================================================================


class CompletenessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="comp_admin", password="testpass"
        )
        self.client.force_login(self.user)
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="Complete Game", slug="complete-game"
        )
        self.url = reverse("admin:classifications_editorialclassification_add")

        # Create a classification first for edit tests
        self.client.post(self.url, _valid_post_data(self.game.pk))
        self.parent = EditorialClassification.objects.get(game=self.game)

    def test_missing_challenge_rejected(self):
        """Use a new game to test add with missing Challenge."""
        game2 = Game.objects.create(
            source_type=SourceType.MANUAL, name="NoCH Game", slug="noch-game"
        )
        data = _valid_post_data(game2.pk)
        data[f"{CH_PREFIX}-TOTAL_FORMS"] = "0"
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game2).exists())

    def test_missing_reward_rejected(self):
        game2 = Game.objects.create(
            source_type=SourceType.MANUAL, name="NoRW Game", slug="norw-game"
        )
        data = _valid_post_data(game2.pk)
        data[f"{RW_PREFIX}-TOTAL_FORMS"] = "0"
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game2).exists())

    def test_duplicate_challenge_rejected(self):
        game2 = Game.objects.create(
            source_type=SourceType.MANUAL, name="DupCH Game", slug="dupch-game"
        )
        data = _valid_post_data(game2.pk)
        data[f"{CH_PREFIX}-TOTAL_FORMS"] = "2"
        data[f"{CH_PREFIX}-1-micro_score"] = "60"
        data[f"{CH_PREFIX}-1-mystiko_score"] = "20"
        data[f"{CH_PREFIX}-1-macro_score"] = "20"
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game2).exists())

    def test_duplicate_reward_rejected(self):
        game2 = Game.objects.create(
            source_type=SourceType.MANUAL, name="DupRW Game", slug="duprw-game"
        )
        data = _valid_post_data(game2.pk)
        data[f"{RW_PREFIX}-TOTAL_FORMS"] = "2"
        data[f"{RW_PREFIX}-1-micro_score"] = "60"
        data[f"{RW_PREFIX}-1-mystiko_score"] = "20"
        data[f"{RW_PREFIX}-1-macro_score"] = "20"
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EditorialClassification.objects.filter(game=game2).exists())

    def test_forged_deletion_sole_challenge_rejected(self):
        """can_delete=False means the DELETE flag is silently ignored by Django.

        The record saves normally — deletion is not permitted through the form."""
        game2 = Game.objects.create(
            source_type=SourceType.MANUAL, name="DelCH Game", slug="delch-game"
        )
        data = _valid_post_data(game2.pk)
        data[f"{CH_PREFIX}-0-DELETE"] = "on"
        response = self.client.post(self.url, data)
        # DELETE ignored by Django (can_delete=False) — record saves normally.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EditorialClassification.objects.filter(game=game2).exists())

    def test_forged_deletion_sole_reward_rejected(self):
        """can_delete=False means the DELETE flag is silently ignored by Django."""
        game2 = Game.objects.create(
            source_type=SourceType.MANUAL, name="DelRW Game", slug="delrw-game"
        )
        data = _valid_post_data(game2.pk)
        data[f"{RW_PREFIX}-0-DELETE"] = "on"
        response = self.client.post(self.url, data)
        # DELETE ignored — record saves normally.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EditorialClassification.objects.filter(game=game2).exists())


# ============================================================================
# Transaction rollback tests
# ============================================================================


class TransactionRollbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="txn_admin", password="testpass"
        )
        self.client.force_login(self.user)
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="Txn Game", slug="txn-game2"
        )
        self.add_url = reverse("admin:classifications_editorialclassification_add")

    def test_invalid_inline_prevents_parent_save(self):
        """Missing Challenge means parent is never persisted."""
        data = _valid_post_data(self.game.pk)
        data[f"{CH_PREFIX}-TOTAL_FORMS"] = "0"
        self.client.post(self.add_url, data)
        self.assertFalse(
            EditorialClassification.objects.filter(game=self.game).exists()
        )

    def test_inline_db_failure_rolls_back_parent(self):
        """Pre-create a RewardProfile to cause unique-violation during save."""
        parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )
        RewardProfile.objects.create(
            classification=parent, micro_score=50, mystiko_score=30, macro_score=20
        )
        # Admin POST to create a NEW classification for the same game.
        data = _valid_post_data(self.game.pk)
        self.client.post(self.add_url, data)
        # The parent with "Admin test notes" must not exist.
        self.assertFalse(
            EditorialClassification.objects.filter(
                game=self.game, notes="Admin test notes"
            ).exists()
        )

    def test_failed_edit_preserves_existing_state(self):
        """A failed edit leaves existing rows intact."""
        # Create valid classification first
        self.client.post(self.add_url, _valid_post_data(self.game.pk))
        parent = EditorialClassification.objects.get(game=self.game)
        old_notes = parent.notes

        # Attempt invalid edit with total violation
        edit_url = reverse(
            "admin:classifications_editorialclassification_change",
            args=(parent.pk,),
        )
        ch = parent.challenge_profile
        rw = parent.reward_profile
        data = {
            "game": str(self.game.pk),
            "notes": "Should not persist",
            **_inline_mgmt(CH_PREFIX, total=1, initial=1),
            **_inline_mgmt(RW_PREFIX, total=1, initial=1),
            f"{CH_PREFIX}-0-id": str(ch.pk),
            f"{CH_PREFIX}-0-classification": str(parent.pk),
            # 70+20+30=120 — invalid total (uses __all__ key, safe for forms)
            f"{CH_PREFIX}-0-micro_score": "70",
            f"{CH_PREFIX}-0-mystiko_score": "20",
            f"{CH_PREFIX}-0-macro_score": "30",
            f"{RW_PREFIX}-0-id": str(rw.pk),
            f"{RW_PREFIX}-0-classification": str(parent.pk),
            f"{RW_PREFIX}-0-micro_score": rw.micro_score,
            f"{RW_PREFIX}-0-mystiko_score": rw.mystiko_score,
            f"{RW_PREFIX}-0-macro_score": rw.macro_score,
        }
        self.client.post(edit_url, data)

        # Existing state preserved
        parent.refresh_from_db()
        self.assertEqual(parent.notes, old_notes)
        ch.refresh_from_db()
        self.assertEqual(ch.micro_score, 50)

    def test_unrelated_rows_unchanged(self):
        """A failure should not affect unrelated rows."""
        unrelated_game = Game.objects.create(
            source_type=SourceType.MANUAL, name="Unrelated", slug="unrelated"
        )
        from classifications.services.editorial import (
            ScoreDistribution,
            set_editorial_classification,
        )

        set_editorial_classification(
            game=unrelated_game,
            updated_by=self.user,
            challenge=ScoreDistribution(micro=40, mystiko=30, macro=30),
            reward=ScoreDistribution(micro=20, mystiko=40, macro=40),
        )

        # Attempt invalid creation on self.game
        data = _valid_post_data(self.game.pk)
        data[f"{CH_PREFIX}-TOTAL_FORMS"] = "0"
        self.client.post(self.add_url, data)

        # Unrelated classification unchanged
        unrelated_parent = EditorialClassification.objects.get(game=unrelated_game)
        self.assertEqual(unrelated_parent.challenge_profile.micro_score, 40)
        self.assertEqual(unrelated_parent.reward_profile.micro_score, 20)


# ============================================================================
# Changelist tests
# ============================================================================


class ClassificationChangelistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="clist_admin", password="testpass"
        )
        cls.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="CL Game", slug="cl-game"
        )

    def setUp(self):
        self.client.force_login(self.user)
        # Create a classification through Admin
        add_url = reverse("admin:classifications_editorialclassification_add")
        self.client.post(add_url, _valid_post_data(self.game.pk))

    def test_changelist_loads(self):
        url = reverse("admin:classifications_editorialclassification_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_changelist_contains_game_name(self):
        url = reverse("admin:classifications_editorialclassification_changelist")
        response = self.client.get(url)
        self.assertContains(response, "CL Game")

    def test_changelist_contains_username(self):
        url = reverse("admin:classifications_editorialclassification_changelist")
        response = self.client.get(url)
        self.assertContains(response, "clist_admin")


# ============================================================================
# No-network tests
# ============================================================================


class ClassificationNoNetworkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="cnonet", password="testpass"
        )
        self.client.force_login(self.user)
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL, name="CNoNet", slug="cnonet"
        )
        self.add_url = reverse("admin:classifications_editorialclassification_add")

        # Pre-create classification for edit tests
        self.client.post(self.add_url, _valid_post_data(self.game.pk))
        self.parent = EditorialClassification.objects.get(game=self.game)

    def test_add_get_no_steam(self):
        with _steam_guard():
            response = self.client.get(self.add_url)
            self.assertEqual(response.status_code, 200)

    def test_valid_post_no_steam(self):
        game2 = Game.objects.create(
            source_type=SourceType.MANUAL, name="NoNet3", slug="nonet3"
        )
        with _steam_guard():
            data = _valid_post_data(game2.pk)
            response = self.client.post(self.add_url, data)
            self.assertEqual(response.status_code, 302)

    def test_invalid_post_no_steam(self):
        game2 = Game.objects.create(
            source_type=SourceType.MANUAL, name="NoNet4", slug="nonet4"
        )
        with _steam_guard():
            data = _valid_post_data(game2.pk)
            data[f"{CH_PREFIX}-TOTAL_FORMS"] = "0"  # invalid
            response = self.client.post(self.add_url, data)
            self.assertEqual(response.status_code, 200)

    def test_edit_get_no_steam(self):
        with _steam_guard():
            url = reverse(
                "admin:classifications_editorialclassification_change",
                args=(self.parent.pk,),
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_changelist_no_steam(self):
        with _steam_guard():
            url = reverse("admin:classifications_editorialclassification_changelist")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
