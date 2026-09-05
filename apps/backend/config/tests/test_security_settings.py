"""
Security-settings & secret-hygiene tests — SBGC-104.

Validates the production fail-fast guards (DEBUG, secret key, allowed hosts,
reCAPTCHA/Steam credentials), production cookie security flags, strict
environment boolean parsing, database-URL masking, and Steam API-key
redaction in URLs and transport-failure logs.

Production settings are exercised in isolated subprocesses with dummy
credentials — never against a real environment or network.
"""

from __future__ import annotations

from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.env_typing import get_env_bool
from config.testing import prod_test_env, run_manage

# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def _check_prod(**overrides) -> tuple[int, str, str]:
    """Run ``manage.py check`` against production settings with *overrides*."""
    proc = run_manage(
        "check",
        "--settings=config.settings.production",
        env=prod_test_env(**overrides),
    )
    return proc.returncode, proc.stdout, proc.stderr


# ============================================================================
# Production fail-fast configuration
# ============================================================================


class ProductionDebugGuardTests(SimpleTestCase):
    def test_production_debug_must_be_false(self):
        rc, _stdout, stderr = _check_prod(DJANGO_DEBUG="true")
        self.assertNotEqual(rc, 0)
        self.assertIn("DJANGO_DEBUG", stderr)

    def test_production_debug_false_forms_accepted(self):
        for value in ("false", "0", "no", "off", ""):
            rc, _stdout, stderr = _check_prod(DJANGO_DEBUG=value)
            self.assertEqual(rc, 0, f"DJANGO_DEBUG={value!r} failed: {stderr}")


class ProductionSecretKeyGuardTests(SimpleTestCase):
    def test_production_missing_secret_key(self):
        rc, _stdout, stderr = _check_prod(DJANGO_SECRET_KEY="")
        self.assertNotEqual(rc, 0)
        self.assertIn("DJANGO_SECRET_KEY", stderr)

    def test_production_insecure_secret_key(self):
        rc, _stdout, stderr = _check_prod(
            DJANGO_SECRET_KEY="django-insecure-dev-key-do-not-use-in-production"
        )
        self.assertNotEqual(rc, 0)

    def test_production_short_secret_key(self):
        rc, _stdout, stderr = _check_prod(DJANGO_SECRET_KEY="too-short")
        self.assertNotEqual(rc, 0)


class ProductionAllowedHostsGuardTests(SimpleTestCase):
    def test_production_allowed_hosts_wildcard(self):
        rc, _stdout, stderr = _check_prod(DJANGO_ALLOWED_HOSTS="*")
        self.assertNotEqual(rc, 0)

    def test_production_allowed_hosts_empty(self):
        rc, _stdout, stderr = _check_prod(DJANGO_ALLOWED_HOSTS="")
        self.assertNotEqual(rc, 0)


class ProductionServiceCredentialGuardTests(SimpleTestCase):
    def test_production_missing_recaptcha_key(self):
        rc, _stdout, stderr = _check_prod(RECAPTCHA_SECRET_KEY="")
        self.assertNotEqual(rc, 0)
        self.assertIn("RECAPTCHA_SECRET_KEY", stderr)

    def test_production_missing_steam_key(self):
        rc, _stdout, stderr = _check_prod(STEAM_WEB_API_KEY="")
        self.assertNotEqual(rc, 0)
        self.assertIn("STEAM_WEB_API_KEY", stderr)

    def test_valid_dummy_config_imports(self):
        rc, _stdout, stderr = _check_prod()
        self.assertEqual(rc, 0, f"stderr: {stderr}")


class ProductionCookieSecurityFlagTests(SimpleTestCase):
    def _production_settings_snapshot(self) -> str:
        proc = run_manage(
            "shell",
            "--settings=config.settings.production",
            "-c",
            "from django.conf import settings; "
            "print('SESSION_COOKIE_SECURE=' + str(settings.SESSION_COOKIE_SECURE)); "
            "print('CSRF_COOKIE_SECURE=' + str(settings.CSRF_COOKIE_SECURE)); "
            "print('SESSION_COOKIE_HTTPONLY=' + "
            "str(settings.SESSION_COOKIE_HTTPONLY)); "
            "print('SESSION_COOKIE_SAMESITE=' + str(settings.SESSION_COOKIE_SAMESITE))",
            env=prod_test_env(),
        )
        self.assertEqual(proc.returncode, 0, f"stderr: {proc.stderr}")
        return proc.stdout

    def test_production_cookie_security_flags(self):
        output = self._production_settings_snapshot()
        self.assertIn("SESSION_COOKIE_SECURE=True", output)
        self.assertIn("CSRF_COOKIE_SECURE=True", output)
        self.assertIn("SESSION_COOKIE_HTTPONLY=True", output)
        self.assertIn("SESSION_COOKIE_SAMESITE=Lax", output)


# ============================================================================
# Strict environment parsing
# ============================================================================


