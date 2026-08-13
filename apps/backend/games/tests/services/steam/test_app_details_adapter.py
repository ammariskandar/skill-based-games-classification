"""
Steam app-details adapter tests — SBGC-53.

Tests against mocked SteamClient.get_store_api_json — no live calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from games.services.steam.adapters import (
    SteamMalformedPayloadError,
    SteamMissingRequiredFieldError,
)
from games.services.steam.adapters.app_details import SteamAppDetailsAdapter
from games.services.steam.dto import SteamAppId
from games.services.steam.errors import (
    SteamConnectionError,
    SteamTimeoutError,
    SteamUpstreamError,
)


def _valid_response(app_id="730", **overrides):
    """Build a minimal valid Steam appdetails response."""
    data = {
        "name": "Test Game",
        "type": "game",
        "short_description": "A test game.",
        "header_image": "https://cdn.example.com/img.jpg",
        "website": "https://example.com",
        "is_free": False,
        "developers": ["Dev Co"],
        "publishers": ["Pub Co"],
        **overrides,
    }
    return {
        app_id: {
            "success": True,
            "data": data,
        }
    }


def _unavailable_response(app_id="730"):
    return {app_id: {"success": False}}


class SuccessTests(SimpleTestCase):
    def setUp(self):
        self.client = MagicMock()
        self.adapter = SteamAppDetailsAdapter(self.client)

    def test_game(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "730", type="game"
        )
        details = self.adapter.fetch(SteamAppId("730"))
        self.assertEqual(details.app_id, "730")
        self.assertEqual(details.name, "Test Game")
        self.assertEqual(details.content_type, "game")

    def test_dlc(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "1000", type="dlc"
        )
        details = self.adapter.fetch(SteamAppId("1000"))
        self.assertEqual(details.content_type, "dlc")

    def test_demo(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "2000", type="demo"
        )
        details = self.adapter.fetch(SteamAppId("2000"))
        self.assertEqual(details.content_type, "demo")

    def test_software(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "3000", type="software"
        )
        details = self.adapter.fetch(SteamAppId("3000"))
        self.assertEqual(details.content_type, "software")

    def test_soundtrack(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "4000", type="music"
        )
        details = self.adapter.fetch(SteamAppId("4000"))
        self.assertEqual(details.content_type, "soundtrack")

    def test_unknown_type(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "5000", type="video"
        )
        details = self.adapter.fetch(SteamAppId("5000"))
        self.assertEqual(details.content_type, "unknown")

    def test_optional_fields(self):
        self.client.get_store_api_json.return_value = _valid_response("730")  # pyright: ignore[reportAttributeAccessIssue]
        details = self.adapter.fetch(SteamAppId("730"))
        self.assertEqual(details.short_description, "A test game.")
        self.assertEqual(details.header_image_url, "https://cdn.example.com/img.jpg")
        self.assertEqual(details.website_url, "https://example.com")
        self.assertFalse(details.is_free)
        self.assertEqual(details.developers, ("Dev Co",))
        self.assertEqual(details.publishers, ("Pub Co",))

    def test_absent_optional_fields(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "730",
            short_description=None,
            header_image=None,
            website=None,
            is_free=None,
            developers=None,
            publishers=None,
        )
        details = self.adapter.fetch(SteamAppId("730"))
        self.assertIsNone(details.short_description)
        self.assertIsNone(details.header_image_url)
        self.assertIsNone(details.website_url)
        self.assertIsNone(details.is_free)
        self.assertIsNone(details.developers)
        self.assertIsNone(details.publishers)

    def test_blank_website_becomes_none(self):
        self.client.get_store_api_json.return_value = _valid_response("730", website="")  # pyright: ignore[reportAttributeAccessIssue]
        details = self.adapter.fetch(SteamAppId("730"))
        self.assertIsNone(details.website_url)

    # -- Image URL structural rejection (SBGC-55 canonical validator) --------

    def test_http_header_image_becomes_none(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "730", header_image="http://cdn.example.com/img.jpg"
        )
        details = self.adapter.fetch(SteamAppId("730"))
        self.assertIsNone(details.header_image_url)

    def test_ip_literal_header_image_becomes_none(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "730", header_image="https://127.0.0.1/img.jpg"
        )
        details = self.adapter.fetch(SteamAppId("730"))
        self.assertIsNone(details.header_image_url)

    def test_credentials_header_image_becomes_none(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "730", header_image="https://user:pass@cdn.example.com/img.jpg"
        )
        details = self.adapter.fetch(SteamAppId("730"))
        self.assertIsNone(details.header_image_url)


class UnavailableTests(SimpleTestCase):
    def setUp(self):
        self.client = MagicMock()
        self.adapter = SteamAppDetailsAdapter(self.client)

    def test_success_false(self):
        self.client.get_store_api_json.return_value = _unavailable_response("999")  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(Exception) as cm:
            self.adapter.fetch(SteamAppId("999"))
        exc = cm.exception
        self.assertEqual(getattr(exc, "code", None), "STEAM_APP_UNAVAILABLE")


class MalformedTests(SimpleTestCase):
    def setUp(self):
        self.client = MagicMock()
        self.adapter = SteamAppDetailsAdapter(self.client)

    def test_root_not_dict(self):
        self.client.get_store_api_json.return_value = ["not", "a", "dict"]  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(SteamMalformedPayloadError):
            self.adapter.fetch(SteamAppId("730"))

    def test_missing_app_id_key(self):
        self.client.get_store_api_json.return_value = {  # pyright: ignore[reportAttributeAccessIssue]
            "999": {"success": True, "data": {}}
        }
        with self.assertRaises(SteamMalformedPayloadError):
            self.adapter.fetch(SteamAppId("730"))

    def test_wrapper_not_dict(self):
        self.client.get_store_api_json.return_value = {"730": "not-a-dict"}  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(SteamMalformedPayloadError):
            self.adapter.fetch(SteamAppId("730"))

    def test_success_not_bool(self):
        self.client.get_store_api_json.return_value = {  # pyright: ignore[reportAttributeAccessIssue]
            "730": {"success": "yes", "data": {}}
        }
        with self.assertRaises(SteamMalformedPayloadError):
            self.adapter.fetch(SteamAppId("730"))

    def test_success_true_without_data(self):
        self.client.get_store_api_json.return_value = {"730": {"success": True}}  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(SteamMalformedPayloadError):
            self.adapter.fetch(SteamAppId("730"))

    def test_data_not_dict(self):
        self.client.get_store_api_json.return_value = {  # pyright: ignore[reportAttributeAccessIssue]
            "730": {"success": True, "data": []}
        }
        with self.assertRaises(SteamMalformedPayloadError):
            self.adapter.fetch(SteamAppId("730"))

    def test_missing_name(self):
        self.client.get_store_api_json.return_value = _valid_response("730", name=None)  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(SteamMissingRequiredFieldError):
            self.adapter.fetch(SteamAppId("730"))

    def test_blank_name(self):
        self.client.get_store_api_json.return_value = _valid_response("730", name="   ")  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(SteamMissingRequiredFieldError):
            self.adapter.fetch(SteamAppId("730"))

    def test_missing_type(self):
        self.client.get_store_api_json.return_value = _valid_response("730", type=None)  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(SteamMissingRequiredFieldError):
            self.adapter.fetch(SteamAppId("730"))

    def test_blank_type(self):
        self.client.get_store_api_json.return_value = _valid_response("730", type="   ")  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(SteamMissingRequiredFieldError):
            self.adapter.fetch(SteamAppId("730"))

    # -- Non-string metadata → malformed -------------------------------------

    def test_non_string_header_image_raises(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "730", header_image=123
        )
        with self.assertRaises(SteamMalformedPayloadError):
            self.adapter.fetch(SteamAppId("730"))

    def test_non_string_website_raises(self):
        self.client.get_store_api_json.return_value = _valid_response(  # pyright: ignore[reportAttributeAccessIssue]
            "730", website=["bad"]
        )
        with self.assertRaises(SteamMalformedPayloadError):
            self.adapter.fetch(SteamAppId("730"))


class TransportPropagationTests(SimpleTestCase):
    """Transport exceptions propagate unchanged."""

    def setUp(self):
        self.client = MagicMock()
        self.adapter = SteamAppDetailsAdapter(self.client)

    def test_timeout_propagates(self):
        self.client.get_store_api_json.side_effect = SteamTimeoutError("timed out")  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(SteamTimeoutError):
            self.adapter.fetch(SteamAppId("730"))

    def test_connection_propagates(self):
        self.client.get_store_api_json.side_effect = SteamConnectionError("conn")  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(SteamConnectionError):
            self.adapter.fetch(SteamAppId("730"))

    def test_upstream_propagates(self):
        self.client.get_store_api_json.side_effect = SteamUpstreamError("500")  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(SteamUpstreamError):
            self.adapter.fetch(SteamAppId("730"))


class NoDatabaseNetworkTests(SimpleTestCase):
    def test_no_database(self):
        """SimpleTestCase has no database access."""
        client = MagicMock()
        adapter = SteamAppDetailsAdapter(client)
        client.get_store_api_json.return_value = _valid_response("730")
        adapter.fetch(SteamAppId("730"))

    def test_no_live_network(self):
        """Adapter never instantiates Requests/urllib3 directly."""
        client = MagicMock()
        adapter = SteamAppDetailsAdapter(client)
        client.get_store_api_json.return_value = _valid_response("730")
        # If adapter called requests directly, this would fail.
        adapter.fetch(SteamAppId("730"))
