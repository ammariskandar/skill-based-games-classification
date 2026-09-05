"""
Email canonicalisation & duplicate detection tests — SBGC-218.

Covers the Gmail/Googlemail dot-alias rule: dots in the local part are ignored
(and the two alias domains are equivalent) because Google routes them all to
the same mailbox, while every other domain keeps dots significant.  Exercises
the helper directly and the two registration endpoints that use it
(`verify-email-request` and `signup`).
"""

from __future__ import annotations

import json
import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from authentication.emails import email_is_registered, normalize_email
from authentication.tokens import (
    confirm_email_challenge,
    create_email_challenge,
)

VERIFY_URL = "/api/v1/auth/verify-email-request"
SIGNUP_URL = "/api/v1/auth/signup"

RECAPTCHA_TOKEN = "test-recaptcha-token"


def _post(client, url, payload):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        REMOTE_ADDR="127.0.0.1",
    )


def _verified_challenge_for(email: str) -> str:
    """Create + confirm a challenge for *email*; return its challenge_id."""
    with patch("authentication.tokens.send_mail") as mail:
        challenge_id = create_email_challenge(email)
        call = mail.call_args
        assert call is not None
        message = str(call.kwargs["message"])
    match = re.search(r"token=([^\s]+)", message)
    assert match is not None
    assert confirm_email_challenge(match.group(1))
    return challenge_id


class NormalizeEmailTests(TestCase):
    def test_gmail_dots_stripped_and_lowercased(self):
        self.assertEqual(normalize_email("John.Smith@gmail.com"), "johnsmith@gmail.com")

    def test_gmail_many_dots_stripped(self):
        self.assertEqual(
            normalize_email("j.o.h.n.s.m.i.t.h@gmail.com"),
            "johnsmith@gmail.com",
        )

    def test_googlemail_is_equivalent_to_gmail(self):
        self.assertEqual(
            normalize_email("john.smith@googlemail.com"),
            normalize_email("johnsmith@gmail.com"),
        )

    def test_other_domains_keep_dots(self):
        self.assertEqual(
            normalize_email("jane.doe@outlook.com"), "jane.doe@outlook.com"
        )
        self.assertNotEqual(
            normalize_email("jane.doe@outlook.com"),
            normalize_email("janedoe@outlook.com"),
        )

    def test_whitespace_trimmed(self):
        self.assertEqual(
            normalize_email("  john.smith@gmail.com "), "johnsmith@gmail.com"
        )


class EmailIsRegisteredTests(TestCase):
    def setUp(self):
        User.objects.create_user(
            username="owner", email="johnsmith@gmail.com", password="p"
        )

    def test_exact_match_detected(self):
        self.assertTrue(email_is_registered("johnsmith@gmail.com"))

    def test_gmail_dot_variant_detected(self):
        self.assertTrue(email_is_registered("john.smith@gmail.com"))

    def test_googlemail_alias_detected(self):
        self.assertTrue(email_is_registered("john.smith@googlemail.com"))

    def test_case_insensitive_detected(self):
        self.assertTrue(email_is_registered("JOHN.SMITH@Gmail.COM"))

    def test_unrelated_address_not_detected(self):
        self.assertFalse(email_is_registered("someone.else@gmail.com"))
        self.assertFalse(email_is_registered("johnsmith@outlook.com"))


class EmailIsRegisteredDottedStoredTests(TestCase):
    """Registration preserves dots in the stored address, so the dot-stripping
    scan (not the exact lookup) must catch canonical duplicates."""

    def setUp(self):
        # As signup stores it: whitespace trimmed + lower-cased, dots intact.
        User.objects.create_user(
            username="owner", email="john.smith@gmail.com", password="p"
        )

    def test_dotless_query_matches_dotted_stored_address(self):
        self.assertTrue(email_is_registered("johnsmith@gmail.com"))

    def test_heavy_dot_query_matches_dotted_stored_address(self):
        self.assertTrue(email_is_registered("j.o.h.n.s.m.i.t.h@googlemail.com"))

    def test_other_gmail_address_not_detected(self):
        self.assertFalse(email_is_registered("someone.else@gmail.com"))


class GmailDuplicateEndpointTests(TestCase):
    def setUp(self):
        User.objects.create_user(
            username="owner", email="johnsmith@gmail.com", password="p"
        )

    def test_verify_request_for_dot_variant_sends_account_exists_email(self):
        # A dot-variant reaches the same Gmail mailbox as the registered
        # address, so it must be treated as taken — without revealing that via
        # the API response shape (still a generic 200 challenge).
        with patch("authentication.tokens.send_mail") as mail:
            response = _post(
                self.client,
                VERIFY_URL,
                {
                    "email": "john.smith@gmail.com",
                    "recaptcha_token": RECAPTCHA_TOKEN,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("challenge_id", body)
        self.assertEqual(body["message"], "Verification email sent.")
        self.assertEqual(mail.call_count, 1)
        self.assertIn("already exists", mail.call_args.kwargs["message"])
        # No verification-link challenge was created for the duplicate.
        self.assertNotIn("verify-email?token=", mail.call_args.kwargs["message"])

    def test_signup_rejects_dot_variant_of_registered_gmail(self):
        # A VERIFIED challenge for the dot-variant exists, but signup must
        # still reject it: the address is the same Gmail mailbox as the
        # already-registered account.
        challenge_id = _verified_challenge_for("john.smith@gmail.com")

        response = _post(
            self.client,
            SIGNUP_URL,
            {
                "username": "newuser",
                "email": "john.smith@gmail.com",
                "password": "StrongPass1!",
                "challenge_id": challenge_id,
                "recaptcha_token": RECAPTCHA_TOKEN,
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "CONFLICT")
        self.assertFalse(
            User.objects.filter(username="newuser").exists(),
            "A duplicate Gmail mailbox must not create a second account.",
        )

    def test_non_gmail_dots_remain_significant_at_signup(self):
        # outlook.com treats dots as significant: registering a dotted variant
        # of a *different* address is a normal fresh signup.
        User.objects.create_user(
            username="someone", email="brand.new@outlook.com", password="p"
        )
        challenge_id = _verified_challenge_for("brandnew@outlook.com")

        response = _post(
            self.client,
            SIGNUP_URL,
            {
                "username": "brandnew",
                "email": "brandnew@outlook.com",
                "password": "StrongPass1!",
                "challenge_id": challenge_id,
                "recaptcha_token": RECAPTCHA_TOKEN,
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username="brandnew").exists())
