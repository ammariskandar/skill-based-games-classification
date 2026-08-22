"""
Classification Admin configuration tests — SBGC-68.

Covers the submission changelist (dominant/total columns), search, filters,
profile total/dominant display, validation UX, provenance readonly behavior,
and the read-only Final Classification presentation.
"""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from games.models import Game, SourceType
from games.types import ContentType

from classifications.admin import EditorialClassificationAdmin
from classifications.models import (
    CalculationEpoch,
    ChallengeProfile,
    ClassificationSnapshot,
    EditorialClassification,
    RewardProfile,
)
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
)

CH_PREFIX = "challenge_profile"
RW_PREFIX = "reward_profile"


def _inline_mgmt(prefix, total=1, initial=0):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "1",
        f"{prefix}-MAX_NUM_FORMS": "1",
    }


def _post_data(game_pk):
    return {
        "game": str(game_pk),
        "notes": "",
        **_inline_mgmt(CH_PREFIX),
        **_inline_mgmt(RW_PREFIX),
        f"{CH_PREFIX}-0-micro_score": "60",
        f"{CH_PREFIX}-0-mystiko_score": "20",
        f"{CH_PREFIX}-0-macro_score": "20",
        f"{RW_PREFIX}-0-micro_score": "20",
        f"{RW_PREFIX}-0-mystiko_score": "20",
        f"{RW_PREFIX}-0-macro_score": "60",
    }


class ProfileDisplayPropertyTests(TestCase):
    def test_total_sums_components(self):
        profile = ChallengeProfile(micro_score=60, mystiko_score=20, macro_score=20)
        self.assertEqual(profile.total, 100)

    def test_total_none_when_incomplete(self):
        profile = ChallengeProfile(micro_score=60, mystiko_score=None, macro_score=20)
        self.assertIsNone(profile.total)

    def test_dominant_single_winner(self):
        profile = ChallengeProfile(micro_score=60, mystiko_score=20, macro_score=20)
        self.assertEqual(profile.dominant_display, "Micro")

    def test_dominant_tie(self):
        profile = ChallengeProfile(micro_score=50, mystiko_score=50, macro_score=0)
        self.assertEqual(profile.dominant_display, "Micro / Mystiko tie")

    def test_dominant_incomplete(self):
        profile = ChallengeProfile(micro_score=60, mystiko_score=None, macro_score=20)
        self.assertEqual(profile.dominant_display, "—")

    def test_reward_has_same_properties(self):
        profile = RewardProfile(micro_score=20, mystiko_score=20, macro_score=60)
        self.assertEqual(profile.total, 100)
        self.assertEqual(profile.dominant_display, "Macro")


class SubmissionChangelistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="changelist-admin", password="pw"
        )
        cls.game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Changelist Game",
            slug="changelist-game",
            content_type=ContentType.GAME,
        )
        create_submission(
            game=cls.game,
            submitted_by=cls.superuser,
            updated_by=cls.superuser,
            challenge=ScoreDistribution(micro=60, mystiko=20, macro=20),
            reward=ScoreDistribution(micro=20, mystiko=20, macro=60),
        )

    def setUp(self):
        self.client.force_login(self.superuser)
        self.url = reverse("admin:classifications_editorialclassification_changelist")

    def test_changelist_shows_dominant(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Micro")
        self.assertContains(response, "Macro")

    def test_changelist_shows_totals(self):
        response = self.client.get(self.url)
        # Both profiles total 100; the changelist shows that value.
        self.assertContains(response, "100")


class SubmissionSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="searcher", password="pw"
        )
        cls.game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Searchable Game",
            slug="searchable-game",
        )
        create_submission(
            game=cls.game,
            submitted_by=cls.superuser,
            updated_by=cls.superuser,
            challenge=ScoreDistribution(micro=60, mystiko=20, macro=20),
            reward=ScoreDistribution(micro=20, mystiko=20, macro=60),
        )

    def setUp(self):
        self.client.force_login(self.superuser)
        self.url = reverse("admin:classifications_editorialclassification_changelist")

    def test_search_by_game_name(self):
        response = self.client.get(self.url, {"q": "Searchable"})
        self.assertContains(response, "Searchable Game")

    def test_search_by_submitter_username(self):
        response = self.client.get(self.url, {"q": "searcher"})
        self.assertContains(response, "Searchable Game")


class SubmissionFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="filter-admin", password="pw"
        )
        cls.game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Filtered Game",
            slug="filtered-game",
        )
        create_submission(
            game=cls.game,
            submitted_by=cls.superuser,
            updated_by=cls.superuser,
            challenge=ScoreDistribution(micro=60, mystiko=20, macro=20),
            reward=ScoreDistribution(micro=20, mystiko=20, macro=60),
        )

    def setUp(self):
        self.client.force_login(self.superuser)
        self.url = reverse("admin:classifications_editorialclassification_changelist")

    def test_filter_by_submitted_role(self):
        response = self.client.get(self.url, {"submitted_role__exact": "superuser"})
        self.assertContains(response, "Filtered Game")


class AddFormFieldsetTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="form-admin", password="pw"
        )
        self.client.force_login(self.superuser)
        self.url = reverse("admin:classifications_editorialclassification_add")

    def test_add_form_shows_total_and_dominant_readonly(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Total")
        self.assertContains(response, "Dominant")


class ValidationUxTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="validation-admin", password="pw"
        )
        self.client.force_login(self.superuser)
        self.game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Validation Game",
            slug="validation-game",
        )
        self.url = reverse("admin:classifications_editorialclassification_add")

    def test_invalid_total_shows_exact_error_and_no_partial_write(self):
        data = _post_data(self.game.pk)
        # 50 + 20 + 29 = 99 — invalid Challenge total.
        data[f"{CH_PREFIX}-0-micro_score"] = "50"
        data[f"{CH_PREFIX}-0-macro_score"] = "29"
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "must total exactly 100 (got 99)")
        self.assertFalse(
            EditorialClassification.objects.filter(game=self.game).exists()
        )


class ProvenanceReadonlyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="provenance-admin", password="pw"
        )
        cls.game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Provenance Game",
            slug="provenance-game",
        )
        cls.submission = create_submission(
            game=cls.game,
            submitted_by=cls.superuser,
            updated_by=cls.superuser,
            challenge=ScoreDistribution(micro=60, mystiko=20, macro=20),
            reward=ScoreDistribution(micro=20, mystiko=20, macro=60),
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_existing_submission_provenance_readonly(self):
        model_admin = admin.site._registry.get(EditorialClassification)
        assert model_admin is not None
        request = RequestFactory().get("/")
        request.user = self.superuser
        readonly = model_admin.get_readonly_fields(request, self.submission)
        for field in (
            "game",
            "submitted_by",
            "submitted_role",
            "submitted_base_weight",
        ):
            self.assertIn(field, readonly)


class FinalClassificationAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="snapshot-admin", password="pw"
        )
        cls.game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Snapshot Game",
            slug="snapshot-game",
        )
        epoch = CalculationEpoch.objects.create(
            epoch_id="snapshot-epoch",
            cutoff_at=timezone.now(),
            master_version="STATISTICAL_MODEL_V1.0.0",
        )
        cls.snapshot = ClassificationSnapshot.objects.create(
            game=cls.game,
            epoch=epoch,
            regime="unified",
            status="READY",
            cutoff_at=timezone.now(),
            confidence_final="50.00",
            confidence_label="Medium",
            validated_count=20,
            unified_integer_challenge=[60, 20, 20],
            unified_integer_reward=[20, 20, 60],
            method_1_status="READY",
            method_1_integer_challenge=[60, 20, 20],
            method_1_integer_reward=[20, 20, 60],
            method_2_status="READY",
            method_2_integer_challenge=[58, 21, 21],
            method_2_integer_reward=[21, 21, 58],
            method_3_status="READY",
            method_3_integer_challenge=[59, 20, 21],
            method_3_integer_reward=[20, 21, 59],
            is_current=True,
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_changelist_shows_final_scores(self):
        url = reverse("admin:classifications_classificationsnapshot_changelist")
        response = self.client.get(url)
        self.assertContains(response, "60 / 20 / 20")
        self.assertContains(response, "20 / 20 / 60")

    def test_change_view_shows_methods_and_final(self):
        url = reverse(
            "admin:classifications_classificationsnapshot_change",
            args=(self.snapshot.pk,),
        )
        response = self.client.get(url)
        self.assertContains(response, "Final Classification")
        self.assertContains(response, "Method 1")
        self.assertContains(response, "Method 2")
        self.assertContains(response, "Method 3")

    def test_derived_admin_is_readonly(self):
        model_admin = admin.site._registry.get(ClassificationSnapshot)
        assert model_admin is not None
        request = RequestFactory().get("/")
        request.user = self.superuser
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))


class EditorialClassificationMediaTests(TestCase):
    def test_admin_includes_game_name_truncation_css(self):
        model_admin = EditorialClassificationAdmin(EditorialClassification, admin.site)
        self.assertIn("classifications/admin.css", str(model_admin.media))

    def test_game_uses_autocomplete(self):
        model_admin = EditorialClassificationAdmin(EditorialClassification, admin.site)
        self.assertIn("game", model_admin.autocomplete_fields)
