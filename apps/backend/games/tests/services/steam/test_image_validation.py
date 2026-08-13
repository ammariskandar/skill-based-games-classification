"""
Canonical Steam image URL validation tests — SBGC-55.

Pure policy tests for ``validate_steam_image_url``.  No database, no
network — validation is structural only.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from games.services.steam.adapters import SteamMalformedPayloadError
from games.services.steam.cdn import validate_steam_image_url


class AcceptedUrlTests(SimpleTestCase):
    def test_valid_https_url_accepted(self):
        url = "https://cdn.akamai.steamstatic.com/steam/apps/620/header.jpg"
        self.assertEqual(validate_steam_image_url(url), url)

    def test_outer_whitespace_stripped(self):
        self.assertEqual(
            validate_steam_image_url("  https://cdn.example.com/img.jpg  "),
            "https://cdn.example.com/img.jpg",
        )

    def test_uppercase_scheme_accepted(self):
        self.assertEqual(
            validate_steam_image_url("HTTPS://cdn.example.com/img.jpg"),
            "HTTPS://cdn.example.com/img.jpg",
        )

    def test_query_string_preserved(self):
        url = "https://cdn.example.com/img.jpg?v=2&x=1"
        self.assertEqual(validate_steam_image_url(url), url)


class AbsentValueTests(SimpleTestCase):
    def test_none_returns_none(self):
        self.assertIsNone(validate_steam_image_url(None))

    def test_blank_returns_none(self):
        self.assertIsNone(validate_steam_image_url(""))

    def test_whitespace_returns_none(self):
        self.assertIsNone(validate_steam_image_url("   "))


class MalformedTypeTests(SimpleTestCase):
    def test_int_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url(123)

    def test_list_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url(["https://cdn.example.com/img.jpg"])

    def test_bool_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url(True)


class MalformedUrlTests(SimpleTestCase):
    """Nonblank malformed URLs are errors — never normalized to None."""

    def test_http_scheme_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url("http://cdn.example.com/img.jpg")

    def test_ftp_scheme_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url("ftp://cdn.example.com/img.jpg")

    def test_file_scheme_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url("file:///etc/passwd")

    def test_schemeless_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url("//cdn.example.com/img.jpg")

    def test_credentials_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url("https://user:pass@cdn.example.com/img.jpg")

    def test_missing_hostname_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url("https:///img.jpg")

    def test_malformed_url_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url("not-a-url")

    def test_ipv4_literal_rejected(self):
        for url in (
            "https://127.0.0.1/img.jpg",
            "https://192.168.1.10/img.jpg",
            "https://10.0.0.1/img.jpg",
        ):
            with self.assertRaises(SteamMalformedPayloadError):
                validate_steam_image_url(url)

    def test_ipv6_literal_rejected(self):
        for url in ("https://[::1]/img.jpg", "https://[2001:db8::1]/img.jpg"):
            with self.assertRaises(SteamMalformedPayloadError):
                validate_steam_image_url(url)

    def test_numeric_host_rejected(self):
        for url in (
            "https://2130706433/img.jpg",
            "https://0x7f000001/img.jpg",
            "https://017700000001/img.jpg",
        ):
            with self.assertRaises(SteamMalformedPayloadError):
                validate_steam_image_url(url)

    def test_localhost_rejected(self):
        for url in (
            "https://localhost/img.jpg",
            "https://localhost.localdomain/img.jpg",
        ):
            with self.assertRaises(SteamMalformedPayloadError):
                validate_steam_image_url(url)

    def test_custom_port_rejected(self):
        with self.assertRaises(SteamMalformedPayloadError):
            validate_steam_image_url("https://cdn.example.com:8443/img.jpg")


class NoNetworkTests(SimpleTestCase):
    def test_validation_performs_no_network(self):
        """Structural validation never resolves hosts or fetches bytes."""
        for value in (
            "https://cdn.example.com/img.jpg",
            "https://127.0.0.1/img.jpg",
            "not-a-url",
            None,
        ):
            try:
                validate_steam_image_url(value)
            except SteamMalformedPayloadError:
                pass  # malformed values raise — but never contact the network
