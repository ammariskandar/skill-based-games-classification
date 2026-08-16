"""
PostgreSQL Classification constraint verification — SBGC-52.

Verifies CheckConstraints, OneToOneField uniqueness, CASCADE/PROTECT
behaviour, bulk-operation enforcement, and service transaction semantics
on an isolated PostgreSQL instance.
"""

from __future__ import annotations

from config.pg_testing import PostgreSQLTestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
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


def _game(slug, **kw):
    return Game.objects.create(
        source_type=SourceType.MANUAL,
        name=slug.replace("-", " ").title(),
        slug=slug,
        **kw,
    )


def _user(username):
    return User.objects.create_user(username=username, password="testpass")


# ============================================================================
# CheckConstraint — score range and total
# ============================================================================


class ChallengeConstraintTests(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.game = _game("ch-constraint")
        cls.user = _user("ch-constraint-user")

    def _create(self, micro, mystiko, macro):
        parent = EditorialClassification.objects.create(
            game=self.game, submitted_by=self.user, updated_by=self.user
        )
        return ChallengeProfile.objects.create(
            classification=parent,
            micro_score=micro,
            mystiko_score=mystiko,
            macro_score=macro,
        )

    def test_score_below_0_rejected(self):
        with self.assertRaises(IntegrityError):
            self._create(-1, 50, 51)

    def test_score_above_100_rejected(self):
        with self.assertRaises(IntegrityError):
            self._create(101, 0, -1)

    def test_total_not_100_rejected(self):
        with self.assertRaises(IntegrityError):
            self._create(40, 30, 20)  # total = 90

    def test_total_exactly_100_accepted(self):
        profile = self._create(50, 20, 30)
        self.assertIsNotNone(profile.pk)

    def test_all_zeros_rejected(self):
        with self.assertRaises(IntegrityError):
            self._create(0, 0, 0)  # total = 0

    def test_all_100_rejected(self):
        with self.assertRaises(IntegrityError):
            self._create(100, 100, 100)  # total = 300


class RewardConstraintTests(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.game = _game("rw-constraint")
        cls.user = _user("rw-constraint-user")

    def _create(self, micro, mystiko, macro):
        parent = EditorialClassification.objects.create(
            game=self.game, submitted_by=self.user, updated_by=self.user
        )
        return RewardProfile.objects.create(
            classification=parent,
            micro_score=micro,
            mystiko_score=mystiko,
            macro_score=macro,
        )

    def test_score_below_0_rejected(self):
        with self.assertRaises(IntegrityError):
            self._create(-5, 50, 55)

    def test_score_above_100_rejected(self):
        with self.assertRaises(IntegrityError):
            self._create(200, 0, -100)

    def test_total_not_100_rejected(self):
        with self.assertRaises(IntegrityError):
            self._create(10, 20, 30)  # total = 60

    def test_total_exactly_100_accepted(self):
        profile = self._create(10, 30, 60)
        self.assertIsNotNone(profile.pk)

    def test_challenge_reward_independent(self):
        """A valid Reward can exist alongside a valid Challenge — same parent."""
        parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )
        ChallengeProfile.objects.create(
            classification=parent, micro_score=50, mystiko_score=20, macro_score=30
        )
        RewardProfile.objects.create(
            classification=parent, micro_score=10, mystiko_score=30, macro_score=60
        )
        self.assertIsNotNone(parent.challenge_profile)
        self.assertIsNotNone(parent.reward_profile)


# ============================================================================
# OneToOneField uniqueness
# ============================================================================


class OneToOneUniquenessTests(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.game = _game("oto-game")
        cls.user = _user("oto-user")

    def test_duplicate_parent_rejected(self):
        EditorialClassification.objects.create(game=self.game, updated_by=self.user)
        with self.assertRaises(IntegrityError):
            EditorialClassification.objects.create(game=self.game, updated_by=self.user)

    def test_duplicate_challenge_rejected(self):
        parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )
        ChallengeProfile.objects.create(
            classification=parent, micro_score=50, mystiko_score=20, macro_score=30
        )
        with self.assertRaises(IntegrityError):
            ChallengeProfile.objects.create(
                classification=parent, micro_score=60, mystiko_score=20, macro_score=20
            )

    def test_duplicate_reward_rejected(self):
        parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )
        RewardProfile.objects.create(
            classification=parent, micro_score=10, mystiko_score=30, macro_score=60
        )
        with self.assertRaises(IntegrityError):
            RewardProfile.objects.create(
                classification=parent, micro_score=20, mystiko_score=40, macro_score=40
            )


# ============================================================================
# CASCADE and PROTECT
# ============================================================================


