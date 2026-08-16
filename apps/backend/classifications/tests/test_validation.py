"""
SBGC-64 classification validation hardening tests.

Focused coverage for the validation gaps closed in SBGC-64: role/weight
pair consistency, friendly model-level duplicate messaging, and duplicate
race translation.  Score-range/total matrix coverage lives in the existing
model, service, constraint, and Admin test modules.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from games.models import Game, SourceType

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
)
from classifications.roles import BASE_WEIGHTS, EditorialRole
from classifications.services.submissions import (
    EditorialSubmissionError,
    ScoreDistribution,
    _is_duplicate_submission_integrity_error,
    _persist_submission,
    create_submission,
)


def _game(slug: str) -> Game:
    return Game.objects.create(source_type=SourceType.MANUAL, name=slug, slug=slug)


def _user(username: str) -> User:
    return User.objects.create_user(username=username, password="p")


def _dist(micro=50, mystiko=20, macro=30) -> ScoreDistribution:
    return ScoreDistribution(micro=micro, mystiko=mystiko, macro=macro)


def _reward(micro=10, mystiko=30, macro=60) -> ScoreDistribution:
    return ScoreDistribution(micro=micro, mystiko=mystiko, macro=macro)


class RoleWeightPairTests(TestCase):
    def test_mismatched_pair_rejected(self):
        submission = EditorialClassification(
            game=_game("pair-bad"),
            submitted_by=_user("pair-bad-sub"),
            updated_by=_user("pair-bad-op"),
            submitted_role=EditorialRole.MODERATOR,
            submitted_base_weight=BASE_WEIGHTS[EditorialRole.COMMUNITY],
        )
        with self.assertRaises(ValidationError) as cm:
            submission.full_clean()
        self.assertIn("Base weight for role Moderator must be 0.95", str(cm.exception))

    def test_consistent_pairs_pass_clean(self):
        for role, weight in BASE_WEIGHTS.items():
            submission = EditorialClassification(
                game=_game(f"pair-ok-{role}"),
                submitted_by=_user(f"pair-ok-{role}-sub"),
                updated_by=_user(f"pair-ok-{role}-op"),
                submitted_role=role,
                submitted_base_weight=weight,
            )
            submission.full_clean()  # should not raise


class ModelDuplicateTranslationTests(TestCase):
    def test_full_clean_duplicate_is_friendly(self):
        game = _game("dup-model")
        user = _user("dup-model-sub")
        EditorialClassification.objects.create(
            game=game, submitted_by=user, updated_by=user
        )
        duplicate = EditorialClassification(
            game=game,
            submitted_by=user,
            updated_by=user,
            submitted_role=EditorialRole.COMMUNITY,
            submitted_base_weight=BASE_WEIGHTS[EditorialRole.COMMUNITY],
        )
        with self.assertRaises(ValidationError) as cm:
            duplicate.full_clean()
        self.assertIn(
            "This user has already submitted scores for this game.",
            str(cm.exception),
        )
        self.assertNotIn("already exists", str(cm.exception))


class DuplicateRaceTests(TestCase):
    def test_duplicate_integrity_error_classified(self):
        game = _game("race-cls")
        user = _user("race-cls-sub")
        EditorialClassification.objects.create(
            game=game, submitted_by=user, updated_by=user
        )
        with self.assertRaises(IntegrityError) as cm:
            EditorialClassification.objects.create(
                game=game, submitted_by=user, updated_by=user
            )
        self.assertTrue(_is_duplicate_submission_integrity_error(cm.exception))

    def test_unrelated_integrity_error_not_classified(self):
        game = _game("race-unrel")
        user = _user("race-unrel-sub")
        parent = EditorialClassification.objects.create(
            game=game, submitted_by=user, updated_by=user
        )
        with self.assertRaises(IntegrityError) as cm:
            ChallengeProfile.objects.create(
                classification=parent, micro_score=40, mystiko_score=40, macro_score=40
            )
        self.assertFalse(_is_duplicate_submission_integrity_error(cm.exception))

    def test_persist_translates_lost_duplicate_race(self):
        game = _game("race-persist")
        user = _user("race-persist-sub")
        create_submission(
            game=game,
            submitted_by=user,
            updated_by=user,
            challenge=_dist(),
            reward=_reward(),
        )

        # Simulate a concurrent loser whose pre-check passed but whose insert
        # now collides with the committed winner.
        submission = EditorialClassification(
            game=game,
            submitted_by=user,
            updated_by=user,
            submitted_role=EditorialRole.COMMUNITY,
            submitted_base_weight=BASE_WEIGHTS[EditorialRole.COMMUNITY],
            notes="",
        )
        with self.assertRaises(EditorialSubmissionError):
            _persist_submission(submission, _dist(), _reward())


class RoleWeightDbConstraintTests(TestCase):
    def test_four_valid_pairs_persist_via_raw_save(self):
        pairs = [
            (EditorialRole.SUPERUSER, BASE_WEIGHTS[EditorialRole.SUPERUSER]),
            (EditorialRole.MODERATOR, BASE_WEIGHTS[EditorialRole.MODERATOR]),
            (
                EditorialRole.COMMUNITY_LEADER,
                BASE_WEIGHTS[EditorialRole.COMMUNITY_LEADER],
            ),
            (EditorialRole.COMMUNITY, BASE_WEIGHTS[EditorialRole.COMMUNITY]),
        ]
        for role, weight in pairs:
            with self.subTest(role=role):
                submission = EditorialClassification(
                    game=_game(f"pair-db-ok-{role}"),
                    submitted_by=_user(f"pair-db-ok-{role}-sub"),
                    updated_by=_user(f"pair-db-ok-{role}-op"),
                    submitted_role=role,
                    submitted_base_weight=weight,
                )
                submission.save()  # bypasses full_clean(); DB accepts valid pair
                self.assertIsNotNone(submission.pk)

    def test_moderator_with_community_weight_rejected_by_db(self):
        submission = EditorialClassification(
            game=_game("pair-db-bad-m"),
            submitted_by=_user("pair-db-bad-m-sub"),
            updated_by=_user("pair-db-bad-m-op"),
            submitted_role=EditorialRole.MODERATOR,
            submitted_base_weight=BASE_WEIGHTS[EditorialRole.COMMUNITY],
        )
        with self.assertRaises(IntegrityError):
            submission.save()

    def test_community_with_moderator_weight_rejected_by_db(self):
        submission = EditorialClassification(
            game=_game("pair-db-bad-c"),
            submitted_by=_user("pair-db-bad-c-sub"),
            updated_by=_user("pair-db-bad-c-op"),
            submitted_role=EditorialRole.COMMUNITY,
            submitted_base_weight=BASE_WEIGHTS[EditorialRole.MODERATOR],
        )
        with self.assertRaises(IntegrityError):
            submission.save()

    def test_canonical_service_create_still_works(self):
        submission = create_submission(
            game=_game("pair-svc-ok"),
            submitted_by=_user("pair-svc-ok-sub"),
            updated_by=_user("pair-svc-ok-op"),
            challenge=_dist(),
            reward=_reward(),
        )
        self.assertEqual(submission.submitted_role, EditorialRole.COMMUNITY)
        self.assertEqual(
            submission.submitted_base_weight, BASE_WEIGHTS[EditorialRole.COMMUNITY]
        )