class StrictEnvBoolTests(SimpleTestCase):
    def test_truthy_spellings(self):
        for value in ("true", "1", "yes", "on", "TRUE", " True "):
            with self.subTest(value=value):
                with patch.dict("os.environ", {"TEST_BOOL": value}):
                    self.assertTrue(get_env_bool("TEST_BOOL", default=False))

    def test_falsy_spellings(self):
        for value in ("false", "0", "no", "off", ""):
            with self.subTest(value=value):
                with patch.dict("os.environ", {"TEST_BOOL": value}):
                    self.assertFalse(get_env_bool("TEST_BOOL", default=True))

    def test_unset_uses_default(self):
        import os

        previous = os.environ.pop("TEST_BOOL", None)
        try:
            self.assertTrue(get_env_bool("TEST_BOOL", default=True))
            self.assertFalse(get_env_bool("TEST_BOOL", default=False))
        finally:
            if previous is not None:
                os.environ["TEST_BOOL"] = previous

    def test_invalid_value_raises(self):
        with patch.dict("os.environ", {"TEST_BOOL": "banana"}):
            with self.assertRaises(ImproperlyConfigured):
                get_env_bool("TEST_BOOL")


# ============================================================================
# Database URL masking
# ============================================================================


class MaskDatabaseUrlTests(SimpleTestCase):
    def test_password_redacted(self):
        from config.database import mask_database_url

        masked = mask_database_url(
            "postgresql://user:hunter2@example.neon.tech/mygamedna"
        )
        self.assertIn("[REDACTED]", masked)
        self.assertNotIn("hunter2", masked)
        self.assertIn("user:", masked)
        self.assertIn("example.neon.tech/mygamedna", masked)

    def test_blank_and_malformed_returned_unchanged(self):
        from config.database import mask_database_url

        self.assertEqual(mask_database_url(""), "")
        self.assertEqual(mask_database_url(None), "")
        self.assertEqual(mask_database_url("not-a-url"), "not-a-url")

    def test_url_without_password_unchanged(self):
        from config.database import mask_database_url

        self.assertEqual(
            mask_database_url("postgresql://example.neon.tech/mygamedna"),
            "postgresql://example.neon.tech/mygamedna",
        )

    def test_query_string_kept_but_password_still_redacted(self):
        from config.database import mask_database_url

        masked = mask_database_url(
            "postgresql://user:hunter2@example.neon.tech/db?sslmode=require"
        )
        self.assertNotIn("hunter2", masked)
        self.assertIn("?sslmode=require", masked)


# ============================================================================
# Steam API key scrubbing
# ============================================================================


class SteamUrlSanitizationTests(SimpleTestCase):
    def test_query_key_redacted(self):
        from games.services.steam.client import sanitize_steam_url

        self.assertEqual(
            sanitize_steam_url("https://api.steampowered.com/x?key=SECRET&appid=730"),
            "https://api.steampowered.com/x?key=[REDACTED]&appid=730",
        )

    def test_ampersand_key_redacted(self):
        from games.services.steam.client import sanitize_steam_url

        self.assertEqual(
            sanitize_steam_url("https://api.steampowered.com/x?appid=730&key=SECRET"),
            "https://api.steampowered.com/x?appid=730&key=[REDACTED]",
        )

    def test_no_key_unchanged(self):
        from games.services.steam.client import sanitize_steam_url

        url = "https://api.steampowered.com/x?appid=730"
        self.assertEqual(sanitize_steam_url(url), url)

    def test_case_insensitive_key_redacted(self):
        from games.services.steam.client import sanitize_steam_url

        self.assertEqual(
            sanitize_steam_url("https://api.steampowered.com/x?appid=1&KEY=secret"),
            "https://api.steampowered.com/x?appid=1&KEY=[REDACTED]",
        )


class SteamClientLogScrubbingTests(SimpleTestCase):
    def test_transport_failure_logs_redacted_url_only(self):
        import requests
        from games.services.steam.client import SteamClient
        from games.services.steam.config import SteamClientConfig
        from games.services.steam.errors import SteamConnectionError

        class _StubSession:
            def get(self, *_args: object, **_kwargs: object) -> object:
                request = requests.PreparedRequest()
                request.url = "https://api.steampowered.com/x?key=SECRET-KEY&appid=730"
                raise requests.exceptions.ConnectionError("boom", request=request)

        config = SteamClientConfig(
            api_key="SECRET-KEY",
            connect_timeout=3.05,
            read_timeout=10.0,
            max_retries=1,
            retry_backoff=0.25,
            retry_sleep_max_seconds=1,
            max_response_bytes=2_097_152,
            cdn_allowed_hosts=(),
        )
        client = SteamClient(config, session=_StubSession())  # type: ignore[arg-type]

        with self.assertLogs("games.services.steam.client", level="WARNING") as logs:
            with self.assertRaises(SteamConnectionError):
                client.get_json("/ISteamApps/GetAppList/v2/", requires_api_key=True)

        output = "\n".join(logs.output)
        self.assertIn("[REDACTED]", output)
        self.assertNotIn("SECRET-KEY", output)
