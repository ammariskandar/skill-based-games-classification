"""
Initial catalogue manifest tests — SBGC-125.

Validates the curated 200-game dataset fixture that seeds the initial public
catalogue (Epic SBGC-20).  These are pure data checks — ``SimpleTestCase`` with
no database, no network, and no Steam calls.

Live AppID resolution against the Steam Store API is deliberately *not* a unit
test (it needs the network and is rate-limited).  Run
``scripts/verify-initial-catalogue.py --online`` to prove every AppID resolves
to a standalone base game before starting a bulk import.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from classifications.questionnaire.registry.v1.types import Dimension
from django.test import SimpleTestCase

from games.models import Aesthetic

MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "initial_catalogue_200.json"
)

EXPECTED_TOTAL = 200
EXPECTED_STEAM = 175
EXPECTED_MANUAL = 25

REQUIRED_KEYS = (
    "slug",
    "name",
    "source",
    "steam_appid",
    "primary_aesthetic",
    "secondary_aesthetic",
    "intended_dominant",
)


class InitialCatalogueManifestTests(SimpleTestCase):
    """Structural and invariant checks for the SBGC-125 catalogue manifest."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.entries = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_exists_and_is_a_list(self):
        self.assertTrue(MANIFEST_PATH.is_file())
        self.assertIsInstance(self.entries, list)

    def test_total_entry_count(self):
        self.assertEqual(len(self.entries), EXPECTED_TOTAL)

    def test_source_breakdown(self):
        sources = Counter(entry["source"] for entry in self.entries)
        self.assertEqual(sources["STEAM"], EXPECTED_STEAM)
        self.assertEqual(sources["MANUAL"], EXPECTED_MANUAL)
        self.assertEqual(set(sources), {"STEAM", "MANUAL"})

    def test_slugs_are_unique(self):
        slugs = [entry["slug"] for entry in self.entries]
        duplicates = [slug for slug, count in Counter(slugs).items() if count > 1]
        self.assertEqual(duplicates, [])

    def test_steam_appids_are_unique(self):
        appids = [
            entry["steam_appid"]
            for entry in self.entries
            if entry["steam_appid"] is not None
        ]
        duplicates = [appid for appid, count in Counter(appids).items() if count > 1]
        self.assertEqual(duplicates, [])
        self.assertEqual(len(appids), EXPECTED_STEAM)

    def test_every_entry_declares_the_required_keys(self):
        for entry in self.entries:
            missing = set(REQUIRED_KEYS) - set(entry)
            self.assertEqual(
                missing, set(), f"{entry.get('slug')} is missing {sorted(missing)}"
            )

    def test_steam_entries_carry_a_positive_integer_appid(self):
        for entry in self.entries:
            if entry["source"] != "STEAM":
                continue
            appid = entry["steam_appid"]
            self.assertIsInstance(
                appid, int, f"{entry['slug']} AppID is not an integer"
            )
            self.assertNotIsInstance(appid, bool)
            self.assertGreater(appid, 0, f"{entry['slug']} AppID must be positive")

    def test_manual_entries_have_no_appid_but_carry_provenance(self):
        for entry in self.entries:
            if entry["source"] != "MANUAL":
                continue
            self.assertIsNone(
                entry["steam_appid"], f"{entry['slug']} AppID must be null"
            )
            self.assertTrue(
                entry.get("developer"), f"{entry['slug']} is missing developer"
            )
            self.assertTrue(
                entry.get("release_date"), f"{entry['slug']} is missing release_date"
            )

    def test_aesthetics_match_the_canonical_enum(self):
        canonical = {choice.value for choice in Aesthetic}
        for entry in self.entries:
            self.assertIn(entry["primary_aesthetic"], canonical, entry["slug"])
            self.assertIn(entry["secondary_aesthetic"], canonical, entry["slug"])
            self.assertNotEqual(
                entry["primary_aesthetic"],
                entry["secondary_aesthetic"],
                f"{entry['slug']} repeats the same aesthetic twice",
            )

    def test_intended_dominant_matches_the_canonical_dimension_enum(self):
        canonical = {dimension.value for dimension in Dimension}
        for entry in self.entries:
            self.assertIn(entry["intended_dominant"], canonical, entry["slug"])

    def test_skill_bias_distribution_is_balanced(self):
        dominant = Counter(entry["intended_dominant"] for entry in self.entries)
        self.assertEqual(set(dominant), {"micro", "mystiko", "macro"})
        # Each dimension dominates roughly a third of the catalogue; allow a
        # modest band so curation can move a few titles without churn.
        for dimension in ("micro", "mystiko", "macro"):
            self.assertGreaterEqual(dominant[dimension], 55, dimension)
            self.assertLessEqual(dominant[dimension], 80, dimension)

    def test_all_four_aesthetics_are_represented_as_primary(self):
        primary = Counter(entry["primary_aesthetic"] for entry in self.entries)
        self.assertEqual(set(primary), {"SENSORY", "FANTASY", "NARRATIVE", "CHALLENGE"})
        for aesthetic in primary:
            self.assertGreaterEqual(primary[aesthetic], 15, aesthetic)
