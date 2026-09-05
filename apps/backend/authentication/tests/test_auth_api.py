"""
Authentication API tests — SBGC-217.

End-to-end (routing-stack) coverage of login / status / logout: zero-PII
payloads, byte-identical 401s for user enumeration defense, dual-key rate
limiting, session establishment/flushing, and cookie lifecycle.
"""

from __future__ import annotations

import json

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import TestCase

LOGIN_URL = "/api/v1/auth/login"
STATUS_URL = "/api/v1/auth/status"
LOGOUT_URL = "/api/v1/auth/logout"


def _post(client, url, payload, *, remote_addr="127.0.0.1"):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        REMOTE_ADDR=remote_addr,
    )


class LoginEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="validuser", password="correct-password"
        )

    def test_login_success_sets_session_and_zero_pii(self):
        response = _post(
            self.client,
            LOGIN_URL,
            {"username": "validuser", "password": "correct-password"},
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        # Strict zero-PII contract — only these two keys may appear.
        self.assertEqual(body, {"authenticated": True, "username": "validuser"})
        self.assertNotIn("id", body)
        self.assertNotIn("email", body)
        self.assertNotIn("password", body)

        # The sessionid cookie is set, and a database session row exists.
        self.assertIn("sessionid", response.cookies)
        session_key = response.cookies["sessionid"].value
        self.assertTrue(Session.objects.filter(session_key=session_key).exists())

    def test_login_invalid_password_returns_authentication_error(self):
        response = _post(
            self.client,
            LOGIN_URL,
            {"username": "validuser", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": "Invalid username or password.",
                    "details": [],
                }
            },
        )

    def test_login_nonexistent_user_returns_identical_401(self):
        invalid_password = _post(
            self.client,
            LOGIN_URL,
            {"username": "validuser", "password": "wrong-password"},
        )
        nonexistent = _post(
            self.client,
            LOGIN_URL,
            {"username": "does-not-exist", "password": "any-password"},
        )
        self.assertEqual(nonexistent.status_code, 401)
        self.assertEqual(nonexistent.content, invalid_password.content)

    def test_login_rate_limiting_by_ip(self):
        # Five distinct usernames so only the IP bucket fills.
        for i in range(5):
            response = _post(
                self.client,
                LOGIN_URL,
                {"username": f"victim-{i}", "password": "wrong"},
            )
            self.assertEqual(response.status_code, 401)

        response = _post(
            self.client,
            LOGIN_URL,
            {"username": "validuser", "password": "correct-password"},
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "RATE_LIMITED")
        self.assertEqual(response["Retry-After"], "60")

    def test_login_rate_limiting_by_username(self):
        # Same target username across five distinct source IPs.
        for i in range(5):
            response = _post(
                self.client,
                LOGIN_URL,
                {"username": "validuser", "password": "wrong"},
                remote_addr=f"10.0.0.{i + 1}",
            )
            self.assertEqual(response.status_code, 401)

        response = _post(
            self.client,
            LOGIN_URL,
            {"username": "validuser", "password": "correct-password"},
            remote_addr="10.0.0.99",
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "RATE_LIMITED")


class StatusEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="validuser", password="p")

    def test_status_unauthenticated(self):
        response = self.client.get(STATUS_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authenticated": False, "username": None})

    def test_status_authenticated(self):
        self.client.force_login(self.user)  # type: ignore[attr-defined]
        response = self.client.get(STATUS_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"authenticated": True, "username": "validuser"}
        )


class LogoutEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="validuser", password="p")

    def test_logout_flushes_session(self):
        self.client.force_login(self.user)  # type: ignore[attr-defined]
        self.assertTrue(Session.objects.exists())

        response = self.client.post(LOGOUT_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authenticated": False, "username": None})

        # The session row is removed from the database…
        self.assertFalse(Session.objects.exists())

        # …and a subsequent status request reports unauthenticated.
        status = self.client.get(STATUS_URL)
        self.assertEqual(status.json(), {"authenticated": False, "username": None})
