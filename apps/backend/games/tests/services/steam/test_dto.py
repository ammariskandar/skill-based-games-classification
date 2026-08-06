"""
Steam DTO and value-type tests — SBGC-53.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

from django.test import SimpleTestCase

from games.services.steam.dto import (
    LookupStatus,
    SteamAppDetails,
    SteamAppId,
    SteamAppLookupResult,
    SteamGameImportCandidate,
)


class SteamAppIdTests(SimpleTestCase):
    def test_valid_digit_string(self):
        sid = SteamAppId("730")
        self.assertEqual(sid.value, "730")
        self.assertEqual(str(sid), "730")

    def test_single_digit(self):
        sid = SteamAppId("1")
        self.assertEqual(sid.value, "1")

    def test_large_app_id(self):
        sid = SteamAppId("12345678901234567890")
        self.assertEqual(sid.value, "12345678901234567890")

    # -- rejection ----------------------------------------------------------

    def test_blank_rejected(self):
        with self.assertRaises(ValueError):
            SteamAppId("")

    def test_whitespace_rejected(self):
        with self.assertRaises(ValueError):
            SteamAppId("   ")

    def test_leading_whitespace_rejected(self):
        with self.assertRaises(ValueError):
            SteamAppId(" 730")

    def test_trailing_whitespace_rejected(self):
        with self.assertRaises(ValueError):
            SteamAppId("730 ")

    def test_nondigit_rejected(self):
        with self.assertRaises(ValueError):
            SteamAppId("abc123")

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            SteamAppId("-1")

    def test_float_rejected(self):
        with self.assertRaises(ValueError):
            SteamAppId("1.0")

    def test_exponent_rejected(self):
        with self.assertRaises(ValueError):
            SteamAppId("1e5")

    def test_bool_rejected(self):
        with self.assertRaises(TypeError):
            SteamAppId(True)  # type: ignore[arg-type]

    def test_none_rejected(self):
        with self.assertRaises(TypeError):
            SteamAppId(None)  # type: ignore[arg-type]

    def test_int_rejected(self):
        with self.assertRaises(TypeError):
            SteamAppId(730)  # type: ignore[arg-type]

    def test_excessive_length_rejected(self):
        with self.assertRaises(ValueError):
            SteamAppId("1" * 33)

    def test_zero_rejected(self):
        with self.assertRaises(ValueError):
            SteamAppId("0")

    # -- repr ----------------------------------------------------------------

    def test_repr_does_not_leak_secrets(self):
        sid = SteamAppId("730")
        r = repr(sid)
        self.assertIn("SteamAppId", r)
        self.assertIn("730", r)


class DtoImmutabilityTests(SimpleTestCase):
    def test_steam_app_details_is_frozen(self):
        d = SteamAppDetails(app_id="730", name="CS:GO", content_type="game")
        with self.assertRaises(FrozenInstanceError):
            d.name = "other"  # type: ignore[misc]

    def test_steam_game_import_candidate_is_frozen(self):
        c = SteamGameImportCandidate(
            app_id="730", name="CS:GO", content_type="game"
        )
        with self.assertRaises(FrozenInstanceError):
            c.name = "other"  # type: ignore[misc]

    def test_steam_app_lookup_result_is_frozen(self):
        r = SteamAppLookupResult(
            status=LookupStatus.FOUND, app_id="730", candidate=None
        )
        with self.assertRaises(FrozenInstanceError):
            r.status = LookupStatus.UNAVAILABLE  # type: ignore[misc]
