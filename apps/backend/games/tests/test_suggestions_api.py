"""
Game suggestion endpoint tests — SBGC-240.

Covers the authentication gate, request validation (name/remarks lengths and
every rejected storefront-URL scheme), the email dispatch contract, the
per-user and per-IP throttles, and the mail-failure 503.  The endpoint is
stateless: nothing is written to the database.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

URL = "/api/v1/suggestions/"

VALID_URL = "https://store.steampowered.com/app/613830"

EXPECTED_BODY = (
    "Game Suggestion Received\n"
    "\n"
    "Submitted By: suggester (suggester@example.com)\n"
    "Name: Chrono Trigger\n"
    f"Storefront URL: {VALID_URL}\n"
    "Remarks: A classic.\n"
)


def _payload(**overrides) -> dict:
    payload = {
        "name": "Chrono Trigger",
        "storefront_url": VALID_URL,
        "remarks": "A classic.",
    }
    payload.update(overrides)
    return payload


class SuggestionApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="suggester",
            email="suggester@example.com",
            password="pw-strong-123",
        )

    def _post(self, payload: dict, *, client: Client | None = None, login: bool = True):
        client = client or self.client
        if login:
            client.force_login(self.user)
        return client.post(
            URL,
            data=json.dumps(payload),
            content_type="application/json",
            REMOTE_ADDR="127.0.0.1",
        )

    # -- authentication ------------------------------------------------------

    def test_anonymous_caller_is_rejected(self):
        response = self._post(_payload(), client=Client(), login=False)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTHENTICATION_ERROR")

    # -- validation ----------------------------------------------------------

    def test_blank_name_is_rejected(self):
        response = self._post(_payload(name="   "))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_empty_name_is_rejected(self):
        response = self._post(_payload(name=""))
        self.assertEqual(response.status_code, 422)

    def test_name_over_50_chars_is_rejected(self):
        response = self._post(_payload(name="x" * 51))
        self.assertEqual(response.status_code, 422)

    def test_remarks_over_250_chars_is_rejected(self):
        response = self._post(_payload(remarks="x" * 251))
        self.assertEqual(response.status_code, 422)

    def test_storefront_url_over_250_chars_is_rejected(self):
        response = self._post(_payload(storefront_url="https://" + "a" * 243))
        self.assertEqual(response.status_code, 422)

    def test_rejected_storefront_url_schemes(self):
        for url in (
            "http://example.com",
            "javascript:alert(1)",
            "data:text/html,hi",
            "ftp://example.com",
            "//evil.test",
        ):
            with self.subTest(url=url):
                response = self._post(_payload(storefront_url=url))
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_empty_storefront_url_is_allowed(self):
        with patch("games.services.suggestions.send_mail"):
            response = self._post(_payload(storefront_url=""))
        self.assertEqual(response.status_code, 200)

    # -- happy path & email contract ----------------------------------------

    def test_valid_submission_emails_the_operator(self):
        with patch("games.services.suggestions.send_mail") as send:
            response = self._post(_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"success": True, "message": "Suggestion submitted successfully."},
        )

        send.assert_called_once()
        kwargs = send.call_args.kwargs
        self.assertEqual(kwargs["from_email"], settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(
            kwargs["recipient_list"], [settings.SUGGESTION_RECIPIENT_EMAIL]
        )
        self.assertEqual(kwargs["subject"], "Game Suggestion Received: Chrono Trigger")
        self.assertEqual(kwargs["message"], EXPECTED_BODY)

    def test_empty_optional_fields_render_as_none(self):
        with patch("games.services.suggestions.send_mail") as send:
            response = self._post(_payload(storefront_url="", remarks=""))

        self.assertEqual(response.status_code, 200)
        message = send.call_args.kwargs["message"]
        self.assertIn("Storefront URL: None\n", message)
        self.assertIn("Remarks: None\n", message)

    # -- throttling ----------------------------------------------------------

    def test_second_submission_by_same_user_is_429(self):
        with patch("games.services.suggestions.send_mail"):
            first = self._post(_payload())
            second = self._post(_payload())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["error"]["code"], "RATE_LIMITED")
        self.assertIn("Retry-After", second)
        self.assertIn(
            "before submitting another suggestion",
            second.json()["error"]["message"],
        )

    def test_malformed_url_does_not_consume_the_suggestion_slot(self):
        bad = self._post(_payload(storefront_url="http://example.com"))
        self.assertEqual(bad.status_code, 422)

        with patch("games.services.suggestions.send_mail"):
            good = self._post(_payload())
        self.assertEqual(good.status_code, 200)

    def test_ip_limit_applies_across_users(self):
        with patch("games.services.suggestions.send_mail"):
            for index in range(3):
                user = User.objects.create_user(
                    username=f"other-{index}", password="pw-strong-123"
                )
                self.client.force_login(user)
                self.assertEqual(self._post(_payload(), login=False).status_code, 200)

            other = User.objects.create_user(
                username="fourth", password="pw-strong-123"
            )
            self.client.force_login(other)
            response = self._post(_payload(), login=False)

        self.assertEqual(response.status_code, 429)
        self.assertIn(
            "Too many suggestions from this IP",
            response.json()["error"]["message"],
        )

    # -- mail failure --------------------------------------------------------

    def test_mail_failure_returns_503(self):
        with patch(
            "games.services.suggestions.send_mail",
            side_effect=RuntimeError("smtp down"),
        ):
            response = self._post(_payload())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "SERVICE_UNAVAILABLE")
