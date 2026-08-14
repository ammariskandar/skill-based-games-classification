"""
Steam import endpoint tests — SBGC-57.

Exercises ``POST /api/v1/games/steam/import`` through the full routing
stack with the project-owned import service mocked at its composition
factory.  Covers status mapping, schema validation, domain App-ID
rejection, representative technical-error mapping, service delegation,
and OpenAPI exposure.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from games.models import Game, SourceType
from games.services.imports.steam import (
    SteamGameImportResult,
    SteamGameImportStatus,
)
from games.services.steam.adapters import SteamAdapterError
from games.services.steam.dto import SteamAppId
from games.services.steam.errors import SteamTimeoutError


class SteamImportEndpointTests(TestCase):
    url = "/api/v1/games/steam/import"

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username="import_staff",
            password="testpass",
            is_staff=True,
        )
        cls.game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
            content_type="game",
            listing_status="draft",
        )

    def _client(self) -> Client:
        client = Client()
        client.force_login(self.staff_user)
        return client

    def _post(
        self, body: dict | list | int | bool | None, client: Client | None = None
    ):
        client = client or self._client()
        data = body if body is None or isinstance(body, str) else json.dumps(body)
        return client.post(
            self.url,
            data=data,
            content_type="application/json",
        )

    def _result(self, status, game_id=None) -> SteamGameImportResult:
        return SteamGameImportResult(
            status=status,
            app_id=SteamAppId("620"),
            game_id=game_id,
        )

    # -- status mapping --------------------------------------------------------

    def test_created_returns_201_with_game_summary(self):
        result = self._result(SteamGameImportStatus.CREATED, self.game.pk)
        with patch("games.api._build_steam_import_service") as factory:
            factory.return_value.import_app.return_value = result
            r = self._post({"app_id": "620"})

        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["status"], "created")
        self.assertEqual(body["app_id"], "620")
        self.assertIsNotNone(body["game"])
        self.assertEqual(body["game"]["id"], self.game.pk)
        self.assertEqual(body["game"]["source_type"], "steam")
        self.assertEqual(body["game"]["external_id"], "620")
        self.assertEqual(body["game"]["name"], "Portal 2")
        self.assertEqual(body["game"]["content_type"], "game")
        self.assertEqual(body["game"]["listing_status"], "draft")
        self.assertIsNone(body["game"]["last_steam_refresh_at"])

    def test_updated_returns_200_with_game_summary(self):
        result = self._result(SteamGameImportStatus.UPDATED, self.game.pk)
        with patch("games.api._build_steam_import_service") as factory:
            factory.return_value.import_app.return_value = result
            r = self._post({"app_id": "620"})

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "updated")
        self.assertEqual(r.json()["game"]["id"], self.game.pk)

    def test_unchanged_returns_200_with_game_summary(self):
        result = self._result(SteamGameImportStatus.UNCHANGED, self.game.pk)
        with patch("games.api._build_steam_import_service") as factory:
            factory.return_value.import_app.return_value = result
            r = self._post({"app_id": "620"})

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "unchanged")
        self.assertEqual(r.json()["game"]["id"], self.game.pk)

    def test_unavailable_returns_200_with_null_game(self):
        result = SteamGameImportResult(
            status=SteamGameImportStatus.UNAVAILABLE,
            app_id=SteamAppId("620"),
            game_id=None,
        )
        with patch("games.api._build_steam_import_service") as factory:
            factory.return_value.import_app.return_value = result
            r = self._post({"app_id": "620"})

        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "unavailable")
        self.assertEqual(body["app_id"], "620")
        self.assertIsNone(body["game"])

    # -- schema validation -----------------------------------------------------

    def test_missing_app_id_is_422(self):
        with patch("games.api._build_steam_import_service") as factory:
            r = self._post({})
            self.assertEqual(r.status_code, 422)
            self.assertEqual(r.json()["error"]["code"], "VALIDATION_ERROR")
            factory.assert_not_called()

    def test_null_app_id_is_422(self):
        r = self._post({"app_id": None})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"]["code"], "VALIDATION_ERROR")

    def test_integer_app_id_is_422(self):
        r = self._post({"app_id": 620})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"]["code"], "VALIDATION_ERROR")

    def test_boolean_app_id_is_422(self):
        r = self._post({"app_id": True})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"]["code"], "VALIDATION_ERROR")

    def test_array_app_id_is_422(self):
        r = self._post({"app_id": ["620"]})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"]["code"], "VALIDATION_ERROR")

    def test_extra_fields_are_422(self):
        r = self._post({"app_id": "620", "unexpected": True})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"]["code"], "VALIDATION_ERROR")

    # -- domain App-ID rejection ----------------------------------------------

    def test_invalid_app_id_is_400(self):
        with patch("games.api._build_steam_import_service") as factory:
            factory.return_value.import_app.side_effect = SteamAdapterError(
                "bad app id",
                code="STEAM_INVALID_APP_ID",
            )
            r = self._post({"app_id": "not-a-number"})

        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["code"], "BAD_REQUEST")

    # -- technical-error mapping ----------------------------------------------

    def test_timeout_maps_to_503(self):
        with patch("games.api._build_steam_import_service") as factory:
            factory.return_value.import_app.side_effect = SteamTimeoutError(
                "read timed out"
            )
            r = self._post({"app_id": "620"})

        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"]["code"], "SERVICE_UNAVAILABLE")

    # -- service delegation ----------------------------------------------------

    def test_service_receives_request_app_id(self):
        service = MagicMock()
        service.import_app.return_value = self._result(
            SteamGameImportStatus.UNCHANGED, self.game.pk
        )
        with patch("games.api._build_steam_import_service") as factory:
            factory.return_value = service
            self._post({"app_id": "620"})

        service.import_app.assert_called_once_with("620")

    # -- OpenAPI --------------------------------------------------------------

    def test_openapi_declares_import_endpoint(self):
        client = Client()
        r = client.get("/api/v1/openapi.json")
        self.assertEqual(r.status_code, 200)
        schema = r.json()
        paths = schema["paths"]
        self.assertIn("/api/v1/games/steam/import", paths)
        operation = paths["/api/v1/games/steam/import"]["post"]
        self.assertEqual(operation["operationId"], "steam_import")
        schemas = schema["components"]["schemas"]
        self.assertIn("SteamImportRequest", schemas)
        self.assertIn("SteamImportResponse", schemas)
        self.assertIn("GameSummary", schemas)
        response_keys = set(operation["responses"].keys())
        self.assertIn("200", response_keys)
        self.assertIn("201", response_keys)
        self.assertIn("422", response_keys)
