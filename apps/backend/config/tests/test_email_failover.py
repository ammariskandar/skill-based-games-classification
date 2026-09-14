"""
Email failover backend tests — SBGC-239.

Covers ZeptoMail HTTPS payload mapping and error handling, the Resend→ZeptoMail
failover ordering, and the production settings matrix that wires them up.
No test performs real network I/O: ``requests.post`` is mocked.
"""

from __future__ import annotations

import json
from unittest import mock

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend
from django.test import SimpleTestCase, override_settings

from config.email_backends import (
    EmailDeliveryError,
    FailoverEmailBackend,
    ZeptoMailApiEmailBackend,
)
from config.testing import prod_test_env, run_manage

# ---------------------------------------------------------------------------
# Stub backends used by the failover tests (imported by dotted path)
# ---------------------------------------------------------------------------

PRIMARY_CALLS: list[int] = []
SECONDARY_CALLS: list[int] = []
PRIMARY_FAILS = False
SECONDARY_FAILS = False


def _reset_stubs() -> None:
    global PRIMARY_FAILS, SECONDARY_FAILS
    PRIMARY_CALLS.clear()
    SECONDARY_CALLS.clear()
    PRIMARY_FAILS = False
    SECONDARY_FAILS = False


class PrimaryStub(BaseEmailBackend):
    def send_messages(self, email_messages) -> int:
        PRIMARY_CALLS.append(len(email_messages))
        if PRIMARY_FAILS:
            raise EmailDeliveryError("primary down")
        return len(email_messages)


class SecondaryStub(BaseEmailBackend):
    def send_messages(self, email_messages) -> int:
        SECONDARY_CALLS.append(len(email_messages))
        if SECONDARY_FAILS:
            raise EmailDeliveryError("secondary down")
        return len(email_messages)


PRIMARY_PATH = "config.tests.test_email_failover.PrimaryStub"
SECONDARY_PATH = "config.tests.test_email_failover.SecondaryStub"


def _message() -> EmailMessage:
    return EmailMessage(
        subject="Verify your email",
        body="Click the link: https://gamedna.my/verify-email?token=abc",
        from_email="MyGameDNA <noreply@gamedna.my>",
        to=["player@example.com"],
    )


# ---------------------------------------------------------------------------
# ZeptoMail HTTPS backend
# ---------------------------------------------------------------------------


class ZeptoMailPayloadTests(SimpleTestCase):
    @override_settings(ZEPTOMAIL_SEND_TOKEN="tok_test_123")
    def test_payload_maps_the_message(self):
        backend = ZeptoMailApiEmailBackend()

        with mock.patch("config.email_backends.requests.post") as post:
            post.return_value = mock.Mock(status_code=200, text="{}")
            backend.send_messages([_message()])

        url = post.call_args.args[0]
        headers = post.call_args.kwargs["headers"]
        payload = post.call_args.kwargs["json"]

        self.assertEqual(url, "https://api.zeptomail.com/v1.1/email")
        self.assertEqual(headers["Authorization"], "Zoho-enczapikey tok_test_123")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(
            payload["from"], {"address": "noreply@gamedna.my", "name": "MyGameDNA"}
        )
        self.assertEqual(
            payload["to"],
            [{"email_address": {"address": "player@example.com", "name": ""}}],
        )
        self.assertEqual(payload["subject"], "Verify your email")
        self.assertIn("https://gamedna.my/verify-email?token=abc", payload["textbody"])

    @override_settings(ZEPTOMAIL_SEND_TOKEN="tok_test_123")
    def test_html_alternative_becomes_htmlbody(self):
        message = EmailMultiAlternatives(
            subject="Verify your email",
            body="Click the link: https://gamedna.my/verify-email?token=abc",
            from_email="MyGameDNA <noreply@gamedna.my>",
            to=["player@example.com"],
        )
        message.attach_alternative("<p>Click the link</p>", "text/html")
        backend = ZeptoMailApiEmailBackend()

        with mock.patch("config.email_backends.requests.post") as post:
            post.return_value = mock.Mock(status_code=200, text="{}")
            backend.send_messages([message])

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["htmlbody"], "<p>Click the link</p>")
        self.assertIn("token=abc", payload["textbody"])

    @override_settings(ZEPTOMAIL_SEND_TOKEN="tok_test_123")
    def test_rejection_raises_with_the_provider_reason(self):
        backend = ZeptoMailApiEmailBackend()

        with mock.patch("config.email_backends.requests.post") as post:
            post.return_value = mock.Mock(
                status_code=403, text='{"message":"domain is not verified"}'
            )
            with self.assertRaises(EmailDeliveryError) as ctx:
                backend.send_messages([_message()])

        self.assertIn("403", str(ctx.exception))
        self.assertIn("domain is not verified", str(ctx.exception))

    @override_settings(ZEPTOMAIL_SEND_TOKEN="tok_test_123")
    def test_fail_silently_swallows_the_rejection(self):
        backend = ZeptoMailApiEmailBackend(fail_silently=True)

        with mock.patch("config.email_backends.requests.post") as post:
            post.return_value = mock.Mock(status_code=500, text="boom")
            self.assertEqual(backend.send_messages([_message()]), 0)

    @override_settings(ZEPTOMAIL_SEND_TOKEN="")
    def test_missing_token_fails_loudly(self):
        backend = ZeptoMailApiEmailBackend()

        with self.assertRaises(Exception) as ctx:
            backend.send_messages([_message()])
        self.assertIn("ZEPTOMAIL_SEND_TOKEN", str(ctx.exception))

    def test_no_messages_sends_nothing(self):
        backend = ZeptoMailApiEmailBackend()

        with mock.patch("config.email_backends.requests.post") as post:
            self.assertEqual(backend.send_messages([]), 0)
        post.assert_not_called()


