"""
Manual Game workflow tests — SBGC-62.

End-to-end workflow evidence across the service and Admin boundaries.
These tests intentionally combine layers instead of re-testing every
unit-level permutation already covered in SBGC-59/60/61 suites.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from classifications.services.editorial import (
    ScoreDistribution,
    set_editorial_classification,
)
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from games.models import Game, ListingStatus, SourceType
from games.services.imports.steam import SteamGameRefreshService, SteamRefreshError
from games.services.manual import create_manual_game, update_manual_game
from games.types import ContentType


class ManualGameWorkflowTests(TestCase):
    def test_create_full_workflow(self):
        game = create_manual_game(
            name="Chess",
            slug="chess-workflow",
            content_type=ContentType.GAME,
            listing_status=ListingStatus.DRAFT,
            release_date=date(2026, 1, 15),
            developer="Workflow Studio",
            manual_description="A description.",
            manual_image_url="https://example.com/chess.jpg",
            manual_website_url="https://example.com",
        )

        self.assertEqual(game.source_type, SourceType.MANUAL)
        self.assertIsNone(game.external_id)
        self.assertEqual(game.steam_image_url, "")
        self.assertIsNone(game.last_steam_refresh_at)
        self.assertEqual(game.release_date, date(2026, 1, 15))
        self.assertEqual(game.developer, "Workflow Studio")
        self.assertEqual(game.manual_description, "A description.")
        self.assertEqual(game.manual_image_url, "https://example.com/chess.jpg")
        self.assertEqual(game.manual_website_url, "https://example.com")

    def test_edit_workflow(self):
        game = create_manual_game(
            name="Chess",
            slug="chess-workflow",
            developer="Old Studio",
        )

        updated = update_manual_game(
            game,
            name="Chess Renamed",
            listing_status=ListingStatus.PUBLISHED,
            release_date=date(2026, 2, 1),
            developer="New Studio",
            manual_description="updated",
            manual_image_url="https://example.com/new.jpg",
        )

        self.assertEqual(updated.pk, game.pk)
        self.assertEqual(updated.name, "Chess Renamed")
        self.assertEqual(updated.slug, "chess-workflow")  # stable on name change
        self.assertEqual(updated.source_type, SourceType.MANUAL)
        self.assertIsNone(updated.external_id)
        self.assertEqual(updated.steam_image_url, "")
        self.assertIsNone(updated.last_steam_refresh_at)
        self.assertEqual(updated.listing_status, ListingStatus.PUBLISHED)
        self.assertEqual(updated.release_date, date(2026, 2, 1))
        self.assertEqual(updated.developer, "New Studio")

    def test_asset_lifecycle_replace_clear_and_invalid_unchanged(self):
        game = create_manual_game(
            name="Chess",
            manual_image_url="https://example.com/one.jpg",
        )

        update_manual_game(game, manual_image_url="https://example.com/two.jpg")
        game.refresh_from_db()
        self.assertEqual(game.manual_image_url, "https://example.com/two.jpg")

        update_manual_game(game, manual_image_url="")
        game.refresh_from_db()
        self.assertEqual(game.manual_image_url, "")

        # Invalid replacement leaves the previous (cleared) state intact.
        with self.assertRaises(ValidationError):
            update_manual_game(game, manual_image_url="http://example.com/bad.jpg")
        game.refresh_from_db()
        self.assertEqual(game.manual_image_url, "")

    def test_steam_refresh_rejected_before_network(self):
        manual = create_manual_game(name="Chess")
        foundation = MagicMock()
        persistence = MagicMock()
        service = SteamGameRefreshService(foundation, persistence)

        with self.assertRaises(SteamRefreshError):
            service.refresh(manual)

        foundation.prepare_candidate.assert_not_called()

    def test_listing_draft_then_published(self):
        game = create_manual_game(name="Chess", listing_status=ListingStatus.DRAFT)
        self.assertNotIn(game, Game.objects.publicly_listable())

        update_manual_game(game, listing_status=ListingStatus.PUBLISHED)
        game.refresh_from_db()
        self.assertIn(game, Game.objects.publicly_listable())

    def test_published_manual_non_game_excluded(self):
        game = create_manual_game(
            name="Manual DLC",
            content_type=ContentType.DLC,
            listing_status=ListingStatus.PUBLISHED,
        )
        self.assertNotIn(game, Game.objects.publicly_listable())

    def test_duplicate_name_allowed_and_duplicate_slug_rejected(self):
        create_manual_game(name="Chess", slug="chess-one")
        create_manual_game(name="Chess", slug="chess-two")
        self.assertEqual(Game.objects.filter(name="Chess").count(), 2)

        with self.assertRaises(ValidationError):
            create_manual_game(name="Chess Three", slug="chess-one")
        self.assertEqual(Game.objects.filter(slug="chess-one").count(), 1)

    def test_classification_preserved_on_edit(self):
        game = create_manual_game(name="Chess")
        user = User.objects.create_user(username="workflow-editor", password="pw")
        parent = set_editorial_classification(
            game=game,
            updated_by=user,
            challenge=ScoreDistribution(micro=30, mystiko=30, macro=40),
            reward=ScoreDistribution(micro=50, mystiko=20, macro=30),
            notes="workflow notes",
        )

        update_manual_game(game, name="Chess Renamed", manual_description="changed")

        parent.refresh_from_db()
        self.assertEqual(parent.notes, "workflow notes")
        self.assertEqual(parent.challenge_profile.micro_score, 30)
        self.assertEqual(parent.challenge_profile.mystiko_score, 30)
        self.assertEqual(parent.challenge_profile.macro_score, 40)
        self.assertEqual(parent.reward_profile.micro_score, 50)
        self.assertEqual(parent.reward_profile.mystiko_score, 20)
        self.assertEqual(parent.reward_profile.macro_score, 30)


class ManualGameAdminWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin-workflow", password="pw"
        )
        self.client.force_login(self.user)
        self.add_url = reverse("admin:games_game_add")

    def _change_url(self, game):
        return reverse("admin:games_game_change", args=(game.pk,))

    def test_admin_create_then_edit(self):
        data = {
            "source_type": SourceType.MANUAL,
            "external_id": "",
            "name": "Workflow Manual",
            "slug": "workflow-manual",
            "content_type": ContentType.GAME,
            "listing_status": ListingStatus.DRAFT,
            "release_date": "2026-01-15",
            "developer": "Workflow Studio",
            "manual_description": "initial",
            "manual_image_url": "https://example.com/one.jpg",
            "manual_website_url": "https://example.com",
        }
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 302)
        game = Game.objects.get(slug="workflow-manual")
        self.assertEqual(game.source_type, SourceType.MANUAL)
        self.assertIsNone(game.external_id)

        edit_data = {
            "source_type": SourceType.MANUAL,
            "external_id": "",
            "name": "Workflow Manual Renamed",
            "slug": "workflow-manual",
            "content_type": ContentType.GAME,
            "listing_status": ListingStatus.PUBLISHED,
            "release_date": "2026-02-01",
            "developer": "Renamed Studio",
            "manual_description": "updated",
            "manual_image_url": "https://example.com/two.jpg",
            "manual_website_url": "https://example.com",
            "_changelist_filters": "",
        }
        response = self.client.post(self._change_url(game), edit_data)
        self.assertEqual(response.status_code, 302)

        game.refresh_from_db()
        self.assertEqual(game.name, "Workflow Manual Renamed")
        self.assertEqual(game.slug, "workflow-manual")
        self.assertEqual(game.source_type, SourceType.MANUAL)
        self.assertIsNone(game.external_id)
        self.assertEqual(game.steam_image_url, "")
        self.assertIsNone(game.last_steam_refresh_at)
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)
        self.assertEqual(game.developer, "Renamed Studio")
        self.assertEqual(game.manual_image_url, "https://example.com/two.jpg")

    def test_admin_invalid_cases_no_partial_persist(self):
        cases = [
            ("blank name", {"name": "   ", "slug": "workflow-blank-name"}),
            (
                "invalid manual image URL",
                {
                    "name": "Workflow Bad Image",
                    "slug": "workflow-bad-image",
                    "manual_image_url": "http://example.com/img.jpg",
                },
            ),
        ]
        for label, overrides in cases:
            with self.subTest(label=label):
                data = {
                    "source_type": SourceType.MANUAL,
                    "external_id": "",
                    "name": "Workflow",
                    "slug": "workflow-unused",
                    "content_type": ContentType.GAME,
                    "listing_status": ListingStatus.DRAFT,
                }
                data.update(overrides)
                response = self.client.post(self.add_url, data)
                self.assertEqual(response.status_code, 200)
                slug = overrides.get("slug")
                if slug:
                    self.assertFalse(Game.objects.filter(slug=slug).exists())

    def test_duplicate_slug_rejected_in_admin(self):
        create_manual_game(name="Chess", slug="workflow-dup")
        data = {
            "source_type": SourceType.MANUAL,
            "external_id": "",
            "name": "Chess Two",
            "slug": "workflow-dup",
            "content_type": ContentType.GAME,
            "listing_status": ListingStatus.DRAFT,
        }
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Game.objects.filter(slug="workflow-dup").count(), 1)


class ManualGameNoNetworkWorkflowTests(TestCase):
    def test_service_create_and_edit_do_not_touch_steam(self):
        with patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("SteamClient must not be called"),
        ):
            game = create_manual_game(
                name="No Network",
                manual_image_url="https://example.com/no-network.jpg",
            )
            update_manual_game(game, name="No Network Renamed")
