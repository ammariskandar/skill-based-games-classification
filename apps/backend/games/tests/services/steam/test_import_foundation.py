"""
Steam import foundation tests — SBGC-53.

Tests against mocked adapter — no live calls, no database.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from games.services.steam.adapters import (
    SteamAdapterError,
    SteamMalformedPayloadError,
    SteamMissingRequiredFieldError,
)
from games.services.steam.dto import (
    LookupStatus,
    SteamAppDetails,
)
from games.services.steam.errors import SteamTimeoutError
from games.services.steam.import_foundation import SteamImportFoundation


class PrepareCandidateTests(SimpleTestCase):
    def setUp(self):
        self.adapter = MagicMock()
        self.foundation = SteamImportFoundation(self.adapter)

    # -- FOUND ----------------------------------------------------------------

    def test_found_returns_candidate(self):
        self.adapter.fetch.return_value = SteamAppDetails(
            app_id="730", name="CS:GO", content_type="game"
        )
        result = self.foundation.prepare_candidate("730")
        self.assertEqual(result.status, LookupStatus.FOUND)
        self.assertEqual(result.app_id, "730")
        self.assertIsNotNone(result.candidate)
        self.assertEqual(result.candidate.name, "CS:GO")
        self.assertEqual(result.candidate.content_type, "game")

    def test_found_candidate_mirrors_details(self):
        self.adapter.fetch.return_value = SteamAppDetails(
            app_id="440",
            name="Team Fortress 2",
            content_type="game",
            short_description="FPS",
            header_image_url="https://cdn.example.com/img.jpg",
            website_url=None,
            is_free=True,
            developers=("Valve",),
            publishers=("Valve",),
        )
        result = self.foundation.prepare_candidate("440")
        self.assertEqual(result.status, LookupStatus.FOUND)
        c = result.candidate
        self.assertIsNotNone(c)
        self.assertEqual(c.app_id, "440")
        self.assertEqual(c.name, "Team Fortress 2")
        self.assertTrue(c.is_free)

    def test_unknown_content_type_is_found(self):
        """Valid response with unrecognised type → FOUND with UNKNOWN content type."""
        self.adapter.fetch.return_value = SteamAppDetails(
            app_id="9999", name="Unknown Thing", content_type="unknown"
        )
        result = self.foundation.prepare_candidate("9999")
        self.assertEqual(result.status, LookupStatus.FOUND)
        self.assertIsNotNone(result.candidate)
        self.assertEqual(result.candidate.content_type, "unknown")

    # -- UNAVAILABLE ---------------------------------------------------------

    def test_unavailable(self):
        exc = SteamAdapterError(
            "Steam app 999 is unavailable (success=false).",
            code="STEAM_APP_UNAVAILABLE",
        )
        self.adapter.fetch.side_effect = exc
        result = self.foundation.prepare_candidate("999")
        self.assertEqual(result.status, LookupStatus.UNAVAILABLE)
        self.assertEqual(result.app_id, "999")
        self.assertIsNone(result.candidate)

    # -- Malformed payload propagation ----------------------------------------

    def test_malformed_payload_propagates(self):
        """MalformedPayloadError is NOT caught — it propagates to caller."""
        self.adapter.fetch.side_effect = SteamMalformedPayloadError("bad structure")
        with self.assertRaises(SteamMalformedPayloadError):
            self.foundation.prepare_candidate("123")

    def test_missing_required_field_propagates(self):
        self.adapter.fetch.side_effect = SteamMissingRequiredFieldError("missing name")
        with self.assertRaises(SteamMissingRequiredFieldError):
            self.foundation.prepare_candidate("456")

    def test_generic_adapter_error_propagates(self):
        """Non-UNAVAILABLE adapter errors propagate unchanged."""
        self.adapter.fetch.side_effect = SteamAdapterError("generic", code="OTHER")
        with self.assertRaises(SteamAdapterError):
            self.foundation.prepare_candidate("789")

    # -- Transport propagation -----------------------------------------------

    def test_transport_error_propagates(self):
        self.adapter.fetch.side_effect = SteamTimeoutError("timeout")
        with self.assertRaises(SteamTimeoutError):
            self.foundation.prepare_candidate("730")

    # -- Invalid App ID -------------------------------------------------------

    def test_invalid_app_id_raises(self):
        with self.assertRaises(SteamAdapterError) as cm:
            self.foundation.prepare_candidate("")
        self.assertEqual(cm.exception.code, "STEAM_INVALID_APP_ID")

    def test_nondigit_app_id_raises(self):
        with self.assertRaises(SteamAdapterError):
            self.foundation.prepare_candidate("abc")

    # -- No database ----------------------------------------------------------

    def test_no_database(self):
        """SimpleTestCase has no database access."""
        self.adapter.fetch.return_value = SteamAppDetails(
            app_id="730", name="Test", content_type="game"
        )
        self.foundation.prepare_candidate("730")

    # -- No network -----------------------------------------------------------

    def test_no_live_network(self):
        self.adapter.fetch.return_value = SteamAppDetails(
            app_id="730", name="Test", content_type="game"
        )
        self.foundation.prepare_candidate("730")


class DtoInvariantTests(SimpleTestCase):
    """Prove SteamAppLookupResult enforces candidate invariants."""

    def test_found_without_candidate_rejected(self):
        with self.assertRaises(ValueError):
            from games.services.steam.dto import SteamAppLookupResult

            SteamAppLookupResult(status=LookupStatus.FOUND, app_id="730")

    def test_unavailable_with_candidate_rejected(self):
        with self.assertRaises(ValueError):
            from games.services.steam.dto import (
                SteamAppLookupResult,
                SteamGameImportCandidate,
            )

            SteamAppLookupResult(
                status=LookupStatus.UNAVAILABLE,
                app_id="730",
                candidate=SteamGameImportCandidate(
                    app_id="730", name="X", content_type="game"
                ),
            )