# ---------------------------------------------------------------------------
# Failover ordering
# ---------------------------------------------------------------------------


@override_settings(
    EMAIL_FAILOVER_PRIMARY_BACKEND=PRIMARY_PATH,
    EMAIL_FAILOVER_SECONDARY_BACKEND=SECONDARY_PATH,
)
class FailoverBackendTests(SimpleTestCase):
    def setUp(self):
        _reset_stubs()

    def test_primary_success_never_touches_the_secondary(self):
        backend = FailoverEmailBackend()

        self.assertEqual(backend.send_messages([_message()]), 1)
        self.assertEqual(PRIMARY_CALLS, [1])
        self.assertEqual(SECONDARY_CALLS, [])

    def test_primary_failure_falls_back_to_the_secondary(self):
        global PRIMARY_FAILS
        PRIMARY_FAILS = True
        backend = FailoverEmailBackend()

        self.assertEqual(backend.send_messages([_message()]), 1)
        self.assertEqual(PRIMARY_CALLS, [1])
        self.assertEqual(SECONDARY_CALLS, [1])

    def test_both_failing_raises_by_default(self):
        global PRIMARY_FAILS, SECONDARY_FAILS
        PRIMARY_FAILS = True
        SECONDARY_FAILS = True
        backend = FailoverEmailBackend()

        with self.assertRaises(EmailDeliveryError):
            backend.send_messages([_message()])
        self.assertEqual(PRIMARY_CALLS, [1])
        self.assertEqual(SECONDARY_CALLS, [1])

    def test_both_failing_is_swallowed_when_fail_silently(self):
        global PRIMARY_FAILS, SECONDARY_FAILS
        PRIMARY_FAILS = True
        SECONDARY_FAILS = True
        backend = FailoverEmailBackend(fail_silently=True)

        self.assertEqual(backend.send_messages([_message()]), 0)

    def test_primary_failure_is_observable_even_when_fail_silently(self):
        """fail_silently must not stop the fallback from being attempted."""
        global PRIMARY_FAILS
        PRIMARY_FAILS = True
        backend = FailoverEmailBackend(fail_silently=True)

        self.assertEqual(backend.send_messages([_message()]), 1)
        self.assertEqual(SECONDARY_CALLS, [1])

    def test_no_messages_short_circuits(self):
        backend = FailoverEmailBackend()

        self.assertEqual(backend.send_messages([]), 0)
        self.assertEqual(PRIMARY_CALLS, [])


# ---------------------------------------------------------------------------
# Production wiring matrix
# ---------------------------------------------------------------------------

_SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
_ZEPTOMAIL_BACKEND = "config.email_backends.ZeptoMailApiEmailBackend"
_FAILOVER_BACKEND = "config.email_backends.FailoverEmailBackend"

_PRINT = (
    "import json; from django.conf import settings; "
    "print('WIRING:' + json.dumps({"
    "'email_backend': settings.EMAIL_BACKEND, "
    "'primary': getattr(settings, 'EMAIL_FAILOVER_PRIMARY_BACKEND', None), "
    "'secondary': getattr(settings, 'EMAIL_FAILOVER_SECONDARY_BACKEND', None), "
    "'smtp_port': settings.EMAIL_PORT, "
    "}))"
)


def _wiring(**overrides: str) -> dict:
    proc = run_manage(
        "shell",
        "--settings=config.settings.production",
        "-c",
        _PRINT,
        env=prod_test_env(**overrides),
    )
    if proc.returncode != 0:
        raise AssertionError(f"production settings failed: {proc.stderr}")
    line = next(
        (line for line in proc.stdout.splitlines() if line.startswith("WIRING:")),
        None,
    )
    if line is None:
        raise AssertionError(f"no wiring payload: {proc.stdout!r}")
    return json.loads(line[len("WIRING:") :])


class EmailWiringMatrixTests(SimpleTestCase):
    def test_resend_and_zeptomail_selects_the_failover_backend(self):
        wiring = _wiring(RESEND_API_KEY="re_test", ZEPTOMAIL_SEND_TOKEN="tok_test")

        self.assertEqual(wiring["email_backend"], _FAILOVER_BACKEND)
        self.assertEqual(wiring["primary"], _SMTP_BACKEND)
        self.assertEqual(wiring["secondary"], _ZEPTOMAIL_BACKEND)

    def test_resend_only_keeps_plain_smtp(self):
        wiring = _wiring(RESEND_API_KEY="re_test", ZEPTOMAIL_SEND_TOKEN="")

        self.assertEqual(wiring["email_backend"], _SMTP_BACKEND)
        self.assertIsNone(wiring["primary"])
        self.assertEqual(wiring["smtp_port"], 2587)

    def test_zeptomail_only_uses_the_zeptomail_backend(self):
        wiring = _wiring(RESEND_API_KEY="", ZEPTOMAIL_SEND_TOKEN="tok_test")

        self.assertEqual(wiring["email_backend"], _ZEPTOMAIL_BACKEND)
        self.assertIsNone(wiring["primary"])

    def test_zeptomail_alone_satisfies_the_credential_guard(self):
        env = prod_test_env(RESEND_API_KEY="", ZEPTOMAIL_SEND_TOKEN="tok_test")
        proc = run_manage("check", "--settings=config.settings.production", env=env)

        self.assertEqual(proc.returncode, 0, f"stderr: {proc.stderr}")
