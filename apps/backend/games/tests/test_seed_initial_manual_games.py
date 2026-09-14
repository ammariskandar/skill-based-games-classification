"""
``seed_initial_manual_games`` command tests — SBGC-127.

Covers dry-run safety, field mapping, idempotent re-runs, optional manifest
artwork, and manifest error handling.  Manual seeding is entirely local, so no
transport is mocked — these tests assert the command simply never needs one.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from games.models import Game, ListingStatus, SourceType
from games.types import ContentType

MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "initial_catalogue_200.json"
)
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
MANUAL_ENTRIES = [entry for entry in MANIFEST if entry["source"] == "MANUAL"]


def _write_manifest(entries: list[dict]) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(entries, handle)
    handle.close()
    return Path(handle.name)


class DryRunTests(TestCase):
    def test_dry_run_writes_no_rows(self):
        out = StringIO()
        call_command("seed_initial_manual_games", "--dry-run", stdout=out)

        self.assertEqual(Game.objects.count(), 0)
        self.assertIn("Would create: 25", out.getvalue())

    def test_dry_run_reports_update_for_an_existing_manual_game(self):
        Game.objects.create(
            source_type=SourceType.MANUAL,
            external_id=None,
            name="Already Here",
            slug=MANUAL_ENTRIES[0]["slug"],
        )

        out = StringIO()
        call_command("seed_initial_manual_games", "--dry-run", stdout=out)

        self.assertIn("would update", out.getvalue())
        self.assertIn("Would update: 1", out.getvalue())
        self.assertEqual(Game.objects.count(), 1)


class CleanExecutionTests(TestCase):
    def test_seeds_exactly_the_manual_entries(self):
        out = StringIO()
        call_command("seed_initial_manual_games", stdout=out)

        self.assertEqual(Game.objects.filter(source_type=SourceType.MANUAL).count(), 25)
        self.assertEqual(Game.objects.filter(source_type=SourceType.STEAM).count(), 0)
        self.assertIn("Created:   25", out.getvalue())

    def test_field_mapping_matches_the_manifest(self):
        call_command("seed_initial_manual_games", stdout=StringIO())

        for entry in MANUAL_ENTRIES:
            game = Game.objects.get(slug=entry["slug"])
            self.assertEqual(game.source_type, SourceType.MANUAL)
            self.assertIsNone(game.external_id)
            self.assertEqual(game.content_type, ContentType.GAME)
            self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)
            self.assertEqual(game.name, entry["name"])
            self.assertEqual(game.developer, entry["developer"])
            self.assertEqual(
                game.release_date, date.fromisoformat(entry["release_date"])
            )
            self.assertEqual(game.aesthetic, entry["primary_aesthetic"])

    def test_manual_artwork_is_left_blank_for_the_card_placeholder(self):
        call_command("seed_initial_manual_games", stdout=StringIO())

        game = Game.objects.get(slug=MANUAL_ENTRIES[0]["slug"])
        self.assertEqual(game.manual_image_url, "")
        self.assertEqual(game.manual_hero_url, "")
        self.assertEqual(game.manual_capsule_url, "")


class IdempotencyTests(TestCase):
    def test_second_run_creates_no_duplicates_and_raises_no_error(self):
        call_command("seed_initial_manual_games", stdout=StringIO())
        count_after_first = Game.objects.count()

        out = StringIO()
        call_command("seed_initial_manual_games", stdout=out)

        self.assertEqual(count_after_first, 25)
        self.assertEqual(Game.objects.count(), 25)
        self.assertIn("Created:   0", out.getvalue())
        self.assertIn("Unchanged: 25", out.getvalue())

    def test_rerun_repairs_a_reverted_row(self):
        call_command("seed_initial_manual_games", stdout=StringIO())

        entry = MANUAL_ENTRIES[0]
        game = Game.objects.get(slug=entry["slug"])
        game.listing_status = ListingStatus.DRAFT
        game.aesthetic = None
        game.save(update_fields=["listing_status", "aesthetic"])

        call_command("seed_initial_manual_games", stdout=StringIO())

        game.refresh_from_db()
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)
        self.assertEqual(game.aesthetic, entry["primary_aesthetic"])


class OptionalArtworkTests(TestCase):
    def test_manifest_artwork_is_honoured_when_present(self):
        entry = {
            "slug": "artwork-sample",
            "name": "Artwork Sample",
            "source": "MANUAL",
            "steam_appid": None,
            "developer": "Sample Studio",
            "release_date": "2020-01-02",
            "primary_aesthetic": "SENSORY",
            "secondary_aesthetic": "CHALLENGE",
            "intended_dominant": "micro",
            "manual_image_url": "https://cdn.example.com/portrait.webp",
            "manual_hero_url": "https://cdn.example.com/hero.webp",
            "manual_capsule_url": "https://cdn.example.com/capsule.webp",
        }
        path = _write_manifest([entry])
        self.addCleanup(path.unlink)

        call_command(
            "seed_initial_manual_games", "--manifest", str(path), stdout=StringIO()
        )

        game = Game.objects.get(slug="artwork-sample")
        self.assertEqual(game.manual_image_url, entry["manual_image_url"])
        self.assertEqual(game.manual_hero_url, entry["manual_hero_url"])
        self.assertEqual(game.manual_capsule_url, entry["manual_capsule_url"])
        self.assertEqual(game.aesthetic, "SENSORY")


class ManifestErrorTests(TestCase):
    def test_missing_manifest_is_rejected(self):
        with self.assertRaises(CommandError):
            call_command(
                "seed_initial_manual_games",
                "--manifest",
                "/nonexistent/manifest.json",
                stdout=StringIO(),
            )

    def test_malformed_release_date_is_rejected(self):
        entry = dict(MANUAL_ENTRIES[0])
        entry["release_date"] = "03/03/2017"
        path = _write_manifest([entry])
        self.addCleanup(path.unlink)

        with self.assertRaises(CommandError):
            call_command(
                "seed_initial_manual_games", "--manifest", str(path), stdout=StringIO()
            )

    def test_unknown_aesthetic_is_rejected(self):
        entry = dict(MANUAL_ENTRIES[0])
        entry["primary_aesthetic"] = "PLEASURE"
        path = _write_manifest([entry])
        self.addCleanup(path.unlink)

        with self.assertRaises(CommandError):
            call_command(
                "seed_initial_manual_games", "--manifest", str(path), stdout=StringIO()
            )

    def test_slug_collision_with_a_steam_game_fails_that_entry_only(self):
        colliding = MANUAL_ENTRIES[0]
        Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Steam Occupant",
            slug=colliding["slug"],
        )

        out = StringIO()
        call_command("seed_initial_manual_games", stdout=out)

        # The Steam row is untouched and the remaining 24 manual entries still seed.
        self.assertEqual(Game.objects.filter(source_type=SourceType.MANUAL).count(), 24)
        self.assertEqual(
            Game.objects.get(slug=colliding["slug"]).source_type, SourceType.STEAM
        )
        self.assertIn("Failed:    1", out.getvalue())
