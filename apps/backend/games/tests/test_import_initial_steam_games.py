"""
``import_initial_steam_games`` command tests — SBGC-126.

Covers dry-run safety, batch field mapping, idempotent re-runs, and the limit
flag.  Every test stubs the Steam transport at the composition root, so no test
ever reaches Valve: the command's ``build_steam_import_service`` is patched to
return a real ``SteamGameImportService`` wired to a mocked
``SteamImportFoundation``.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from games.models import Game, ListingStatus, SourceType
from games.services.imports.steam import (
    SteamGameImportService,
    SteamGamePersistenceService,
)
from games.services.steam.dto import (
    LookupStatus,
    SteamAppLookupResult,
    SteamGameImportCandidate,
)
from games.services.steam.errors import SteamTimeoutError
from games.services.steam.import_foundation import SteamImportFoundation
from games.types import ContentType

MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "initial_catalogue_200.json"
)
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
STEAM_ENTRIES = [entry for entry in MANIFEST if entry["source"] == "STEAM"]

BUILDER_TARGET = (
    "games.management.commands.import_initial_steam_games.build_steam_import_service"
)


def _found(app_id: str, *, content_type: str = "game") -> SteamAppLookupResult:
    return SteamAppLookupResult(
        status=LookupStatus.FOUND,
        app_id=app_id,
        candidate=SteamGameImportCandidate(
            app_id=app_id,
            name=f"Catalogue Game {app_id}",
            content_type=content_type,
        ),
    )


def _service(*, content_type: str = "game", fail_for: str | None = None):
    """Real import service over a mocked foundation — no network, real persistence."""
    foundation = mock.MagicMock(spec=SteamImportFoundation)

    def prepare(app_id: str):
        if fail_for is not None and app_id == fail_for:
            raise SteamTimeoutError("timed out")
        return _found(app_id, content_type=content_type)

    foundation.prepare_candidate.side_effect = prepare
    return SteamGameImportService(foundation, SteamGamePersistenceService())


class DryRunTests(TestCase):
    def test_dry_run_writes_no_rows(self):
        out = StringIO()
        call_command("import_initial_steam_games", "--dry-run", stdout=out)

        self.assertEqual(Game.objects.count(), 0)
        self.assertIn("Would create: 175", out.getvalue())

    def test_dry_run_never_builds_the_steam_service(self):
        """Dry run must not open a transport — real network is unreachable by design."""
        with mock.patch(
            BUILDER_TARGET,
            side_effect=AssertionError("dry run must not build the Steam service"),
        ):
            call_command("import_initial_steam_games", "--dry-run", stdout=StringIO())

        self.assertEqual(Game.objects.count(), 0)

    def test_dry_run_honours_limit(self):
        out = StringIO()
        call_command(
            "import_initial_steam_games", "--dry-run", "--limit", "5", stdout=out
        )

        self.assertEqual(Game.objects.count(), 0)
        self.assertIn("Total:        5", out.getvalue())

    def test_dry_run_reports_update_for_an_existing_row(self):
        Game.objects.create(
            source_type=SourceType.STEAM,
            external_id=str(STEAM_ENTRIES[0]["steam_appid"]),
            name="Already Here",
            slug="already-here",
        )

        out = StringIO()
        call_command(
            "import_initial_steam_games", "--dry-run", "--limit", "1", stdout=out
        )

        self.assertIn("would update", out.getvalue())
        self.assertIn("Would update: 1", out.getvalue())


class BatchImportTests(TestCase):
    def test_import_maps_manifest_metadata_onto_created_games(self):
        with mock.patch(BUILDER_TARGET) as builder:
            builder.return_value = _service()
            out = StringIO()
            call_command(
                "import_initial_steam_games", "--limit", "5", "--delay", "0", stdout=out
            )

        self.assertEqual(Game.objects.count(), 5)
        self.assertIn("Created:  5", out.getvalue())

        for entry in STEAM_ENTRIES[:5]:
            game = Game.objects.get(external_id=str(entry["steam_appid"]))
            self.assertEqual(game.source_type, SourceType.STEAM)
            self.assertEqual(game.content_type, ContentType.GAME)
            self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)
            self.assertEqual(game.aesthetic, entry["primary_aesthetic"])

    def test_import_skips_unavailable_apps(self):
        with mock.patch(BUILDER_TARGET) as builder:
            builder.return_value = _service(
                fail_for=str(STEAM_ENTRIES[2]["steam_appid"])
            )
            out = StringIO()
            call_command(
                "import_initial_steam_games", "--limit", "5", "--delay", "0", stdout=out
            )

        # One transport failure is recorded, the remaining four still import.
        self.assertEqual(Game.objects.count(), 4)
        self.assertIn("Failed:   1", out.getvalue())
        self.assertIn("Errors: 1", out.getvalue())

    def test_non_game_content_is_imported_but_not_published(self):
        with mock.patch(BUILDER_TARGET) as builder:
            builder.return_value = _service(content_type="dlc")
            out = StringIO()
            call_command(
                "import_initial_steam_games", "--limit", "3", "--delay", "0", stdout=out
            )

        self.assertEqual(Game.objects.count(), 3)
        for entry in STEAM_ENTRIES[:3]:
            game = Game.objects.get(external_id=str(entry["steam_appid"]))
            self.assertEqual(game.listing_status, ListingStatus.DRAFT)
            self.assertIsNone(game.aesthetic)
        self.assertIn("Published (listing_status=PUBLISHED): 0", out.getvalue())

    def test_only_steam_entries_are_processed(self):
        with mock.patch(BUILDER_TARGET) as builder:
            builder.return_value = _service()
            call_command(
                "import_initial_steam_games",
                "--limit",
                "25",
                "--delay",
                "0",
                stdout=StringIO(),
            )

        self.assertEqual(Game.objects.count(), 25)
        self.assertEqual(Game.objects.filter(source_type=SourceType.MANUAL).count(), 0)


class IdempotencyTests(TestCase):
    def test_second_run_updates_without_duplicating_or_failing(self):
        with mock.patch(BUILDER_TARGET) as builder:
            builder.return_value = _service()
            first = StringIO()
            call_command(
                "import_initial_steam_games",
                "--limit",
                "5",
                "--delay",
                "0",
                stdout=first,
            )
            count_after_first = Game.objects.count()

            second = StringIO()
            call_command(
                "import_initial_steam_games",
                "--limit",
                "5",
                "--delay",
                "0",
                stdout=second,
            )

        self.assertEqual(count_after_first, 5)
        self.assertEqual(Game.objects.count(), 5)
        self.assertIn("Created:  0", second.getvalue())
        # Nothing changed on the second pass, so every entry is skipped as unchanged.
        self.assertIn("Skipped:  5", second.getvalue())

    def test_rerun_restores_published_status_and_aesthetic(self):
        """A row reverted to draft by hand is repaired on the next run."""
        with mock.patch(BUILDER_TARGET) as builder:
            builder.return_value = _service()
            call_command(
                "import_initial_steam_games",
                "--limit",
                "1",
                "--delay",
                "0",
                stdout=StringIO(),
            )

            entry = STEAM_ENTRIES[0]
            game = Game.objects.get(external_id=str(entry["steam_appid"]))
            game.listing_status = ListingStatus.DRAFT
            game.aesthetic = None
            game.save(update_fields=["listing_status", "aesthetic"])

            call_command(
                "import_initial_steam_games",
                "--limit",
                "1",
                "--delay",
                "0",
                stdout=StringIO(),
            )

        game.refresh_from_db()
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)
        self.assertEqual(game.aesthetic, entry["primary_aesthetic"])


class LimitFlagTests(TestCase):
    def test_limit_processes_exactly_n_records(self):
        with mock.patch(BUILDER_TARGET) as builder:
            builder.return_value = _service()
            out = StringIO()
            call_command(
                "import_initial_steam_games", "--limit", "5", "--delay", "0", stdout=out
            )

        self.assertEqual(Game.objects.count(), 5)
        self.assertIn("Total:    5", out.getvalue())

    def test_limit_larger_than_manifest_is_harmless(self):
        with mock.patch(BUILDER_TARGET) as builder:
            builder.return_value = _service()
            out = StringIO()
            call_command(
                "import_initial_steam_games",
                "--limit",
                "100000",
                "--delay",
                "0",
                stdout=out,
            )

        self.assertEqual(Game.objects.count(), 175)
        self.assertIn("Created:  175", out.getvalue())

    def test_negative_limit_is_rejected(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                "import_initial_steam_games", "--limit", "-1", stdout=StringIO()
            )

    def test_missing_manifest_is_rejected(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                "import_initial_steam_games",
                "--manifest",
                "/nonexistent/manifest.json",
                stdout=StringIO(),
            )
