"""
Steam metadata normalization tests — SBGC-188.

Pure-function tests: no network, no database.
"""

from __future__ import annotations

from datetime import date

from django.test import SimpleTestCase

from games.services.steam.normalization import (
    normalize_steam_description,
    normalize_steam_developer,
    normalize_steam_release_date,
)


class DescriptionTests(SimpleTestCase):
    def test_plain_text(self):
        self.assertEqual(normalize_steam_description("A test game."), "A test game.")

    def test_trims_whitespace(self):
        self.assertEqual(normalize_steam_description("  padded  "), "padded")

    def test_decodes_html_entities(self):
        self.assertEqual(
            normalize_steam_description("The &quot;Perpetual&quot; &amp; co-op"),
            'The "Perpetual" & co-op',
        )

    def test_preserves_unicode(self):
        self.assertEqual(
            normalize_steam_description("Pokémon — épée"), "Pokémon — épée"
        )

    def test_keeps_html_looking_text_safe(self):
        # Entities decode; literal tags stay as text (frontend escapes them).
        self.assertEqual(
            normalize_steam_description("&lt;b&gt;bold&lt;/b&gt;"),
            "<b>bold</b>",
        )

    def test_absent_values_return_none(self):
        self.assertIsNone(normalize_steam_description(None))
        self.assertIsNone(normalize_steam_description(""))
        self.assertIsNone(normalize_steam_description("   "))
        self.assertIsNone(normalize_steam_description(123))


class DeveloperTests(SimpleTestCase):
    def test_single(self):
        self.assertEqual(normalize_steam_developer(["Valve"]), "Valve")

    def test_multiple_preserves_order(self):
        self.assertEqual(
            normalize_steam_developer(["Studio A", "Studio B"]),
            "Studio A, Studio B",
        )

    def test_ignores_blank_entries(self):
        self.assertEqual(
            normalize_steam_developer(["Studio A", "", "  ", "Studio B"]),
            "Studio A, Studio B",
        )

    def test_dedup_exact(self):
        self.assertEqual(
            normalize_steam_developer(["Studio A", "Studio A"]),
            "Studio A",
        )

    def test_absent_values_return_none(self):
        self.assertIsNone(normalize_steam_developer(None))
        self.assertIsNone(normalize_steam_developer([]))
        self.assertIsNone(normalize_steam_developer("Valve"))


class ReleaseDateTests(SimpleTestCase):
    def test_released_date(self):
        self.assertEqual(
            normalize_steam_release_date(
                {"coming_soon": False, "date": "18 Apr, 2011"}
            ),
            date(2011, 4, 18),
        )

    def test_single_digit_day(self):
        self.assertEqual(
            normalize_steam_release_date({"coming_soon": False, "date": "1 Jan, 2000"}),
            date(2000, 1, 1),
        )

    def test_missing(self):
        self.assertIsNone(normalize_steam_release_date(None))

    def test_coming_soon(self):
        self.assertIsNone(
            normalize_steam_release_date({"coming_soon": True, "date": "Coming soon"})
        )

    def test_malformed_date(self):
        self.assertIsNone(
            normalize_steam_release_date({"coming_soon": False, "date": "not-a-date"})
        )

    def test_non_dict(self):
        self.assertIsNone(normalize_steam_release_date("18 Apr, 2011"))
