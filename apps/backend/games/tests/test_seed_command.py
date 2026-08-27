"""
Seed command tests — SBGC-50.

Safety, idempotency, corrective rerun, transaction rollback,
no-network, and query-helper smoke.
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
)
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from games.development_data import _SEED_EMAIL, _SEED_USERNAME
from games.models import ContentType, Game, ListingStatus, SourceType

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


class SafetyTests(TestCase):
    def test_disabled_setting_raises_command_error(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=False):
            with self.assertRaises(CommandError):
                call_command("seed_development_data", stdout=StringIO())

    def test_no_writes_before_refusal(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=False):
            try:
                call_command("seed_development_data", stdout=StringIO())
            except CommandError:
                pass
        self.assertEqual(Game.objects.count(), 0)

    def test_no_superuser_created(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
        user = User.objects.get(username=_SEED_USERNAME)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_seed_user_password_unusable(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
        user = User.objects.get(username=_SEED_USERNAME)
        self.assertFalse(user.has_usable_password())

    def test_no_secret_in_output(self):
        out = StringIO()
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=out)
        output = out.getvalue()
        self.assertNotIn("password", output.lower())
        self.assertNotIn("secret", output.lower())
        self.assertNotIn("key", output.lower())


# ---------------------------------------------------------------------------
# First run
# ---------------------------------------------------------------------------


class FirstRunTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())

    def test_seed_editor_created(self):
        user = User.objects.get(username=_SEED_USERNAME)
        self.assertEqual(user.email, _SEED_EMAIL)

    def test_steam_records_exist(self):
        steam = Game.objects.steam()
        self.assertGreaterEqual(steam.count(), 3)

    def test_manual_records_exist(self):
        manual = Game.objects.manual()
        self.assertGreaterEqual(manual.count(), 4)

    def test_public_game_exists(self):
        self.assertGreaterEqual(Game.objects.publicly_listable().count(), 1)

    def test_draft_game_exists(self):
        self.assertTrue(
            Game.objects.filter(listing_status=ListingStatus.DRAFT).exists()
        )

    def test_non_game_content_exists(self):
        self.assertTrue(Game.objects.filter(content_type=ContentType.SOFTWARE).exists())
        self.assertTrue(Game.objects.filter(content_type=ContentType.DEMO).exists())

    def test_manual_metadata_present(self):
        chess = Game.objects.get(slug="chess")
        self.assertIn("board game", chess.description)

    def test_complete_classifications_exist(self):
        qs = EditorialClassification.objects.filter(
            challenge_profile__isnull=False,
            reward_profile__isnull=False,
        )
        self.assertGreaterEqual(qs.count(), 4)

    def test_classification_updated_by(self):
        user = User.objects.get(username=_SEED_USERNAME)
        for c in EditorialClassification.objects.all():
            self.assertEqual(c.updated_by, user)

    def test_profile_totals(self):
        for cp in ChallengeProfile.objects.all():
            self.assertEqual(cp.micro_score + cp.mystiko_score + cp.macro_score, 100)
        for rp in RewardProfile.objects.all():
            self.assertEqual(rp.micro_score + rp.mystiko_score + rp.macro_score, 100)

    def test_notes_persisted(self):
        portal = EditorialClassification.objects.get(game__slug="portal-2")
        self.assertIn("puzzle", portal.notes)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class IdempotencyTests(TestCase):
    def test_double_run_stable_counts(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
            game_count = Game.objects.count()
            class_count = EditorialClassification.objects.count()
            ch_count = ChallengeProfile.objects.count()
            rw_count = RewardProfile.objects.count()
            user_count = User.objects.count()

            call_command("seed_development_data", stdout=StringIO())

            self.assertEqual(Game.objects.count(), game_count)
            self.assertEqual(EditorialClassification.objects.count(), class_count)
            self.assertEqual(ChallengeProfile.objects.count(), ch_count)
            self.assertEqual(RewardProfile.objects.count(), rw_count)
            self.assertEqual(User.objects.count(), user_count)

    def test_double_run_stable_pks(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
            pks_before = set(Game.objects.values_list("pk", flat=True))
            call_command("seed_development_data", stdout=StringIO())
            pks_after = set(Game.objects.values_list("pk", flat=True))
            self.assertEqual(pks_before, pks_after)


# ---------------------------------------------------------------------------
# Corrective rerun
# ---------------------------------------------------------------------------


class CorrectiveRerunTests(TestCase):
    def setUp(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())

    def test_restores_game_fields(self):
        g = Game.objects.get(slug="chess")
        g.name = "Modified"
        g.listing_status = ListingStatus.ARCHIVED
        g.save()
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
        g.refresh_from_db()
        self.assertEqual(g.name, "Chess")
        self.assertEqual(g.listing_status, ListingStatus.PUBLISHED)

    def test_restores_manual_metadata(self):
        g = Game.objects.get(slug="chess")
        g.description = "Wrong"
        g.save()
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
        g.refresh_from_db()
        self.assertIn("board game", g.description)

    def test_restores_classification_notes(self):
        c = EditorialClassification.objects.get(game__slug="portal-2")
        c.notes = "Wrong notes"
        c.save()
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
        c.refresh_from_db()
        self.assertIn("puzzle", c.notes)

    def test_restores_challenge_scores(self):
        c = EditorialClassification.objects.get(game__slug="hades")
        c.challenge_profile.micro_score = 99
        c.challenge_profile.mystiko_score = 1
        c.challenge_profile.macro_score = 0
        c.challenge_profile.save()
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
        c.refresh_from_db()
        self.assertEqual(c.challenge_profile.micro_score, 60)

    def test_restores_reward_scores(self):
        c = EditorialClassification.objects.get(game__slug="hades")
        c.reward_profile.micro_score = 99
        c.reward_profile.mystiko_score = 1
        c.reward_profile.macro_score = 0
        c.reward_profile.save()
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
        c.refresh_from_db()
        self.assertEqual(c.reward_profile.micro_score, 20)

    def test_restores_seed_user_email(self):
        user = User.objects.get(username=_SEED_USERNAME)
        user.email = "wrong@example.com"
        user.save()
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
        user.refresh_from_db()
        self.assertEqual(user.email, _SEED_EMAIL)


# ---------------------------------------------------------------------------
# Unrelated data preservation
# ---------------------------------------------------------------------------


class UnrelatedDataTests(TestCase):
    def setUp(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())

    def test_unrelated_data_preserved(self):
        User.objects.create_user(username="other-user", password="p")
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Other Game",
            slug="other-game",
        )
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())
        self.assertTrue(User.objects.filter(username="other-user").exists())
        self.assertTrue(Game.objects.filter(slug="other-game").exists())


# ---------------------------------------------------------------------------
# Transaction rollback
# ---------------------------------------------------------------------------


class TransactionRollbackTests(TestCase):
    def test_rollback_on_failure(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            with patch(
                "games.development_data._seed_one_game",
                side_effect=RuntimeError("simulated"),
            ):
                with self.assertRaises(RuntimeError):
                    call_command("seed_development_data", stdout=StringIO())
        # Nothing persisted.
        self.assertEqual(Game.objects.count(), 0)
        self.assertEqual(User.objects.count(), 0)


# ---------------------------------------------------------------------------
# No network
# ---------------------------------------------------------------------------


class NoNetworkTests(TestCase):
    def _steam_guard(self):
        return patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("SteamClient must not be called"),
        )

    def test_command_no_steam(self):
        with self._steam_guard():
            with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
                call_command("seed_development_data", stdout=StringIO())


# ---------------------------------------------------------------------------
# Query-helper smoke
# ---------------------------------------------------------------------------


class QueryHelperSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=StringIO())

    def test_publicly_listable_returns_results(self):
        self.assertGreater(Game.objects.publicly_listable().count(), 0)

    def test_steam_returns_results(self):
        self.assertGreater(Game.objects.steam().count(), 0)

    def test_manual_returns_results(self):
        self.assertGreater(Game.objects.manual().count(), 0)


# ---------------------------------------------------------------------------
# Production refusal (subprocess)
# ---------------------------------------------------------------------------


class ProductionRefusalTests(TestCase):
    """The command refuses to run under production settings."""

    def test_production_setting_refuses(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=False):
            with self.assertRaises(CommandError) as cm:
                call_command("seed_development_data", stdout=StringIO())
            self.assertIn("DEVELOPMENT_SEEDING_ENABLED", str(cm.exception))
            self.assertEqual(Game.objects.count(), 0)
            self.assertFalse(User.objects.filter(username=_SEED_USERNAME).exists())


# ---------------------------------------------------------------------------
# Seed-user conflict handling
# ---------------------------------------------------------------------------


class SeedUserConflictTests(TestCase):
    def test_privileged_user_rejected(self):
        User.objects.create_superuser(
            username=_SEED_USERNAME,
            email="admin@example.com",
            password="secret123",
        )
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            with self.assertRaises(CommandError):
                call_command("seed_development_data", stdout=StringIO())
        user = User.objects.get(username=_SEED_USERNAME)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "admin@example.com")
        self.assertEqual(Game.objects.count(), 0)

    def test_staff_user_rejected(self):
        User.objects.create_user(
            username=_SEED_USERNAME,
            email="staff@example.com",
            password="secret123",
            is_staff=True,
        )
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            with self.assertRaises(CommandError):
                call_command("seed_development_data", stdout=StringIO())
        user = User.objects.get(username=_SEED_USERNAME)
        self.assertTrue(user.is_staff)
        self.assertEqual(Game.objects.count(), 0)


# ---------------------------------------------------------------------------
# Game conflict handling
# ---------------------------------------------------------------------------


class GameConflictTests(TestCase):
    def test_steam_slug_collision_rejected(self):
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Block",
            slug="portal-2",
        )
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            with self.assertRaises(CommandError):
                call_command("seed_development_data", stdout=StringIO())
        self.assertEqual(Game.objects.count(), 1)

    def test_conflict_run_is_atomic(self):
        User.objects.create_user(username="pre-existing", password="p")
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Pre",
            slug="pre",
        )
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Block",
            slug="portal-2",
        )
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            with self.assertRaises(CommandError):
                call_command("seed_development_data", stdout=StringIO())
        self.assertTrue(User.objects.filter(username="pre-existing").exists())
        self.assertTrue(Game.objects.filter(slug="pre").exists())


# ---------------------------------------------------------------------------
# Strengthened rollback
# ---------------------------------------------------------------------------


class StrengthenedRollbackTests(TestCase):
    def test_failure_after_writes_rolls_back_all(self):
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            with patch(
                "games.development_data.set_editorial_classification",
                side_effect=RuntimeError("simulated"),
            ):
                with self.assertRaises(RuntimeError):
                    call_command("seed_development_data", stdout=StringIO())
        self.assertEqual(Game.objects.count(), 0)
        self.assertFalse(User.objects.filter(username=_SEED_USERNAME).exists())
        self.assertEqual(EditorialClassification.objects.count(), 0)
        self.assertEqual(ChallengeProfile.objects.count(), 0)
        self.assertEqual(RewardProfile.objects.count(), 0)


# ---------------------------------------------------------------------------
# Command output safety
# ---------------------------------------------------------------------------


class OutputSafetyTests(TestCase):
    def setUp(self):
        self.out = StringIO()
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=self.out)
        self.output = self.out.getvalue()

    def test_no_password_in_output(self):
        self.assertNotIn("password", self.output.lower())

    def test_no_secret_key_in_output(self):
        self.assertNotIn("SECRET_KEY", self.output)
        self.assertNotIn("secret", self.output.lower())

    def test_no_steam_key_in_output(self):
        self.assertNotIn("WEB_API_KEY", self.output)
        self.assertNotIn("steam", self.output.lower())

    def test_no_database_url_in_output(self):
        self.assertNotIn("DATABASE_URL", self.output)
        self.assertNotIn("postgresql", self.output.lower())

    def test_reports_counts(self):
        self.assertIn("Development data seeded", self.output)
        self.assertIn("created", self.output.lower())

    def test_rerun_output_distinguishes(self):
        out2 = StringIO()
        with override_settings(DEVELOPMENT_SEEDING_ENABLED=True):
            call_command("seed_development_data", stdout=out2)
        self.assertIn("Development data seeded", out2.getvalue())
