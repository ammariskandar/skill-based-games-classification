"""
Account recovery & one-chance password-reset tests — SBGC-219.

Covers the zero-enumeration forgot-username / forgot-password entrypoints, the
single-claim signed reset token → ephemeral session-nonce exchange, burn-on-
abandon, full password confirmation (hash change, session revocation, security
notification), expired/burned nonce rejection, and the recovery rate-limit
lockout.  Email dispatch is mocked; reCAPTCHA uses the canonical test token so
no network is touched.
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
    burn_reset_session_nonce,
    claim_password_reset_token,
    create_password_reset_token,
    get_reset_session,
)

FORGOT_USERNAME_URL = "/api/v1/auth/forgot-username"
FORGOT_PASSWORD_URL = "/api/v1/auth/forgot-password"
VERIFY_TOKEN_URL = "/api/v1/auth/verify-reset-token"
BURN_TOKEN_URL = "/api/v1/auth/burn-reset-token"
RESET_CONFIRM_URL = "/api/v1/auth/reset-password-confirm"

RECAPTCHA_TOKEN = "test-recaptcha-token"

GENERIC_MESSAGE = (
    "If the provided details match an account, instructions have been sent."
)


def _post(client, url, payload, *, remote_addr="127.0.0.1"):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        REMOTE_ADDR=remote_addr,
    )


def _forgot_username_payload(email: str, **overrides):
    return {"email": email, "recaptcha_token": RECAPTCHA_TOKEN, **overrides}


def _forgot_password_payload(username: str, email: str, **overrides):
    return {
        "username": username,
        "email": email,
        "recaptcha_token": RECAPTCHA_TOKEN,
        **overrides,
    }


def _token_from_message(message: str) -> str:
    """Extract the signed reset token from an emailed reset link."""
    match = re.search(r"reset-password\?token=([^\s]+)", message)
    assert match is not None, f"No reset link found in: {message!r}"
    return match.group(1)


class ForgotUsernameTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_existing_account_dispatches_username_email(self):
        User.objects.create_user(
            username="james.bond", email="bond@example.com", password="p"
        )

        with patch("authentication.tokens.send_mail") as mail:
            response = _post(
                self.client,
                FORGOT_USERNAME_URL,
                _forgot_username_payload("bond@example.com"),
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body, {"success": True, "message": GENERIC_MESSAGE})
        self.assertEqual(mail.call_count, 1)
        call = mail.call_args
        assert call is not None
        self.assertEqual(call.kwargs["subject"], "Your MyGameDNA Username")
        self.assertIn("james.bond", call.kwargs["message"])
        self.assertEqual(call.kwargs["recipient_list"], ["bond@example.com"])

    def test_gmail_dot_variant_resolves_to_registered_account(self):
        # The stored address keeps its dots; a dotless query must still find it.
        User.objects.create_user(
            username="johnsmith", email="john.smith@gmail.com", password="p"
        )

        with patch("authentication.tokens.send_mail") as mail:
            response = _post(
                self.client,
                FORGOT_USERNAME_URL,
                _forgot_username_payload("johnsmith@gmail.com"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.call_count, 1)
        assert mail.call_args is not None
        self.assertIn("johnsmith", mail.call_args.kwargs["message"])

    def test_nonexistent_account_returns_identical_generic_response(self):
        # A registered account exists so the two envelopes can be compared.
        User.objects.create_user(
            username="bond", email="bond@example.com", password="p"
        )
        existing_payload = _forgot_username_payload("bond@example.com")
        missing_payload = _forgot_username_payload("ghost@example.com")

        with patch("authentication.tokens.send_mail"):
            existing_response = _post(
                self.client, FORGOT_USERNAME_URL, existing_payload
            )
        with patch("authentication.tokens.send_mail") as mail:
            missing_response = _post(self.client, FORGOT_USERNAME_URL, missing_payload)

        # Byte-identical envelopes — no address enumeration over the API.
        self.assertEqual(missing_response.status_code, 200)
        self.assertEqual(missing_response.content, existing_response.content)
        # …and a missing account dispatches nothing at all.
        self.assertEqual(mail.call_count, 0)

    def test_honeypot_rejected_silently(self):
        with patch("authentication.tokens.send_mail") as mail:
            response = _post(
                self.client,
                FORGOT_USERNAME_URL,
                _forgot_username_payload("bond@example.com", company_website="spam"),
            )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(mail.called)

    def test_rate_limiting_429_after_three_requests(self):
        for _ in range(3):
            response = _post(
                self.client,
                FORGOT_USERNAME_URL,
                _forgot_username_payload("spammer@example.com"),
            )
            self.assertEqual(response.status_code, 200)

        with patch("authentication.tokens.send_mail"):
            response = _post(
                self.client,
                FORGOT_USERNAME_URL,
                _forgot_username_payload("spammer@example.com"),
            )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "RATE_LIMITED")
        self.assertEqual(response["Retry-After"], "1800")


class ForgotPasswordTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="resetuser",
            email="reset@example.com",
            password="OldPass1!",
            is_active=True,
        )

    def test_matching_credentials_dispatch_reset_link(self):
        with patch("authentication.tokens.send_mail") as mail:
            response = _post(
                self.client,
                FORGOT_PASSWORD_URL,
                _forgot_password_payload("resetuser", "reset@example.com"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "message": GENERIC_MESSAGE})
        self.assertEqual(mail.call_count, 1)
        call = mail.call_args
        assert call is not None
        self.assertEqual(call.kwargs["subject"], "Reset your MyGameDNA password")
        message = call.kwargs["message"]
        # The signed one-chance token appears in the emailed link.
        self.assertRegex(message, r"reset-password\?token=.+")

    def test_case_insensitive_username_and_canonical_email_match(self):
        # Canonicalised comparison tolerates a dotted Gmail variant of the
        # stored address (dots are preserved in the stored column).
        self.user.email = "reset.user@gmail.com"
        self.user.save()

        with patch("authentication.tokens.send_mail") as mail:
            response = _post(
                self.client,
                FORGOT_PASSWORD_URL,
                _forgot_password_payload("RESETUSER", "resetuser@gmail.com"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.call_count, 1)

    def test_mismatched_credentials_dispatch_nothing(self):
        cases = [
            # Wrong email for a real username.
            _forgot_password_payload("resetuser", "other@example.com"),
            # Unknown username.
            _forgot_password_payload("ghostuser", "reset@example.com"),
            # Both wrong.
            _forgot_password_payload("ghostuser", "other@example.com"),
        ]

        for payload in cases:
            with patch("authentication.tokens.send_mail") as mail:
                response = _post(self.client, FORGOT_PASSWORD_URL, payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json(), {"success": True, "message": GENERIC_MESSAGE}
            )
            self.assertEqual(mail.call_count, 0)

    def test_honeypot_rejected_silently(self):
        with patch("authentication.tokens.send_mail") as mail:
            response = _post(
                self.client,
                FORGOT_PASSWORD_URL,
                _forgot_password_payload(
                    "resetuser", "reset@example.com", company_website="spam"
                ),
            )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(mail.called)

    def test_rate_limiting_429_after_three_requests(self):
        for _ in range(3):
            response = _post(
                self.client,
                FORGOT_PASSWORD_URL,
                _forgot_password_payload("resetuser", "reset@example.com"),
            )
            self.assertEqual(response.status_code, 200)

        with patch("authentication.tokens.send_mail"):
            response = _post(
                self.client,
                FORGOT_PASSWORD_URL,
                _forgot_password_payload("resetuser", "reset@example.com"),
            )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "RATE_LIMITED")


class ResetTokenLifecycleTests(TestCase):
    """Direct token/nonce machinery coverage (single claim + burn)."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="flowuser", password="p")

    def test_claim_then_burn(self):
        signed_token = create_password_reset_token(self.user)

        # First claim exchanges the token for a session nonce.
        nonce = claim_password_reset_token(signed_token)
        self.assertIsNotNone(nonce)
        self.assertIsNotNone(get_reset_session(nonce))  # type: ignore[arg-type]

        # The same signed token can never be claimed again.
        self.assertIsNone(claim_password_reset_token(signed_token))

        # Burning removes the nonce record entirely.
        burn_reset_session_nonce(nonce)  # type: ignore[arg-type]
        self.assertIsNone(get_reset_session(nonce))  # type: ignore[arg-type]

    def test_garbage_token_returns_none(self):
        self.assertIsNone(claim_password_reset_token("not-a-signed-token"))


class ResetPasswordConfirmTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="confirmuser",
            email="confirm@example.com",
            password="OldPass1!",
        )

    def _obtain_nonce(self, mail) -> str:
        """Run forgot-password + verify-reset-token; return the session nonce."""
        response = _post(
            self.client,
            FORGOT_PASSWORD_URL,
            _forgot_password_payload("confirmuser", "confirm@example.com"),
        )
        self.assertEqual(response.status_code, 200)
        call = mail.call_args
        assert call is not None
        token = _token_from_message(call.kwargs["message"])

        response = _post(self.client, VERIFY_TOKEN_URL, {"token": token})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["valid"])
        return body["session_nonce"]

    def test_confirm_updates_password_revokes_sessions_and_alerts(self):
        # Establish a live authenticated session that must be kicked out.
        self.client.force_login(self.user)  # type: ignore[attr-defined]
        self.assertTrue(Session.objects.exists())

        with patch("authentication.tokens.send_mail") as mail:
            nonce = self._obtain_nonce(mail)
            response = _post(
                self.client,
                RESET_CONFIRM_URL,
                {
                    "session_nonce": nonce,
                    "new_password": "BrandNewPass9!",
                    "recaptcha_token": RECAPTCHA_TOKEN,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})

        # Password hash updated; the old password no longer works.
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass9!"))
        self.assertFalse(self.user.check_password("OldPass1!"))

        # Every live session for this user was deleted from django_session.
        self.assertFalse(Session.objects.exists())

        # A security-alert email was dispatched (second send_mail call).
        self.assertEqual(mail.call_count, 2)
        security_call = mail.call_args
        assert security_call is not None
        self.assertEqual(
            security_call.kwargs["subject"],
            "Security Alert: Your MyGameDNA password has been changed",
        )
        self.assertIn("MAY BE COMPROMISED", security_call.kwargs["message"])

        # The nonce is single-use: the same confirm cannot be replayed.
        response = _post(
            self.client,
            RESET_CONFIRM_URL,
            {
                "session_nonce": nonce,
                "new_password": "AnotherPass1!",
                "recaptcha_token": RECAPTCHA_TOKEN,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "EXPIRED_RESET_TOKEN")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass9!"))

    def test_expired_or_unknown_nonce_rejected(self):
        with patch("authentication.tokens.send_mail"):
            response = _post(
                self.client,
                RESET_CONFIRM_URL,
                {
                    "session_nonce": "does-not-exist",
                    "new_password": "BrandNewPass9!",
                    "recaptcha_token": RECAPTCHA_TOKEN,
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "EXPIRED_RESET_TOKEN")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPass1!"))

    def test_honeypot_rejected(self):
        with patch("authentication.tokens.send_mail") as mail:
            nonce = self._obtain_nonce(mail)
            response = _post(
                self.client,
                RESET_CONFIRM_URL,
                {
                    "session_nonce": nonce,
                    "new_password": "BrandNewPass9!",
                    "recaptcha_token": RECAPTCHA_TOKEN,
                    "company_website": "spam",
                },
            )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPass1!"))


class BurnResetTokenEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="burnuser", password="p")

    def test_burn_endpoint_deletes_nonce(self):
        signed_token = create_password_reset_token(self.user)
        nonce = claim_password_reset_token(signed_token)
        self.assertIsNotNone(nonce)

        response = _post(self.client, BURN_TOKEN_URL, {"session_nonce": nonce})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})
        self.assertIsNone(get_reset_session(nonce))  # type: ignore[arg-type]
