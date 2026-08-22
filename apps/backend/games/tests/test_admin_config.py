"""
Game Admin configuration tests — SBGC-67.

Covers the changelist columns (developer, submission count, current
classification status), search, filters, ordering, and fieldsets.  Existing
source-editability / readonly / delete behavior is already protected by
``test_admin_validation.py`` and ``test_game_deletion_admin.py``.
"""

from __future__ import annotations

from classifications.models import CalculationEpoch, ClassificationSnapshot
from classifications.services.editorial import (
    ScoreDistribution,
    set_editorial_classification,
)
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from games.models import Game, ListingStatus, SourceType
from games.types import ContentType


class _GameAdminTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="config-admin", password="pw"
        )
        cls.add_url = reverse("admin:games_game_add")
        cls.changelist_url = reverse("admin:games_game_changelist")

    def setUp(self):
        self.client.force_login(self.superuser)


class ChangelistColumnTests(_GameAdminTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.steam = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Counter-Strike",
            slug="counter-strike",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
            developer="Valve",
        )
        set_editorial_classification(
            game=cls.steam,
            updated_by=cls.superuser,
            challenge=ScoreDistribution(micro=50, mystiko=30, macro=20),
            reward=ScoreDistribution(micro=20, mystiko=30, macro=50),
        )
        epoch = CalculationEpoch.objects.create(
            epoch_id="config-epoch",
            cutoff_at=timezone.now(),
            master_version="STATISTICAL_MODEL_V1.0.0",
        )
        ClassificationSnapshot.objects.create(
            game=cls.steam,
            epoch=epoch,
            regime="provisional",
            status="READY",
            cutoff_at=timezone.now(),
            confidence_label="Low",
            is_current=True,
        )
        cls.plain = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Empty Manual",
            slug="empty-manual",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.DRAFT,
        )

    def test_changelist_shows_developer(self):
        response = self.client.get(self.changelist_url)
        self.assertContains(response, "Valve")

    def test_changelist_shows_submission_count(self):
        response = self.client.get(self.changelist_url)
        # One submission on the Steam game; zero on the manual game.
        self.assertContains(response, "Counter-Strike")
        self.assertIn("1", response.content.decode())

    def test_changelist_shows_ready_classification_status(self):
        response = self.client.get(self.changelist_url)
        self.assertContains(response, "Ready · Low")

    def test_changelist_shows_empty_classification_status(self):
        response = self.client.get(self.changelist_url)
        self.assertContains(response, "Empty Manual")


class SearchTests(_GameAdminTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.steam = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="570",
            name="Dota 2",
            slug="dota-2",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
            developer="Valve",
        )
        cls.manual = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Chess",
            slug="chess",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
            developer="FIDE",
        )

    def test_search_by_name(self):
        response = self.client.get(self.changelist_url, {"q": "Dota"})
        self.assertContains(response, "Dota 2")
        self.assertNotContains(response, "Chess")

    def test_search_by_slug(self):
        response = self.client.get(self.changelist_url, {"q": "chess"})
        self.assertContains(response, "Chess")
        self.assertNotContains(response, "Dota 2")

    def test_search_by_external_id(self):
        response = self.client.get(self.changelist_url, {"q": "570"})
        self.assertContains(response, "Dota 2")
        self.assertNotContains(response, "Chess")

    def test_search_by_developer(self):
        response = self.client.get(self.changelist_url, {"q": "FIDE"})
        self.assertContains(response, "Chess")
        self.assertNotContains(response, "Dota 2")


class FilterTests(_GameAdminTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.steam_game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="400",
            name="Portal",
            slug="portal",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        cls.manual_dlc = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Portal DLC",
            slug="portal-dlc",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.DRAFT,
        )

    def test_filter_by_source_type(self):
        response = self.client.get(self.changelist_url, {"source_type__exact": "steam"})
        self.assertContains(response, "Portal")
        self.assertNotContains(response, "Portal DLC")

    def test_filter_by_content_type(self):
        response = self.client.get(self.changelist_url, {"content_type__exact": "dlc"})
        self.assertContains(response, "Portal DLC")
        self.assertNotContains(response, "Portal</a>")

    def test_filter_by_listing_status(self):
        response = self.client.get(
            self.changelist_url, {"listing_status__exact": "published"}
        )
        self.assertContains(response, "Portal")
        self.assertNotContains(response, "Portal DLC")


class OrderingTests(_GameAdminTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.names = ["Zulu", "Alpha", "Mike"]
        for name in cls.names:
            Game.objects.create(
                source_type=SourceType.MANUAL,
                name=name,
                slug=name.lower(),
                content_type=ContentType.GAME,
                listing_status=ListingStatus.DRAFT,
            )

    def test_changelist_orders_by_name(self):
        response = self.client.get(self.changelist_url)
        content = response.content.decode()
        positions = [content.index(name) for name in sorted(self.names)]
        self.assertEqual(positions, sorted(positions))


class FieldsetTests(_GameAdminTestCase):
    def test_add_form_groups_fields(self):
        response = self.client.get(self.add_url)
        for heading in (
            "Identity",
            "Publication",
            "Editable metadata",
            "Steam metadata",
            "System",
        ):
            self.assertContains(response, heading)

    def test_edit_form_groups_fields(self):
        game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Grouped",
            slug="grouped",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.DRAFT,
        )
        response = self.client.get(reverse("admin:games_game_change", args=(game.pk,)))
        for heading in (
            "Identity",
            "Publication",
            "Editable metadata",
            "Steam metadata",
            "System",
        ):
            self.assertContains(response, heading)
