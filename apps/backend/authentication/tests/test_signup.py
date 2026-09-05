"""
Sign-up flow tests — SBGC-218.

End-to-end coverage of username availability, the pre-registration email
verification challenge, zero email enumeration, the 30-minute resend lockout,
honeypot rejection, and final registration (auto-login + single-use challenge
invalidation).  Email dispatch is mocked; reCAPTCHA uses the canonical test
token so no network is touched.
"""

from __future__ import annotations

import json
import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import TestCase

from authentication.tokens import (
    confirm_email_challenge,
    create_email_challenge,
    get_challenge,
)

CHECK_URL = "/api/v1/auth/check-username"
VERIFY_URL = "/api/v1/auth/verify-email-request"
STATUS_URL = "/api/v1/auth/verification-status"
CONFIRM_URL = "/api/v1/auth/confirm-email"
SIGNUP_URL = "/api/v1/auth/signup"

RECAPTCHA_TOKEN = "test-recaptcha-token"


def _post(client, url, payload, *, remote_addr="127.0.0.1"):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        REMOTE_ADDR=remote_addr,
    )


def _request_verification(email: str) -> tuple[str, str]:
    """Create a challenge and return (challenge_id, emailed_token)."""
    with patch("authentication.tokens.send_mail") as mail:
        challenge_id = create_email_challenge(email)
        call = mail.call_args
        assert call is not None
        message = str(call.kwargs["message"])
    match = re.search(r"token=([^\s]+)", message)
    assert match is not None
    return challenge_id, match.group(1)


class UsernameAvailabilityTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_username_available(self):
        response = self.client.get(f"{CHECK_URL}?username=freeuser")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"available": True, "username": "freeuser"})

    def test_username_taken_case_insensitive(self):
        User.objects.create_user(username="TakenUser", password="p")
        response = self.client.get(f"{CHECK_URL}?username=takenuser")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"available": False, "username": "takenuser"})

    def test_username_invalid_format_rejected(self):
        response = self.client.get(f"{CHECK_URL}?username=ab")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")


class VerifyEmailRequestTests(TestCase):
    def setUp(self):
        cache.clear()

    def _verify(self, email, **overrides):
        payload = {"email": email, "recaptcha_token": RECAPTCHA_TOKEN, **overrides}
        return _post(self.client, VERIFY_URL, payload)

    def test_creates_challenge_and_dispatches_email(self):
        with patch("authentication.tokens.send_mail") as mail:
            response = self._verify("new@example.com")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("challenge_id", body)
        self.assertEqual(body["message"], "Verification email sent.")
        self.assertEqual(mail.call_count, 1)

        data = get_challenge(body["challenge_id"])
        self.assertEqual(data, {"email": "new@example.com", "status": "PENDING"})

    def test_existing_email_returns_generic_success(self):
        User.objects.create_user(
            username="existing", email="existing@example.com", password="p"
        )

        with patch("authentication.tokens.send_mail") as mail:
            response = self._verify("existing@example.com")

        # Same generic 200 shape as a fresh email — no enumeration leak.
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("challenge_id", body)
        self.assertEqual(body["message"], "Verification email sent.")
        self.assertEqual(mail.call_count, 1)
        # The sent email states the account already exists (not a verify link).
        self.assertIn("already exists", mail.call_args.kwargs["message"])

    def test_honeypot_rejected_silently(self):
        with patch("authentication.tokens.send_mail") as mail:
            response = self._verify("new@example.com", company_website="spam")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(mail.called)

    def test_rate_limited_after_three_resends(self):
        for _ in range(3):
            response = self._verify("ratelimit@example.com")
            self.assertEqual(response.status_code, 200)

        with patch("authentication.tokens.send_mail"):
            response = self._verify("ratelimit@example.com")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "RATE_LIMITED")
        self.assertEqual(response["Retry-After"], "1800")


class ConfirmEmailTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_confirm_transitions_challenge_to_verified(self):
        challenge_id, token = _request_verification("confirm@example.com")

        response = _post(self.client, CONFIRM_URL, {"token": token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})

        self.assertEqual(
            get_challenge(challenge_id),
            {"email": "confirm@example.com", "status": "VERIFIED"},
        )

    def test_confirm_invalid_token_rejected(self):
        response = _post(self.client, CONFIRM_URL, {"token": "bogus"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "BAD_REQUEST")


class SignupTests(TestCase):
    def setUp(self):
        cache.clear()

    def _verified_challenge(self, email: str) -> str:
        challenge_id, token = _request_verification(email)
        self.assertTrue(confirm_email_challenge(token))
        return challenge_id

    def test_signup_creates_user_auto_login_and_invalidates_challenge(self):
        challenge_id = self._verified_challenge("signup@example.com")

        response = _post(
            self.client,
            SIGNUP_URL,
            {
                "username": "signupuser",
                "email": "signup@example.com",
                "password": "StrongPass1!",
                "challenge_id": challenge_id,
                "recaptcha_token": RECAPTCHA_TOKEN,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(), {"authenticated": True, "username": "signupuser"}
        )

        user = User.objects.get(username="signupuser")
        self.assertEqual(user.email, "signup@example.com")
        self.assertTrue(user.check_password("StrongPass1!"))

        # Single-use challenge is removed after registration.
        self.assertIsNone(get_challenge(challenge_id))
        # Auto-login established a session row.
        self.assertTrue(Session.objects.exists())

    def test_signup_without_verified_challenge_fails(self):
        response = _post(
            self.client,
            SIGNUP_URL,
            {
                "username": "tampered",
                "email": "tampered@example.com",
                "password": "StrongPass1!",
                "challenge_id": "does-not-exist",
                "recaptcha_token": RECAPTCHA_TOKEN,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "EMAIL_NOT_VERIFIED")
        self.assertFalse(User.objects.filter(username="tampered").exists())

    def test_signup_honeypot_rejected(self):
        challenge_id = self._verified_challenge("honey@example.com")
        response = _post(
            self.client,
            SIGNUP_URL,
            {
                "username": "honeybot",
                "email": "honey@example.com",
                "password": "StrongPass1!",
                "challenge_id": challenge_id,
                "recaptcha_token": RECAPTCHA_TOKEN,
                "company_website": "spam",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="honeybot").exists())

    def test_signup_duplicate_username_rejected(self):
        User.objects.create_user(username="dupuser", password="p")
        challenge_id = self._verified_challenge("dup@example.com")

        response = _post(
            self.client,
            SIGNUP_URL,
            {
                "username": "dupuser",
                "email": "dup@example.com",
                "password": "StrongPass1!",
                "challenge_id": challenge_id,
                "recaptcha_token": RECAPTCHA_TOKEN,
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "CONFLICT")
