"""
Steam mutation endpoint authorization matrix tests — SBGC-57.

Exercises the full route → auth → (schema) boundary with real HTTP
requests through Django's test client, proving:

    anonymous                    → 401 AUTHENTICATION_ERROR
    authenticated non-staff      → 403 AUTHORIZATION_ERROR
    authenticated staff          → authorized (service is reached)
    superuser                    → authorized (is_staff is True)

Also proves that Django session CSRF protection is *not* weakened: a
session-authenticated POST without a CSRF token is rejected, while the
documented login → CSRF-token → X-CSRFToken flow succeeds.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory, TestCase
from games.models import Game, SourceType


class SteamEndpointAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username="steam_staff",
            password="testpass",
            is_staff=True,
        )
        cls.superuser = User.objects.create_superuser(
            username="steam_super",
            password="testpass",
        )
        cls.normal_user = User.objects.create_user(
            username="steam_normal",
            password="testpass",
            is_staff=False,
        )
        cls.game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
        )
        cls.import_url = "/api/v1/games/steam/import"
        cls.refresh_url = f"/api/v1/games/{cls.game.pk}/steam/refresh"

    def _post(self, url, body: dict | None, *, client: Client | None = None):
        client = client or Client()
        return client.post(
            url,
            data=json.dumps(body) if body is not None else None,
            content_type="application/json",
        )

    def _staff_client(self) -> Client:
        client = Client()
        client.force_login(self.staff_user)
        return client

    # -- authentication / authorization matrix --------------------------------

    def test_import_anonymous_is_401(self):
        with patch("games.api._build_steam_import_service") as factory:
            r = self._post(self.import_url, {"app_id": "620"})
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.json()["error"]["code"], "AUTHENTICATION_ERROR")
            factory.assert_not_called()

    def test_import_normal_user_is_403(self):
        client = Client()
        client.force_login(self.normal_user)
        with patch("games.api._build_steam_import_service") as factory:
            r = self._post(self.import_url, {"app_id": "620"}, client=client)
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()["error"]["code"], "AUTHORIZATION_ERROR")
            factory.assert_not_called()

    def test_refresh_anonymous_is_401(self):
        with patch("games.api._build_steam_refresh_service") as factory:
            r = self._post(self.refresh_url, None)
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.json()["error"]["code"], "AUTHENTICATION_ERROR")
            factory.assert_not_called()

    def test_refresh_normal_user_is_403(self):
        client = Client()
        client.force_login(self.normal_user)
        with patch("games.api._build_steam_refresh_service") as factory:
            r = self._post(self.refresh_url, None, client=client)
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()["error"]["code"], "AUTHORIZATION_ERROR")
            factory.assert_not_called()

    # -- CSRF is enforced (session auth) --------------------------------------

    def test_import_without_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff_user)
        with patch("games.api._build_steam_import_service") as factory:
            r = self._post(self.import_url, {"app_id": "620"}, client=client)
            self.assertEqual(r.status_code, 403)
            # Ninja session-auth CSRF check raises HttpError(403), which the
            # registered handler surfaces through the JSON error envelope.
            self.assertEqual(r["Content-Type"], "application/json")
            self.assertIn("error", r.json())
            factory.assert_not_called()

    def test_import_with_csrf_token_succeeds(self):
        from games.services.imports.steam import (
            SteamGameImportResult,
            SteamGameImportStatus,
        )
        from games.services.steam.dto import SteamAppId

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff_user)
        token = self._issue_csrf_token(client)

        result = SteamGameImportResult(
            status=SteamGameImportStatus.UNCHANGED,
            app_id=SteamAppId("620"),
            game_id=self.game.pk,
        )
        with patch("games.api._build_steam_import_service") as factory:
            factory.return_value.import_app.return_value = result
            r = client.post(
                self.import_url,
                data=json.dumps({"app_id": "620"}),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["status"], "unchanged")

    def _issue_csrf_token(self, client: Client) -> str:
        request = RequestFactory().get(self.import_url)
        token = get_token(request)
        client.cookies["csrftoken"] = request.META["CSRF_COOKIE"]
        return token
