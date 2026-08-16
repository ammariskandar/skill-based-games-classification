"""
Manual release-date Admin input format tests — SBGC-62.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from games.models import Game, ListingStatus, SourceType
from games.types import ContentType


class ManualReleaseDateInputFormatTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="date-admin", password="pw")
        self.client.force_login(self.user)
        self.url = reverse("admin:games_game_add")

    def _post(self, slug, release_date_value):
        data = {
            "source_type": SourceType.MANUAL,
            "external_id": "",
            "name": f"Date {slug}",
            "slug": slug,
            "content_type": ContentType.GAME,
            "listing_status": ListingStatus.DRAFT,
            "release_date": release_date_value,
            "developer": "Date Studio",
            "manual_description": "",
            "manual_image_url": "",
            "manual_website_url": "",
        }
        return self.client.post(self.url, data)

    def test_all_four_formats_normalize_to_same_date(self):
        formats = {
            "date-iso": "2026-08-16",
            "date-dash-dmy": "16-08-2026",
            "date-slash-dmy": "16/08/2026",
            "date-slash-ymd": "2026/08/16",
        }
        for slug, value in formats.items():
            with self.subTest(value=value):
                response = self._post(slug, value)
                self.assertEqual(response.status_code, 302)
                game = Game.objects.get(slug=slug)
                self.assertEqual(game.release_date, date(2026, 8, 16))

    def test_unsupported_format_rejected_cleanly(self):
        response = self._post("date-unsupported", "16 Aug 2026")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Game.objects.filter(slug="date-unsupported").exists())

    def test_ambiguous_month_day_format_rejected(self):
        response = self._post("date-mmdd", "08/16/2026")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Game.objects.filter(slug="date-mmdd").exists())


class UserFacingHelpTextTests(TestCase):
    def _help_text(self, field_name: str) -> str:
        return str(getattr(Game._meta.get_field(field_name), "help_text", "") or "")

    def test_manual_metadata_help_text_has_no_internal_references(self):
        for field_name in (
            "release_date",
            "developer",
            "steam_image_url",
            "last_steam_refresh_at",
        ):
            self.assertNotIn("SBGC", self._help_text(field_name))

    def test_release_date_help_text_documents_accepted_formats(self):
        release_help = self._help_text("release_date")
        for token in ("YYYY-MM-DD", "DD-MM-YYYY", "DD/MM/YYYY", "YYYY/MM/DD"):
            self.assertIn(token, release_help)
