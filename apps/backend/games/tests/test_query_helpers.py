"""
Game query helper tests — SBGC-49.

Source filtering, editorial classification helpers, dominant-skill
annotations/filtering, score filtering/sorting, query-count behaviour,
and no-network evidence.
"""

from __future__ import annotations

from unittest.mock import patch

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
)
from classifications.skills import EditorialProfile, SkillCategory
from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.test import TestCase

from games.models import ContentType, Game, ListingStatus, SourceType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make(**kw):
    defaults = {
        "source_type": SourceType.MANUAL,
        "content_type": ContentType.GAME,
        "listing_status": ListingStatus.PUBLISHED,
    }
    return Game.objects.create(**{**defaults, **kw})


def _classify(game, user, ch=(50, 20, 30), rw=(10, 30, 60)):
    parent = EditorialClassification.objects.create(game=game, updated_by=user)
    ChallengeProfile.objects.create(
        classification=parent,
        micro_score=ch[0],
        mystiko_score=ch[1],
        macro_score=ch[2],
    )
    RewardProfile.objects.create(
        classification=parent,
        micro_score=rw[0],
        mystiko_score=rw[1],
        macro_score=rw[2],
    )


# ---------------------------------------------------------------------------
# Source helpers
# ---------------------------------------------------------------------------


class SourceHelperTests(TestCase):
    def setUp(self):
        _make(
            name="Steam Game",
            slug="steam-game",
            source_type=SourceType.STEAM,
            external_id="100",
        )
        _make(name="Manual Game", slug="manual-game")

    def test_steam_returns_only_steam(self):
        qs = Game.objects.steam()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().source_type, SourceType.STEAM)

    def test_manual_returns_only_manual(self):
        qs = Game.objects.manual()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().source_type, SourceType.MANUAL)

    def test_steam_chainable_with_publicly_listable(self):
        qs = Game.objects.steam().publicly_listable()
        self.assertEqual(qs.count(), 1)

    def test_manual_chainable_with_publicly_listable(self):
        qs = Game.objects.manual().publicly_listable()
        self.assertEqual(qs.count(), 1)


# ---------------------------------------------------------------------------
# Editorially classified
# ---------------------------------------------------------------------------


class EditoriallyClassifiedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ec_u", password="p")
        self.no_parent = _make(name="No Parent", slug="no-parent")
        self.parent_only = _make(name="Parent Only", slug="parent-only")
        EditorialClassification.objects.create(
            game=self.parent_only, updated_by=self.user
        )
        self.ch_only = _make(name="CH Only", slug="ch-only")
        pc = EditorialClassification.objects.create(
            game=self.ch_only, updated_by=self.user
        )
        ChallengeProfile.objects.create(
            classification=pc, micro_score=50, mystiko_score=20, macro_score=30
        )
        self.complete = _make(name="Complete", slug="complete")
        _classify(self.complete, self.user)

    def test_excludes_no_parent(self):
        qs = Game.objects.editorially_classified()
        self.assertNotIn(self.no_parent.pk, qs.values_list("pk", flat=True))

    def test_excludes_parent_only(self):
        qs = Game.objects.editorially_classified()
        self.assertNotIn(self.parent_only.pk, qs.values_list("pk", flat=True))

    def test_excludes_challenge_only(self):
        qs = Game.objects.editorially_classified()
        self.assertNotIn(self.ch_only.pk, qs.values_list("pk", flat=True))

    def test_includes_complete(self):
        qs = Game.objects.editorially_classified()
        self.assertIn(self.complete.pk, qs.values_list("pk", flat=True))

    def test_with_editorial_profiles_no_filter(self):
        """with_editorial_profiles does not filter — returns all Games."""
        qs = Game.objects.with_editorial_profiles()
        self.assertEqual(qs.count(), Game.objects.count())

    def test_with_editorial_profiles_select_related(self):
        g = Game.objects.with_editorial_profiles().get(pk=self.complete.pk)
        with self.assertNumQueries(0):
            _ = g.editorial_classification
            _ = g.editorial_classification.challenge_profile
            _ = g.editorial_classification.reward_profile


# ---------------------------------------------------------------------------
# Score filtering
# ---------------------------------------------------------------------------


class ScoreFilteringTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sf_u", password="p")

        self.low = _make(name="SF Low", slug="sf-low")
        _classify(self.low, self.user, ch=(10, 20, 70), rw=(5, 10, 85))

        self.high = _make(name="SF High", slug="sf-high")
        _classify(self.high, self.user, ch=(80, 10, 10), rw=(90, 5, 5))

    def test_minimum_only(self):
        qs = Game.objects.filter_by_editorial_score(
            profile=EditorialProfile.CHALLENGE,
            category=SkillCategory.MICRO,
            minimum=50,
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().slug, "sf-high")

    def test_maximum_only(self):
        qs = Game.objects.filter_by_editorial_score(
            profile=EditorialProfile.CHALLENGE,
            category=SkillCategory.MICRO,
            maximum=50,
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().slug, "sf-low")

    def test_inclusive_bounds(self):
        qs = Game.objects.filter_by_editorial_score(
            profile=EditorialProfile.CHALLENGE,
            category=SkillCategory.MICRO,
            minimum=10,
            maximum=80,
        )
        self.assertEqual(qs.count(), 2)

    def test_both_bounds_none_raises(self):
        with self.assertRaises(ValueError):
            Game.objects.filter_by_editorial_score(
                profile=EditorialProfile.CHALLENGE,
                category=SkillCategory.MICRO,
            )

    def test_minimum_exceeds_maximum_raises(self):
        with self.assertRaises(ValueError):
            Game.objects.filter_by_editorial_score(
                profile=EditorialProfile.CHALLENGE,
                category=SkillCategory.MICRO,
                minimum=80,
                maximum=10,
            )

    def test_bool_bound_rejected(self):
        with self.assertRaises(TypeError):
            Game.objects.filter_by_editorial_score(
                profile=EditorialProfile.CHALLENGE,
                category=SkillCategory.MICRO,
                minimum=True,
            )

    def test_float_bound_rejected(self):
        with self.assertRaises(TypeError):
            Game.objects.filter_by_editorial_score(
                profile=EditorialProfile.CHALLENGE,
                category=SkillCategory.MICRO,
                minimum=50.5,
            )

    def test_all_six_paths_supported(self):
        for profile in EditorialProfile.values:
            for category in SkillCategory.values:
                qs = Game.objects.filter_by_editorial_score(
                    profile=profile, category=category, minimum=0, maximum=100
                )
                self.assertIsInstance(qs, QuerySet)


# ---------------------------------------------------------------------------
# Score sorting
# ---------------------------------------------------------------------------


class ScoreSortingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ss_u", password="p")

        self.a = _make(name="Sort A", slug="sort-a")
        _classify(self.a, self.user, ch=(30, 40, 30), rw=(50, 20, 30))

        self.b = _make(name="Sort B", slug="sort-b")
        _classify(self.b, self.user, ch=(70, 20, 10), rw=(70, 20, 10))

    def test_descending(self):
        qs = Game.objects.order_by_editorial_score(
            profile=EditorialProfile.CHALLENGE,
            category=SkillCategory.MICRO,
            descending=True,
        )
        slugs = list(qs.values_list("slug", flat=True))
        self.assertEqual(slugs, ["sort-b", "sort-a"])

    def test_ascending(self):
        qs = Game.objects.order_by_editorial_score(
            profile=EditorialProfile.CHALLENGE,
            category=SkillCategory.MICRO,
            descending=False,
        )
        slugs = list(qs.values_list("slug", flat=True))
        self.assertEqual(slugs, ["sort-a", "sort-b"])

    def test_descending_not_bool_raises(self):
        with self.assertRaises(TypeError):
            Game.objects.order_by_editorial_score(
                profile=EditorialProfile.CHALLENGE,
                category=SkillCategory.MICRO,
                descending=1,
            )

    def test_all_six_paths(self):
        for profile in EditorialProfile.values:
            for category in SkillCategory.values:
                qs = Game.objects.order_by_editorial_score(
                    profile=profile,
                    category=category,
                )
                self.assertIsInstance(qs, QuerySet)


# ---------------------------------------------------------------------------
# Default manager
# ---------------------------------------------------------------------------


class DefaultManagerTests(TestCase):
    def setUp(self):
        _make(
            name="DM Published",
            slug="dm-pub",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        _make(
            name="DM DLC",
            slug="dm-dlc",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
        )
        _make(
            name="DM Draft",
            slug="dm-draft",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.DRAFT,
        )

    def test_all_returns_every_record(self):
        self.assertEqual(Game.objects.all().count(), 3)

    def test_all_includes_non_game(self):
        slugs = set(Game.objects.all().values_list("slug", flat=True))
        self.assertIn("dm-dlc", slugs)

    def test_all_includes_draft(self):
        slugs = set(Game.objects.all().values_list("slug", flat=True))
        self.assertIn("dm-draft", slugs)


# ---------------------------------------------------------------------------
# Query count
# ---------------------------------------------------------------------------


class QueryCountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="qc_u", password="p")
        for i in range(3):
            g = _make(name=f"QC {i}", slug=f"qc-{i}")
            _classify(g, self.user)

    def test_with_editorial_profiles_single_query(self):
        with self.assertNumQueries(1):
            qs = list(Game.objects.editorially_classified().with_editorial_profiles())
            self.assertEqual(len(qs), 3)

    def test_no_n_plus_one(self):
        """Accessing profiles after select_related incurs no extra queries."""
        games = list(Game.objects.editorially_classified().with_editorial_profiles())
        with self.assertNumQueries(0):
            for g in games:
                _ = g.editorial_classification.challenge_profile.micro_score
                _ = g.editorial_classification.reward_profile.macro_score


# ---------------------------------------------------------------------------
# No-network
# ---------------------------------------------------------------------------


class NoNetworkTests(TestCase):
    def _steam_guard(self):
        return patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("SteamClient must not be called"),
        )

    def setUp(self):
        self.user = User.objects.create_user(username="nn_u", password="p")
        self.g = _make(name="NoNet", slug="nonet")
        _classify(self.g, self.user)

    def test_steam_helper_no_steam(self):
        with self._steam_guard():
            list(Game.objects.steam())

    def test_classified_helper_no_steam(self):
        with self._steam_guard():
            list(Game.objects.editorially_classified())

    def test_score_filter_no_steam(self):
        with self._steam_guard():
            list(
                Game.objects.order_by_editorial_score(
                    profile=EditorialProfile.CHALLENGE,
                    category=SkillCategory.MICRO,
                )
            )
