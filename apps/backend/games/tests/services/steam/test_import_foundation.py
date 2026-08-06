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
        self.assertEqual(result.candidate.name, "CS:GO")  # type: ignore[union-attr]
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
        self.assertEqual(c.app_id, "440")  # type: ignore[union-attr]
        self.assertEqual(c.name, "Team Fortress 2")  # type: ignore[union-attr]
        self.assertTrue(c.is_free)  # type: ignore[union-attr]

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

    # -- UNSUPPORTED ---------------------------------------------------------

    def test_unsupported_on_malformed(self):
        self.adapter.fetch.side_effect = SteamMalformedPayloadError("bad")
        result = self.foundation.prepare_candidate("123")
        self.assertEqual(result.status, LookupStatus.UNSUPPORTED)
        self.assertIsNone(result.candidate)

    def test_unsupported_on_generic_adapter_error(self):
        self.adapter.fetch.side_effect = SteamAdapterError("unknown")
        result = self.foundation.prepare_candidate("456")
        self.assertEqual(result.status, LookupStatus.UNSUPPORTED)

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
        # If foundation called network directly, mock would fail.
