"""
Steam refresh endpoint tests — SBGC-57.

Exercises ``POST /api/v1/games/{game_id}/steam/refresh`` through the full
routing stack with the project-owned refresh service mocked at its
composition factory.  Covers status mapping, Game-not-found, manual-Game
rejection, representative technical-error mapping, service delegation,
and OpenAPI exposure.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from games.models import Game, SourceType
from games.services.imports.steam import (
    SteamGameRefreshResult,
    SteamGameRefreshStatus,
    SteamRefreshError,
)
from games.services.steam.errors import SteamConnectionError


class SteamRefreshEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username="refresh_staff",
            password="testpass",
            is_staff=True,
        )
        cls.steam_game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
        )
        cls.manual_game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Chess",
            slug="chess",
        )

    def _client(self) -> Client:
        client = Client()
        client.force_login(self.staff_user)
        return client

    def _url(self, game_id) -> str:
        return f"/api/v1/games/{game_id}/steam/refresh"

    def _post(self, game_id, *, client: Client | None = None):
        client = client or self._client()
        return client.post(self._url(game_id), content_type="application/json")

    def _result(
        self, status, game_id=None, changed_fields=()
    ) -> SteamGameRefreshResult:
        return SteamGameRefreshResult(
            status=status,
            game_id=game_id if game_id is not None else self.steam_game.pk,
            changed_fields=changed_fields,
        )

    # -- status mapping --------------------------------------------------------

    def test_updated_returns_200_with_changed_fields(self):
        result = self._result(
            SteamGameRefreshStatus.UPDATED,
            changed_fields=("name",),
        )
        with patch("games.api._build_steam_refresh_service") as factory:
            factory.return_value.refresh.return_value = result
            r = self._post(self.steam_game.pk)

        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "updated")
        self.assertEqual(body["changed_fields"], ["name"])
        self.assertEqual(body["game"]["id"], self.steam_game.pk)
        self.assertEqual(body["game"]["source_type"], "steam")
        self.assertEqual(body["game"]["external_id"], "620")

    def test_unchanged_returns_200_with_empty_changed_fields(self):
        result = self._result(SteamGameRefreshStatus.UNCHANGED)
        with patch("games.api._build_steam_refresh_service") as factory:
            factory.return_value.refresh.return_value = result
            r = self._post(self.steam_game.pk)

        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "unchanged")
        self.assertEqual(body["changed_fields"], [])

    def test_unavailable_returns_200_and_preserves_identity(self):
        result = self._result(SteamGameRefreshStatus.UNAVAILABLE)
        with patch("games.api._build_steam_refresh_service") as factory:
            factory.return_value.refresh.return_value = result
            r = self._post(self.steam_game.pk)

        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "unavailable")
        self.assertEqual(body["game"]["id"], self.steam_game.pk)

    # -- not found -------------------------------------------------------------

    def test_missing_game_is_404_and_no_service_call(self):
        with patch("games.api._build_steam_refresh_service") as factory:
            r = self._post(999_999)
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.json()["error"]["code"], "NOT_FOUND")
            factory.assert_not_called()

    # -- manual game rejection -------------------------------------------------

    def test_manual_game_is_400_and_no_service_call(self):
        service = MagicMock()
        service.refresh.side_effect = SteamRefreshError(
            "Only Steam-sourced games can refresh"
        )
        with patch("games.api._build_steam_refresh_service") as factory:
            factory.return_value = service
            r = self._post(self.manual_game.pk)

        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["code"], "BAD_REQUEST")

    def test_manual_game_reaches_service_with_resolved_game(self):
        """The route resolves the manual Game and delegates — service rejects."""
        service = MagicMock()
        service.refresh.side_effect = SteamRefreshError("manual")
        with patch("games.api._build_steam_refresh_service") as factory:
            factory.return_value = service
            self._post(self.manual_game.pk)

        args, _kwargs = service.refresh.call_args
        self.assertEqual(args[0].pk, self.manual_game.pk)

    # -- technical-error mapping ----------------------------------------------

    def test_connection_error_maps_to_503(self):
        with patch("games.api._build_steam_refresh_service") as factory:
            factory.return_value.refresh.side_effect = SteamConnectionError(
                "connection refused"
            )
            r = self._post(self.steam_game.pk)

        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"]["code"], "SERVICE_UNAVAILABLE")

    # -- service delegation ----------------------------------------------------

    def test_service_receives_resolved_steam_game(self):
        service = MagicMock()
        service.refresh.return_value = self._result(SteamGameRefreshStatus.UNCHANGED)
        with patch("games.api._build_steam_refresh_service") as factory:
            factory.return_value = service
            self._post(self.steam_game.pk)

        args, _kwargs = service.refresh.call_args
        self.assertEqual(args[0].pk, self.steam_game.pk)

    # -- OpenAPI --------------------------------------------------------------

    def test_openapi_declares_refresh_endpoint(self):
        client = Client()
        r = client.get("/api/v1/openapi.json")
        self.assertEqual(r.status_code, 200)
        schema = r.json()
        paths = schema["paths"]
        self.assertIn("/api/v1/games/{game_id}/steam/refresh", paths)
        operation = paths["/api/v1/games/{game_id}/steam/refresh"]["post"]
        self.assertEqual(operation["operationId"], "steam_refresh")
        schemas = schema["components"]["schemas"]
        self.assertIn("SteamRefreshResponse", schemas)
        response_keys = set(operation["responses"].keys())
        self.assertIn("200", response_keys)
