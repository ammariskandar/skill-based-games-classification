"""
Production email settings tests — SBGC-239.

Covers the automatic Resend SMTP wiring, the explicit-relay fallback, the
email-credential fail-fast, and the absence of production SMTP defaults in the
test and development settings.

Production settings are imported in an isolated subprocess (the established
pattern in this suite) so the fail-fast validators run for real.
"""

from __future__ import annotations

import json

from django.conf import settings
from django.test import SimpleTestCase

from config.testing import minimal_subprocess_env, prod_test_env, run_manage

_SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
_MARKER = "EMAILJSON:"

_PRINT_SETTINGS = (
    "import json; "
    "from django.conf import settings; "
    f"print('{_MARKER}' + json.dumps({{"
    "'host': settings.EMAIL_HOST, "
    "'port': settings.EMAIL_PORT, "
    "'user': settings.EMAIL_HOST_USER, "
    "'tls': settings.EMAIL_USE_TLS, "
    "'ssl': settings.EMAIL_USE_SSL, "
    "'password': settings.EMAIL_HOST_PASSWORD, "
    "'backend': settings.EMAIL_BACKEND, "
    "'default_from': settings.DEFAULT_FROM_EMAIL, "
    "'server': settings.SERVER_EMAIL, "
    "}))"
)


def _load_production_email(**overrides: str) -> dict:
    """Return production email settings under a dummy production environment."""
    env = prod_test_env(**overrides)
    proc = run_manage(
        "shell",
        "--settings=config.settings.production",
        "-c",
        _PRINT_SETTINGS,
        env=env,
    )
    if proc.returncode != 0:
        raise AssertionError(f"production settings failed to load: {proc.stderr}")

    for line in proc.stdout.splitlines():
        if line.startswith(_MARKER):
            return json.loads(line[len(_MARKER) :])
    raise AssertionError(f"no settings payload in stdout: {proc.stdout!r}")


class ResendAutoWiringTests(SimpleTestCase):
    def test_resend_api_key_configures_the_smtp_relay(self):
        payload = _load_production_email(RESEND_API_KEY="re_test_123")

        self.assertEqual(payload["backend"], _SMTP_BACKEND)
        self.assertEqual(payload["host"], "smtp.resend.com")
        # 2587 rather than 587: Render free web services block outbound 25/465/587.
        self.assertEqual(payload["port"], 2587)
        self.assertEqual(payload["user"], "resend")
        self.assertIs(payload["tls"], True)
        self.assertIs(payload["ssl"], False)
        self.assertEqual(payload["password"], "re_test_123")

    def test_implicit_tls_port_selects_ssl(self):
        payload = _load_production_email(
            RESEND_API_KEY="re_test_123", RESEND_SMTP_PORT="2465"
        )

        self.assertEqual(payload["port"], 2465)
        self.assertIs(payload["ssl"], True)
        self.assertIs(payload["tls"], False)

    def test_starttls_port_selects_tls(self):
        payload = _load_production_email(
            RESEND_API_KEY="re_test_123", RESEND_SMTP_PORT="587"
        )

        self.assertEqual(payload["port"], 587)
        self.assertIs(payload["tls"], True)
        self.assertIs(payload["ssl"], False)

    def test_unsupported_resend_port_is_rejected(self):
        env = prod_test_env(RESEND_API_KEY="re_test_123", RESEND_SMTP_PORT="1234")
        proc = run_manage("check", "--settings=config.settings.production", env=env)

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("RESEND_SMTP_PORT", proc.stderr)

    def test_resend_branch_applies_gamedna_sender_defaults(self):
        payload = _load_production_email(RESEND_API_KEY="re_test_123")

        self.assertEqual(payload["default_from"], "noreply@gamedna.my")
        self.assertEqual(payload["server"], "alerts@gamedna.my")

    def test_explicit_sender_overrides_are_respected(self):
        payload = _load_production_email(
            RESEND_API_KEY="re_test_123",
            DEFAULT_FROM_EMAIL="hello@example.com",
            SERVER_EMAIL="ops@example.com",
        )

        self.assertEqual(payload["default_from"], "hello@example.com")
        self.assertEqual(payload["server"], "ops@example.com")


class ExplicitRelayFallbackTests(SimpleTestCase):
    def test_explicit_smtp_relay_is_used_when_resend_is_absent(self):
        payload = _load_production_email(
            RESEND_API_KEY="",
            EMAIL_HOST="smtp.example.com",
            EMAIL_PORT="2525",
            EMAIL_HOST_USER="mailer",
            EMAIL_HOST_PASSWORD="relay-secret",
            EMAIL_USE_TLS="true",
        )

        self.assertEqual(payload["host"], "smtp.example.com")
        self.assertEqual(payload["port"], 2525)
        self.assertEqual(payload["user"], "mailer")
        self.assertEqual(payload["password"], "relay-secret")
        self.assertIs(payload["tls"], True)

    def test_invalid_email_port_is_rejected(self):
        env = prod_test_env(
            RESEND_API_KEY="",
            EMAIL_HOST_PASSWORD="relay-secret",
            EMAIL_PORT="not-a-port",
        )
        proc = run_manage("check", "--settings=config.settings.production", env=env)

        self.assertNotEqual(proc.returncode, 0)

    def test_out_of_range_email_port_is_rejected(self):
        env = prod_test_env(
            RESEND_API_KEY="",
            EMAIL_HOST_PASSWORD="relay-secret",
            EMAIL_PORT="70000",
        )
        proc = run_manage("check", "--settings=config.settings.production", env=env)

        self.assertNotEqual(proc.returncode, 0)


class EmailCredentialFailFastTests(SimpleTestCase):
    def test_missing_credential_blocks_production_boot(self):
        env = prod_test_env(RESEND_API_KEY="")
        proc = run_manage("check", "--settings=config.settings.production", env=env)

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("RESEND_API_KEY or EMAIL_HOST_PASSWORD", proc.stderr)

    def test_explicit_host_password_satisfies_the_guard_without_resend(self):
        env = prod_test_env(
            RESEND_API_KEY="",
            EMAIL_HOST="smtp.example.com",
            EMAIL_HOST_PASSWORD="relay-secret",
        )
        proc = run_manage("check", "--settings=config.settings.production", env=env)

        self.assertEqual(proc.returncode, 0, f"stderr: {proc.stderr}")

    def test_blank_resend_key_is_treated_as_absent(self):
        env = prod_test_env(RESEND_API_KEY="   ")
        proc = run_manage("check", "--settings=config.settings.production", env=env)

        self.assertNotEqual(proc.returncode, 0)


class OtherEnvironmentsUnpollutedTests(SimpleTestCase):
    def test_test_settings_do_not_use_the_resend_relay(self):
        self.assertNotEqual(settings.EMAIL_HOST, "smtp.resend.com")
        self.assertNotEqual(settings.DEFAULT_FROM_EMAIL, "noreply@gamedna.my")

    def test_development_settings_keep_local_mail(self):
        env = minimal_subprocess_env(DJANGO_SKIP_DOTENV="1")
        proc = run_manage(
            "shell",
            "--settings=config.settings.development",
            "-c",
            _PRINT_SETTINGS,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, f"stderr: {proc.stderr}")

        payload_line = next(
            line for line in proc.stdout.splitlines() if line.startswith(_MARKER)
        )
        payload = json.loads(payload_line[len(_MARKER) :])

        self.assertNotEqual(payload["host"], "smtp.resend.com")
        self.assertEqual(payload["host"], "127.0.0.1")
        self.assertNotEqual(payload["password"], "re_test_dummy_key")
