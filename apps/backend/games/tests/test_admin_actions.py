"""
Game Admin action tests — SBGC-69 / SBGC-70.

Covers publish / hide / archive bulk actions, the continuing absence of
``delete_selected``, and Admin audit-log entry creation.  The existing Steam
refresh action is already covered by ``test_admin_refresh.py``.
"""

from __future__ import annotations

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from games.models import Game, ListingStatus, SourceType


class GameStateActionTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="state-admin", password="pw"
        )
        self.client.force_login(self.superuser)
        self.url = reverse("admin:games_game_changelist")

    def _post_action(self, action, game_pks):
        return self.client.post(
            self.url,
            {
                "action": action,
                "_selected_action": [str(pk) for pk in game_pks],
                "index": "0",
            },
            follow=True,
        )

    def _manual(self, name, listing_status=ListingStatus.DRAFT):
        return Game.objects.create(
            source_type=SourceType.MANUAL,
            name=name,
            slug=name.lower().replace(" ", "-"),
            listing_status=listing_status,
        )

    def test_publish_selected(self):
        game = self._manual("Publish Me")
        response = self._post_action("publish_selected", [game.pk])
        game.refresh_from_db()
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)
        self.assertContains(response, "1 Games published")

    def test_publish_skips_already_published(self):
        published = self._manual("Already Published", ListingStatus.PUBLISHED)
        draft = self._manual("Draft To Publish")
        response = self._post_action("publish_selected", [published.pk, draft.pk])
        draft.refresh_from_db()
        self.assertEqual(draft.listing_status, ListingStatus.PUBLISHED)
        self.assertContains(response, "1 Games published")
        self.assertContains(response, "1 skipped")

    def test_hide_selected(self):
        game = self._manual("Hide Me", ListingStatus.PUBLISHED)
        self._post_action("hide_selected", [game.pk])
        game.refresh_from_db()
        self.assertEqual(game.listing_status, ListingStatus.DRAFT)

    def test_archive_selected(self):
        game = self._manual("Archive Me")
        self._post_action("archive_selected", [game.pk])
        game.refresh_from_db()
        self.assertEqual(game.listing_status, ListingStatus.ARCHIVED)

    def test_source_identity_unaffected(self):
        game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Source Game",
            slug="source-game",
            listing_status=ListingStatus.DRAFT,
        )
        self._post_action("publish_selected", [game.pk])
        game.refresh_from_db()
        self.assertEqual(game.source_type, SourceType.STEAM)
        self.assertEqual(game.external_id, "730")
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)

    def test_delete_selected_still_absent(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "delete_selected")

    def test_publish_action_creates_log_entry(self):
        game = self._manual("Audited Publish")
        self._post_action("publish_selected", [game.pk])
        entry = LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Game),
            object_id=str(game.pk),
            action_flag=CHANGE,
        ).first()
        assert entry is not None
        self.assertEqual(entry.user, self.superuser)
        self.assertIn("published", entry.change_message)
