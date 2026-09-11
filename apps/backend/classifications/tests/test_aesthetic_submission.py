"""
Aesthetic capture in manual submissions — SBGC-228.

Covers the optional canonical aesthetic on both ingestion targets:

* community submissions (``UserGameScoreSubmission``) via the temporal engine
  and the ``POST /api/v1/classifications/games/{slug}/submit-score`` endpoint;
* staff/editorial submissions (``EditorialClassification``) via the same
  endpoint and the direct submission service.

Aesthetic is optional (legacy clients keep working), normalized to the canonical
uppercase taxonomy, and never touches the sum-to-100 score invariants.
"""

from __future__ import annotations

import json

from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from games.models import Game, SourceType

from classifications.admin import EditorialClassificationAdminForm
from classifications.models import (
    AESTHETIC_CHOICES,
    EditorialClassification,
    EditorialGroupProfile,
    UserGameScoreSubmission,
)
from classifications.questionnaire.domain import AestheticCategory
from classifications.services.submission_ingestion import ingest_score_submission
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
    update_submission,
)

SUBMIT_URL = "/api/v1/classifications/games/{slug}/submit-score"


def _game() -> Game:
    return Game.objects.create(
        name="Aesthetic Test Game",
        slug="aesthetic-test-game",
        source_type=SourceType.MANUAL,
        content_type="game",
        listing_status="published",
    )


def _payload(
    challenge=(40, 30, 30),
    reward=(35, 35, 30),
    aesthetic: str | None = None,
) -> dict:
    payload: dict = {
        "challenge": {
            "micro": challenge[0],
            "mystiko": challenge[1],
            "macro": challenge[2],
        },
        "reward": {
            "micro": reward[0],
            "mystiko": reward[1],
            "macro": reward[2],
        },
    }
    if aesthetic is not None:
        payload["aesthetic"] = aesthetic
    return payload


def _moderator(username: str = "mod") -> User:
    user = User.objects.create_user(username=username, password="pw")
    group = Group.objects.create(name=f"{username}-mod-group")
    EditorialGroupProfile.objects.create(group=group, is_moderator=True)
    user.groups.add(group)
    return user


class AestheticTaxonomyTests(TestCase):
    def test_choices_derive_from_the_canonical_domain_enum(self):
        self.assertEqual(
            {value for value, _label in AESTHETIC_CHOICES},
            {
                AestheticCategory.SENSORY.value,
                AestheticCategory.FANTASY.value,
                AestheticCategory.NARRATIVE.value,
                AestheticCategory.CHALLENGE.value,
            },
        )


class CommunityAestheticIngestionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="gamer", password="pw")
        self.game = _game()

    def _latest(self) -> UserGameScoreSubmission:
        row = UserGameScoreSubmission.objects.filter(
            user=self.user, game=self.game
        ).first()
        assert row is not None
        return row

    def test_first_submission_persists_normalized_aesthetic(self):
        ingest_score_submission(
            user=self.user,
            game=self.game,
            payload=_payload(aesthetic="sensory"),
        )
        self.assertEqual(self._latest().aesthetic, AestheticCategory.SENSORY.value)

    def test_omitted_aesthetic_is_nullable(self):
        ingest_score_submission(user=self.user, game=self.game, payload=_payload())
        self.assertIsNone(self._latest().aesthetic)

    def test_unknown_aesthetic_is_dropped(self):
        ingest_score_submission(
            user=self.user,
            game=self.game,
            payload=_payload(aesthetic="action"),
        )
        self.assertIsNone(self._latest().aesthetic)

    def test_revision_updates_aesthetic_in_place(self):
        ingest_score_submission(
            user=self.user,
            game=self.game,
            payload=_payload(aesthetic="SENSORY"),
        )
        first = self._latest()

        ingest_score_submission(
            user=self.user,
            game=self.game,
            payload=_payload(challenge=(50, 25, 25), aesthetic="fantasy"),
        )
        self.assertEqual(UserGameScoreSubmission.objects.count(), 1)
        latest = self._latest()
        self.assertEqual(latest.pk, first.pk)
        self.assertEqual(latest.aesthetic, AestheticCategory.FANTASY.value)

    def test_revision_without_aesthetic_preserves_the_existing_value(self):
        ingest_score_submission(
            user=self.user,
            game=self.game,
            payload=_payload(aesthetic="NARRATIVE"),
        )
        ingest_score_submission(
            user=self.user,
            game=self.game,
            payload=_payload(challenge=(50, 25, 25)),
        )
        self.assertEqual(self._latest().aesthetic, AestheticCategory.NARRATIVE.value)


class EditorialAestheticIngestionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.game = _game()
        self.moderator = _moderator()

    def test_staff_create_persists_aesthetic_on_editorial_record(self):
        ingest_score_submission(
            user=self.moderator,
            game=self.game,
            payload=_payload(aesthetic="fantasy"),
        )
        submission = EditorialClassification.objects.get(
            game=self.game, submitted_by=self.moderator
        )
        self.assertEqual(submission.aesthetic, AestheticCategory.FANTASY.value)

    def test_staff_update_supersedes_aesthetic(self):
        ingest_score_submission(
            user=self.moderator,
            game=self.game,
            payload=_payload(aesthetic="FANTASY"),
        )
        ingest_score_submission(
            user=self.moderator,
            game=self.game,
            payload=_payload(challenge=(50, 25, 25), aesthetic="challenge"),
        )
        submission = EditorialClassification.objects.get(
            game=self.game, submitted_by=self.moderator
        )
        self.assertEqual(submission.aesthetic, AestheticCategory.CHALLENGE.value)


class EditorialSubmissionServiceTests(TestCase):
    def setUp(self):
        self.game = _game()
        self.admin = User.objects.create_superuser("root", password="pw")

    def test_create_submission_accepts_aesthetic(self):
        submission = create_submission(
            game=self.game,
            submitted_by=self.admin,
            updated_by=self.admin,
            challenge=ScoreDistribution(40, 30, 30),
            reward=ScoreDistribution(35, 35, 30),
            aesthetic="SENSORY",
        )
        submission.refresh_from_db()
        self.assertEqual(submission.aesthetic, "SENSORY")

    def test_update_submission_sets_aesthetic_only_when_provided(self):
        submission = create_submission(
            game=self.game,
            submitted_by=self.admin,
            updated_by=self.admin,
            challenge=ScoreDistribution(40, 30, 30),
            reward=ScoreDistribution(35, 35, 30),
            aesthetic="SENSORY",
        )
        update_submission(
            submission,
            updated_by=self.admin,
            challenge=ScoreDistribution(50, 25, 25),
            reward=ScoreDistribution(35, 35, 30),
        )
        submission.refresh_from_db()
        self.assertEqual(submission.aesthetic, "SENSORY")

        update_submission(
            submission,
            updated_by=self.admin,
            aesthetic="CHALLENGE",
        )
        submission.refresh_from_db()
        self.assertEqual(submission.aesthetic, "CHALLENGE")


class SubmitScoreAestheticEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.game = _game()
        self.url = SUBMIT_URL.format(slug=self.game.slug)

    def _post(self, body: dict):
        return self.client.post(
            self.url, data=json.dumps(body), content_type="application/json"
        )

    def _login_community(self) -> User:
        user = User.objects.create_user(username="gamer", password="pw")
        self.client.force_login(user)
        return user

    def test_lowercase_aesthetic_is_accepted_and_normalized(self):
        user = self._login_community()
        response = self._post(_payload(aesthetic="sensory"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["aesthetic"], "SENSORY")
        self.assertEqual(
            UserGameScoreSubmission.objects.get(user=user, game=self.game).aesthetic,
            "SENSORY",
        )

    def test_uppercase_canonical_aesthetic_is_accepted(self):
        self._login_community()
        response = self._post(_payload(aesthetic="CHALLENGE"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["aesthetic"], "CHALLENGE")

    def test_invalid_aesthetic_is_rejected_with_422(self):
        self._login_community()
        response = self._post(_payload(aesthetic="action"))
        self.assertEqual(response.status_code, 422)

    def test_omitted_aesthetic_still_succeeds(self):
        self._login_community()
        response = self._post(_payload())
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["aesthetic"])

    def test_staff_submission_returns_and_persists_aesthetic(self):
        self.client.force_login(_moderator("endpoint-mod"))
        response = self._post(_payload(aesthetic="narrative"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["aesthetic"], "NARRATIVE")


class AestheticAdminTests(TestCase):
    def test_editorial_admin_exposes_aesthetic(self):
        model_admin = admin.site._registry[EditorialClassification]
        self.assertIn("aesthetic", model_admin.list_display)
        self.assertIn("aesthetic", model_admin.list_filter)
        self.assertIn("aesthetic", EditorialClassificationAdminForm.Meta.fields)

    def test_community_admin_lists_and_reads_only_aesthetic(self):
        model_admin = admin.site._registry[UserGameScoreSubmission]
        self.assertIn("aesthetic", model_admin.list_display)
        self.assertIn(
            "aesthetic", {f.name for f in UserGameScoreSubmission._meta.fields}
        )
        self.assertIn("aesthetic", model_admin.readonly_fields)

    def test_editorial_admin_help_text_summarises_the_taxonomy(self):
        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser("help-admin", password="pw")
        model_admin = admin.site._registry[EditorialClassification]
        form_class = model_admin.get_form(request)
        help_text = str(form_class.base_fields["aesthetic"].help_text)
        for label in ("SENSORY", "FANTASY", "NARRATIVE", "CHALLENGE"):
            self.assertIn(label, help_text)
