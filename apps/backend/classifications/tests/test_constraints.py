"""
Classification database-constraint tests — SBGC-47.

Bulk operations, deletions, and direct DB enforcement for editorial
classification models.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from games.models import Game, SourceType

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
)


def _game(slug):
    return Game.objects.create(source_type=SourceType.MANUAL, name=slug, slug=slug)


def _user(username):
    return User.objects.create_user(username=username, password="test")


def _parent(game, user):
    return EditorialClassification.objects.create(game=game, updated_by=user)


def _challenge(parent, micro=50, mystiko=20, macro=30):
    return ChallengeProfile.objects.create(
        classification=parent,
        micro_score=micro,
        mystiko_score=mystiko,
        macro_score=macro,
    )


def _reward(parent, micro=10, mystiko=30, macro=60):
    return RewardProfile.objects.create(
        classification=parent,
        micro_score=micro,
        mystiko_score=mystiko,
        macro_score=macro,
    )


# ---------------------------------------------------------------------------
# Score constraint tests — direct DB
# ---------------------------------------------------------------------------


class ChallengeScoreConstraintTests(TestCase):
    def setUp(self):
        self.parent = _parent(_game("ch-score"), _user("ch-score-u"))

    def test_score_below_0_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent,
                    micro_score=-1,
                    mystiko_score=50,
                    macro_score=51,
                )

    def test_score_above_100_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent,
                    micro_score=101,
                    mystiko_score=0,
                    macro_score=-1,
                )

    def test_total_99_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent,
                    micro_score=50,
                    mystiko_score=20,
                    macro_score=29,
                )

    def test_total_101_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent,
                    micro_score=50,
                    mystiko_score=21,
                    macro_score=30,
                )

    def test_40_40_40_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent,
                    micro_score=40,
                    mystiko_score=40,
                    macro_score=40,
                )

    def test_valid_100_0_0_accepted(self):
        cp = ChallengeProfile.objects.create(
            classification=self.parent,
            micro_score=100,
            mystiko_score=0,
            macro_score=0,
        )
        self.assertIsNotNone(cp.pk)

    def test_valid_33_33_34_accepted(self):
        cp = ChallengeProfile.objects.create(
            classification=self.parent,
            micro_score=33,
            mystiko_score=33,
            macro_score=34,
        )
        self.assertIsNotNone(cp.pk)


class RewardScoreConstraintTests(TestCase):
    def setUp(self):
        self.parent = _parent(_game("rw-score"), _user("rw-score-u"))

    def test_score_below_0_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=self.parent,
                    micro_score=-5,
                    mystiko_score=50,
                    macro_score=55,
                )

    def test_score_above_100_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=self.parent,
                    micro_score=101,
                    mystiko_score=-1,
                    macro_score=0,
                )

    def test_total_99_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=self.parent,
                    micro_score=10,
                    mystiko_score=30,
                    macro_score=59,
                )

    def test_total_101_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=self.parent,
                    micro_score=10,
                    mystiko_score=31,
                    macro_score=60,
                )

    def test_40_40_40_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=self.parent,
                    micro_score=40,
                    mystiko_score=40,
                    macro_score=40,
                )

    def test_valid_100_0_0_accepted(self):
        rp = RewardProfile.objects.create(
            classification=self.parent,
            micro_score=100,
            mystiko_score=0,
            macro_score=0,
        )
        self.assertIsNotNone(rp.pk)

    def test_valid_33_33_34_accepted(self):
        rp = RewardProfile.objects.create(
            classification=self.parent,
            micro_score=33,
            mystiko_score=33,
            macro_score=34,
        )
        self.assertIsNotNone(rp.pk)


# ---------------------------------------------------------------------------
# Bulk operation tests
# ---------------------------------------------------------------------------


class ChallengeBulkOperationTests(TestCase):
    def setUp(self):
        g = _game("ch-bulk")
        self.user = _user("ch-bulk-u")
        self.parent = _parent(g, self.user)
        self.cp = _challenge(self.parent)

    def test_update_causes_total_99_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.filter(pk=self.cp.pk).update(macro_score=29)

    def test_update_causes_score_101_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.filter(pk=self.cp.pk).update(micro_score=101)

    def test_valid_update_accepted(self):
        ChallengeProfile.objects.filter(pk=self.cp.pk).update(
            micro_score=40, mystiko_score=30, macro_score=30
        )
        self.cp.refresh_from_db()
        self.assertEqual(self.cp.micro_score, 40)


class RewardBulkOperationTests(TestCase):
    def setUp(self):
        g = _game("rw-bulk")
        self.user = _user("rw-bulk-u")
        self.parent = _parent(g, self.user)
        self.rp = _reward(self.parent)

    def test_update_causes_total_99_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.filter(pk=self.rp.pk).update(macro_score=59)

    def test_update_causes_score_101_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.filter(pk=self.rp.pk).update(micro_score=101)

    def test_valid_update_accepted(self):
        RewardProfile.objects.filter(pk=self.rp.pk).update(
            micro_score=20, mystiko_score=30, macro_score=50
        )
        self.rp.refresh_from_db()
        self.assertEqual(self.rp.micro_score, 20)


# ---------------------------------------------------------------------------
# Relationship and deletion tests
# ---------------------------------------------------------------------------


class RelationshipTests(TestCase):
    def setUp(self):
        self.game = _game("rel-game")
        self.user = _user("rel-user")
        self.parent = _parent(self.game, self.user)
        self.cp = _challenge(self.parent)
        self.rp = _reward(self.parent)

    def test_duplicate_parent_per_game_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                EditorialClassification.objects.create(
                    game=self.game, updated_by=self.user
                )

    def test_duplicate_challenge_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ChallengeProfile.objects.create(
                    classification=self.parent,
                    micro_score=50,
                    mystiko_score=20,
                    macro_score=30,
                )

    def test_duplicate_reward_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RewardProfile.objects.create(
                    classification=self.parent,
                    micro_score=10,
                    mystiko_score=30,
                    macro_score=60,
                )

    def test_game_deletion_cascades_all(self):
        self.game.delete()
        self.assertFalse(
            EditorialClassification.objects.filter(pk=self.parent.pk).exists()
        )
        self.assertFalse(ChallengeProfile.objects.filter(pk=self.cp.pk).exists())
        self.assertFalse(RewardProfile.objects.filter(pk=self.rp.pk).exists())

    def test_parent_deletion_cascades_profiles(self):
        self.parent.delete()
        self.assertFalse(ChallengeProfile.objects.filter(pk=self.cp.pk).exists())
        self.assertFalse(RewardProfile.objects.filter(pk=self.rp.pk).exists())

    def test_user_protection(self):
        with self.assertRaises(IntegrityError):
            self.user.delete()

    def test_delete_one_profile_leaves_parent(self):
        self.cp.delete()
        self.parent.refresh_from_db()
        self.assertIsNotNone(self.parent.pk)

    def test_delete_one_game_not_another(self):
        game2 = _game("other-game")
        parent2 = _parent(game2, _user("other-user"))
        self.game.delete()
        parent2.refresh_from_db()
        self.assertIsNotNone(parent2.pk)

    def test_direct_orm_can_create_incomplete_parent(self):
        """Direct ORM allows a parent without profiles — documented limitation."""
        g = _game("orphan")
        u = _user("orphan-u")
        p = EditorialClassification.objects.create(game=g, updated_by=u)
        self.assertIsNotNone(p.pk)
        self.assertFalse(ChallengeProfile.objects.filter(classification=p).exists())
        self.assertFalse(RewardProfile.objects.filter(classification=p).exists())


class ClassificationMigrationReversibilityTests(TransactionTestCase):
    """``classifications.0001_initial`` executes forward and reverse.

    ``TransactionTestCase`` permits schema-changing migration operations.
    The test explicitly restores the latest app migration state in a
    ``finally`` block so that assertion failures or migration errors
    do not leave the database in an incomplete state.
    """

    @staticmethod
    def _migrate_app(app, target):
        from django.core.management import call_command

        call_command(
            "migrate",
            app,
            target,
            verbosity=0,
            interactive=False,
            skip_checks=True,
        )

    def test_forward_reverse_forward(self):
        from django.contrib.auth.models import User
        from django.db import IntegrityError, connection, transaction
        from games.models import Game, SourceType

        from classifications.models import (
            ChallengeProfile,
            EditorialClassification,
            RewardProfile,
        )

        # Confirm initial state: all three tables exist.
        tables = connection.introspection.table_names()
        self.assertIn(
            "classifications_editorialclassification",
            tables,
            "editorial table must exist before reverse test",
        )
        self.assertIn("classifications_challengeprofile", tables)
        self.assertIn("classifications_rewardprofile", tables)
        self.assertIn("games_game", tables)
        self.assertIn("auth_user", tables)

        try:
            # -- (1) Reverse classifications to zero --------------------------
            self._migrate_app("classifications", "zero")
            tables = connection.introspection.table_names()
            self.assertNotIn("classifications_editorialclassification", tables)
            self.assertNotIn("classifications_challengeprofile", tables)
            self.assertNotIn("classifications_rewardprofile", tables)
            self.assertIn("games_game", tables)
            self.assertIn("auth_user", tables)

            # -- (2) Forward classifications to latest SBGC-63 state --------
            self._migrate_app("classifications", "0004")
            tables = connection.introspection.table_names()
            self.assertIn("classifications_editorialclassification", tables)
            self.assertIn("classifications_challengeprofile", tables)
            self.assertIn("classifications_rewardprofile", tables)

            # -- (3) Verify constraints by exercising them --------------------
            g = Game.objects.create(
                source_type=SourceType.MANUAL, name="Rev", slug="rev"
            )
            u = User.objects.create_user(username="rev_u", password="p")
            parent = EditorialClassification.objects.create(game=g, updated_by=u)
            ChallengeProfile.objects.create(
                classification=parent,
                micro_score=50,
                mystiko_score=20,
                macro_score=30,
            )
            RewardProfile.objects.create(
                classification=parent,
                micro_score=10,
                mystiko_score=30,
                macro_score=60,
            )
            with transaction.atomic():
                with self.assertRaises(IntegrityError):
                    ChallengeProfile.objects.create(
                        classification=parent,
                        micro_score=40,
                        mystiko_score=40,
                        macro_score=40,
                    )
        finally:
            # Always restore the full project to the latest migration state.
            self._migrate_app("", "")

        # Confirm restored.
        tables = connection.introspection.table_names()
        self.assertIn("classifications_editorialclassification", tables)
        self.assertIn("classifications_challengeprofile", tables)
        self.assertIn("classifications_rewardprofile", tables)
        self.assertIn("games_game", tables)
        self.assertIn("auth_user", tables)

    def test_operations_marked_reversible(self):
        """Supplemental: every operation is marked reversible."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        migration = loader.disk_migrations[("classifications", "0001_initial")]
        for op in migration.operations:
            self.assertTrue(
                op.reversible,
                f"Operation '{op.describe()}' must be reversible",
            )