class CascadeProtectTests(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _user("fk-user")
        cls.game = _game("fk-game")
        cls.parent = EditorialClassification.objects.create(
            game=cls.game, updated_by=cls.user
        )
        cls.ch = ChallengeProfile.objects.create(
            classification=cls.parent, micro_score=50, mystiko_score=20, macro_score=30
        )
        cls.rw = RewardProfile.objects.create(
            classification=cls.parent, micro_score=10, mystiko_score=30, macro_score=60
        )

    def test_cascade_game_delete_removes_classification(self):
        game = _game("cascade-game")
        parent = EditorialClassification.objects.create(game=game, updated_by=self.user)
        ChallengeProfile.objects.create(
            classification=parent, micro_score=40, mystiko_score=30, macro_score=30
        )
        RewardProfile.objects.create(
            classification=parent, micro_score=20, mystiko_score=40, macro_score=40
        )
        parent_pk = parent.pk
        game.delete()
        self.assertFalse(EditorialClassification.objects.filter(pk=parent_pk).exists())

    def test_cascade_parent_delete_removes_profiles(self):
        game = _game("cascade-parent")
        parent = EditorialClassification.objects.create(game=game, updated_by=self.user)
        ChallengeProfile.objects.create(
            classification=parent, micro_score=33, mystiko_score=33, macro_score=34
        )
        RewardProfile.objects.create(
            classification=parent, micro_score=33, mystiko_score=33, macro_score=34
        )
        ch_pk = parent.challenge_profile.pk
        rw_pk = parent.reward_profile.pk
        parent.delete()
        self.assertFalse(ChallengeProfile.objects.filter(pk=ch_pk).exists())
        self.assertFalse(RewardProfile.objects.filter(pk=rw_pk).exists())

    def test_protect_user_delete_blocked(self):
        """PROTECT on updated_by prevents user deletion when referenced."""
        with self.assertRaises(IntegrityError):
            self.user.delete()


# ============================================================================
# Bulk operation constraint enforcement
# ============================================================================


class BulkConstraintTests(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.game = _game("bulk-cls")
        cls.user = _user("bulk-cls-user")

    def test_bulk_create_invalid_challenge_rejected(self):
        parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )
        # 40+40+40=120 — unambiguously violates total=100 constraint.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChallengeProfile.objects.bulk_create(
                    [
                        ChallengeProfile(
                            classification=parent,
                            micro_score=40,
                            mystiko_score=40,
                            macro_score=40,
                        ),
                    ]
                )
        self.assertFalse(
            ChallengeProfile.objects.filter(classification=parent).exists()
        )

    def test_bulk_update_invalid_challenge_rejected(self):
        parent = EditorialClassification.objects.create(
            game=self.game, updated_by=self.user
        )
        profile = ChallengeProfile.objects.create(
            classification=parent, micro_score=50, mystiko_score=20, macro_score=30
        )
        profile.micro_score = 999
        with self.assertRaises(IntegrityError):
            ChallengeProfile.objects.bulk_update([profile], ["micro_score"])


# ============================================================================
# Service transaction semantics
# ============================================================================


class ServiceTransactionTests(PostgreSQLTestCase):
    def test_invalid_reward_rolls_back_parent_and_challenge(self):
        game = _game("svc-rollback")
        user = _user("svc-rollback-user")

        with self.assertRaises(ValidationError):
            # Reward total 50+50+10=110 — invalid.
            set_editorial_classification(
                game=game,
                updated_by=user,
                challenge=ScoreDistribution(micro=50, mystiko=20, macro=30),
                reward=ScoreDistribution(micro=50, mystiko=50, macro=10),
            )

        # Nothing persisted.
        self.assertFalse(EditorialClassification.objects.filter(game=game).exists())
        self.assertFalse(
            ChallengeProfile.objects.filter(classification__game=game).exists()
        )
        self.assertFalse(
            RewardProfile.objects.filter(classification__game=game).exists()
        )

    def test_invalid_update_preserves_prior_state(self):
        game = _game("svc-update-keep")
        user = _user("svc-update-keep-user")

        parent = set_editorial_classification(
            game=game,
            updated_by=user,
            challenge=ScoreDistribution(micro=50, mystiko=20, macro=30),
            reward=ScoreDistribution(micro=10, mystiko=30, macro=60),
        )
        old_micro = parent.challenge_profile.micro_score

        with self.assertRaises(ValidationError):
            set_editorial_classification(
                game=game,
                updated_by=user,
                challenge=ScoreDistribution(micro=99, mystiko=0, macro=0),
                reward=ScoreDistribution(micro=10, mystiko=30, macro=60),
            )

        parent.challenge_profile.refresh_from_db()
        self.assertEqual(parent.challenge_profile.micro_score, old_micro)

    def test_nested_savepoint_recovers_after_integrity_error(self):
        """IntegrityError in a nested atomic block does not poison the
        outer transaction.  Uses Django's nested atomic() for automatic
        savepoint management — no manual savepoint calls."""
        game = _game("svc-sp")
        user = _user("svc-sp-user")

        with transaction.atomic():
            # Establish valid outer-transaction state.
            original = EditorialClassification.objects.create(
                game=game, updated_by=user
            )

            # Nested atomic block — IntegrityError rolls back its savepoint.
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    EditorialClassification.objects.create(game=game, updated_by=user)

            # Outer transaction still usable.
            self.assertTrue(
                EditorialClassification.objects.filter(pk=original.pk).exists()
            )

            # Another valid write succeeds.
            game2 = _game("svc-sp-2")
            second = EditorialClassification.objects.create(game=game2, updated_by=user)
            self.assertIsNotNone(second.pk)


# ============================================================================
# Constraint name introspection
# ============================================================================


class ClassificationConstraintIntrospectionTests(PostgreSQLTestCase):
    def _constraint_names(self, table):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT conname FROM pg_constraint
                WHERE conrelid = %s::regclass
                ORDER BY conname
                """,
                [table],
            )
            return {row[0] for row in cursor.fetchall()}

    def test_challenge_constraint_names(self):
        names = self._constraint_names("classifications_challengeprofile")
        self.assertIn("challenge_scores_range_ck", names)
        self.assertIn("challenge_scores_total_100_ck", names)

    def test_reward_constraint_names(self):
        names = self._constraint_names("classifications_rewardprofile")
        self.assertIn("reward_scores_range_ck", names)
        self.assertIn("reward_scores_total_100_ck", names)
