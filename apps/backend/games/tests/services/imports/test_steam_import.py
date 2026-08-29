"""
Steam game import service tests — SBGC-54.

Orchestration tests: lookup → persistence boundary, unavailable handling,
error propagation, and the no-network-inside-transaction rule.
"""

from __future__ import annotations

from unittest import mock

from django.db import connection
from django.test import TestCase, TransactionTestCase

from games.models import Game, SourceType
from games.services.imports.steam import (
    SteamGameImportResult,
    SteamGameImportService,
    SteamGameImportStatus,
    SteamGamePersistenceService,
)
from games.services.steam.adapters import SteamMalformedPayloadError
from games.services.steam.dto import (
    LookupStatus,
    SteamAppId,
    SteamAppLookupResult,
    SteamGameImportCandidate,
)
from games.services.steam.errors import (
    SteamConnectionError,
    SteamRateLimitedError,
    SteamTimeoutError,
    SteamUpstreamError,
)
from games.services.steam.import_foundation import SteamImportFoundation
from games.services.steam.mapping import map_steam_product_type


def _candidate(
    app_id: str = "730",
    name: str = "Counter-Strike",
    content_type: str = "game",
) -> SteamGameImportCandidate:
    return SteamGameImportCandidate(
        app_id=app_id,
        name=name,
        content_type=content_type,
    )


def _found_lookup(
    app_id: str = "730",
    name: str = "Counter-Strike",
    content_type: str = "game",
) -> SteamAppLookupResult:
    return SteamAppLookupResult(
        status=LookupStatus.FOUND,
        app_id=app_id,
        candidate=_candidate(app_id, name, content_type),
    )


def _unavailable_lookup(app_id: str = "730") -> SteamAppLookupResult:
    return SteamAppLookupResult(status=LookupStatus.UNAVAILABLE, app_id=app_id)


def _make_service():
    foundation = mock.MagicMock(spec=SteamImportFoundation)
    persistence = SteamGamePersistenceService()
    return SteamGameImportService(foundation, persistence), foundation


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class ImportHappyPathTests(TestCase):
    def test_found_candidate_is_persisted(self):
        service, foundation = _make_service()
        foundation.prepare_candidate.return_value = _found_lookup("620", "Portal 2")

        result = service.import_app("620")

        self.assertEqual(result.status, SteamGameImportStatus.CREATED)
        self.assertEqual(result.app_id.value, "620")
        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.source_type, SourceType.STEAM)
        self.assertEqual(game.name, "Portal 2")

    def test_reimport_returns_unchanged(self):
        service, foundation = _make_service()
        foundation.prepare_candidate.return_value = _found_lookup("620", "Portal 2")

        first = service.import_app("620")
        foundation.prepare_candidate.return_value = _found_lookup("620", "Portal 2")
        second = service.import_app("620")

        self.assertEqual(first.status, SteamGameImportStatus.CREATED)
        self.assertEqual(second.status, SteamGameImportStatus.UNCHANGED)
        self.assertEqual(second.game_id, first.game_id)

    def test_prepare_receives_raw_app_id(self):
        service, foundation = _make_service()
        foundation.prepare_candidate.return_value = _found_lookup("620", "Portal 2")

        service.import_app("620")

        foundation.prepare_candidate.assert_called_once_with("620")


# ---------------------------------------------------------------------------
# Content-type classification
# ---------------------------------------------------------------------------


class ContentTypeClassificationTests(TestCase):
    """Imported products persist exactly the classified content type (SBGC-95)."""

    def test_candidate_content_type_is_persisted(self):
        # Raw Steam type strings are classified by the canonical mapping (the
        # same mapper the adapter applies) and that canonical value is what
        # reaches persistence unchanged.
        raw_types = (
            "game",
            "dlc",
            "demo",
            "software",
            "music",
            "soundtrack",
            "hardware",
            "mod",
        )
        for index, raw in enumerate(raw_types):
            with self.subTest(raw=raw):
                canonical = map_steam_product_type(raw)
                app_id = str(7000 + index)
                service, foundation = _make_service()
                foundation.prepare_candidate.return_value = _found_lookup(
                    app_id,
                    f"Product {raw}",
                    content_type=canonical,
                )

                result = service.import_app(app_id)

                self.assertEqual(result.status, SteamGameImportStatus.CREATED)
                game = Game.objects.get(pk=result.game_id)
                self.assertEqual(game.content_type, canonical)


# ---------------------------------------------------------------------------
# Unavailable behavior
# ---------------------------------------------------------------------------


class UnavailableTests(TestCase):
    def test_unavailable_returns_unavailable_result(self):
        service, foundation = _make_service()
        foundation.prepare_candidate.return_value = _unavailable_lookup("999")

        result = service.import_app("999")

        self.assertEqual(result.status, SteamGameImportStatus.UNAVAILABLE)
        self.assertIsNone(result.game_id)
        self.assertEqual(result.app_id.value, "999")
        self.assertEqual(Game.objects.count(), 0)

    def test_unavailable_does_not_touch_existing_game(self):
        existing = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="999",
            name="Old Name",
            slug="old-name",
        )
        service, foundation = _make_service()
        foundation.prepare_candidate.return_value = _unavailable_lookup("999")

        result = service.import_app("999")

        self.assertEqual(result.status, SteamGameImportStatus.UNAVAILABLE)
        existing.refresh_from_db()
        self.assertEqual(existing.name, "Old Name")
        steam_rows = Game.objects.filter(
            source_type=SourceType.STEAM, external_id="999"
        )
        self.assertEqual(steam_rows.count(), 1)


# ---------------------------------------------------------------------------
# Error propagation — no writes
# ---------------------------------------------------------------------------


class ErrorPropagationTests(TestCase):
    def _assert_propagates_without_writes(self, exc: Exception):
        service, foundation = _make_service()
        foundation.prepare_candidate.side_effect = exc

        with self.assertRaises(type(exc)):
            service.import_app("730")

        self.assertEqual(Game.objects.count(), 0)

    def test_malformed_payload_propagates(self):
        self._assert_propagates_without_writes(SteamMalformedPayloadError("bad"))

    def test_timeout_propagates(self):
        self._assert_propagates_without_writes(SteamTimeoutError("timeout"))

    def test_connection_error_propagates(self):
        self._assert_propagates_without_writes(SteamConnectionError("refused"))

    def test_rate_limit_propagates(self):
        self._assert_propagates_without_writes(SteamRateLimitedError("slow down"))

    def test_upstream_error_propagates(self):
        self._assert_propagates_without_writes(SteamUpstreamError("502"))

    def test_preparation_failure_does_not_modify_existing(self):
        existing = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="730",
            name="Existing",
            slug="existing",
        )
        service, foundation = _make_service()
        foundation.prepare_candidate.side_effect = SteamTimeoutError("timeout")

        with self.assertRaises(SteamTimeoutError):
            service.import_app("730")

        existing.refresh_from_db()
        self.assertEqual(existing.name, "Existing")


# ---------------------------------------------------------------------------
# Transaction boundary
# ---------------------------------------------------------------------------


class TransactionBoundaryTests(TransactionTestCase):
    """Network preparation must never run inside a database transaction."""

    def test_prepare_runs_before_and_outside_atomic(self):
        order: list[tuple[str, bool]] = []

        def fake_prepare(app_id: str):
            order.append(("prepare", connection.in_atomic_block))
            return _found_lookup("620", "Portal 2")

        service = SteamGameImportService(
            foundation=mock.MagicMock(spec=SteamImportFoundation),
            persistence=SteamGamePersistenceService(),
        )
        with mock.patch.object(
            service._foundation, "prepare_candidate", side_effect=fake_prepare
        ):
            result = service.import_app("620")

        self.assertEqual(result.status, SteamGameImportStatus.CREATED)
        self.assertEqual(order, [("prepare", False)])
        steam_rows = Game.objects.filter(
            source_type=SourceType.STEAM, external_id="620"
        )
        self.assertEqual(steam_rows.count(), 1)

    def test_guarded_prepare_proves_no_transaction_wraps_network(self):
        def guarded_prepare(app_id: str):
            self.assertFalse(
                connection.in_atomic_block,
                "prepare_candidate ran inside a database transaction",
            )
            return _found_lookup("440", "Team Fortress 2")

        service = SteamGameImportService(
            foundation=mock.MagicMock(spec=SteamImportFoundation),
            persistence=SteamGamePersistenceService(),
        )
        with mock.patch.object(
            service._foundation, "prepare_candidate", side_effect=guarded_prepare
        ):
            result = service.import_app("440")

        self.assertEqual(result.status, SteamGameImportStatus.CREATED)
        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.name, "Team Fortress 2")


# ---------------------------------------------------------------------------
# Result app_id fidelity
# ---------------------------------------------------------------------------


class ResultFidelityTests(TestCase):
    def test_result_app_id_is_steam_app_id_instance(self):
        service, foundation = _make_service()
        foundation.prepare_candidate.return_value = _found_lookup("620", "Portal 2")

        result = service.import_app("620")

        self.assertIsInstance(result.app_id, SteamAppId)
        self.assertEqual(result.app_id.value, "620")
        self.assertIsInstance(result, SteamGameImportResult)
