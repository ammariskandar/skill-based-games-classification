"""
Backend security tests — SBGC-41.

Covers secret-key validation, allowed hosts, CSRF trusted origins,
non-negative-integer parsing, password hashing, CORS absence,
production-settings import, HTTPS/proxy/cookie behaviour, and
hostile-header rejection.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, SimpleTestCase

from config.security import (
    parse_allowed_hosts,
    parse_non_negative_integer,
    parse_trusted_origins,
    validate_secret_key,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_MANAGE_PY = _BACKEND_DIR / "manage.py"
_DUMMY_PG_URL = (
    "postgresql://u:p@example.neon.tech/db?sslmode=require&channel_binding=require"
)


def _manage(*args, env=None):
    """Run manage.py in a subprocess and return (rc, stdout, stderr)."""
    merged = {**os.environ}
    if env is not None:
        merged.update(env)
    proc = subprocess.run(
        [sys.executable, str(_MANAGE_PY), *args],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        env=merged,
        timeout=15,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _prod_env(**overrides):
    """Return a dict with all required production security values."""
    return {
        "DJANGO_SECRET_KEY": "a-valid-production-secret-key-long-enough",
        "DATABASE_URL": _DUMMY_PG_URL,
        "DJANGO_ALLOWED_HOSTS": "example.com",
        "CSRF_TRUSTED_ORIGINS": "https://example.com",
        **overrides,
    }


# ============================================================================
# Secret key validation
# ============================================================================


class SecretKeyValidationTests(SimpleTestCase):
    def test_valid_key_accepted(self):
        result = validate_secret_key("a-valid-secret-that-is-long-enough")
        self.assertEqual(result, "a-valid-secret-that-is-long-enough")

    def test_none_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secret_key(None)

    def test_blank_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secret_key("")

    def test_whitespace_only_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secret_key("   ")

    def test_placeholder_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secret_key("django-insecure-dev-key-do-not-use-in-production")

    def test_short_value_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secret_key("short")


# ============================================================================
# Allowed hosts
# ============================================================================


class AllowedHostsTests(SimpleTestCase):
    # -- accepted -------------------------------------------------------------

    def test_valid_hostname(self):
        self.assertEqual(parse_allowed_hosts("example.com"), ["example.com"])

    def test_subdomain_accepted(self):
        self.assertEqual(
            parse_allowed_hosts("api.example.com"),
            ["api.example.com"],
        )

    def test_localhost_accepted(self):
        self.assertEqual(parse_allowed_hosts("localhost"), ["localhost"])

    def test_ipv4_accepted(self):
        self.assertEqual(parse_allowed_hosts("127.0.0.1"), ["127.0.0.1"])

    def test_label_with_internal_hyphen_accepted(self):
        self.assertEqual(
            parse_allowed_hosts("my-game.example.com"),
            ["my-game.example.com"],
        )

    def test_multiple_hosts(self):
        self.assertEqual(
            parse_allowed_hosts("example.com, api.example.com"),
            ["example.com", "api.example.com"],
        )

    def test_deduplicates(self):
        self.assertEqual(
            parse_allowed_hosts("a.com, a.com, b.com"),
            ["a.com", "b.com"],
        )

    # -- blank / missing ------------------------------------------------------

    def test_none_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts(None)

    def test_blank_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("")

    # -- wildcard / scheme / path / query / cred / port -----------------------

    def test_wildcard_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("*")

    def test_scheme_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("https://example.com")

    def test_path_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("example.com/path")

    def test_malformed_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("@invalid")

    def test_port_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("host:8000")

    def test_ip_with_port_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("example.com:443")

    # -- per-label DNS validation ---------------------------------------------

    def test_hostname_trailing_hyphen_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("host-.example.com")

    def test_hostname_label_leading_dot_hyphen_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("host.-example.com")

    def test_short_label_trailing_hyphen_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("a-.b.com")

    def test_short_label_leading_dot_hyphen_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("a.-b.com")

    def test_consecutive_dots_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("example..com")

    def test_label_too_long_rejected(self):
        long_label = "a" * 64
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts(f"{long_label}.com")

    def test_hostname_too_long_rejected(self):
        # 254 bytes of hostname exceeds the 253-char limit.
        long_host = "a" * 254
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts(long_host)

    # -- IPv6 unsupported -----------------------------------------------------

    def test_ipv6_bracketed_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("[::1]")

    def test_ipv6_unbracketed_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("::1")

    # -- leading / trailing dot -----------------------------------------------

    def test_leading_dot_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts(".example.com")

    def test_trailing_dot_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_allowed_hosts("example.com.")


# ============================================================================
# CSRF trusted origins
# ============================================================================


class CsrfTrustedOriginsTests(SimpleTestCase):
    def test_valid_http_origin(self):
        self.assertEqual(
            parse_trusted_origins("http://localhost:4321", require_https=False),
            ["http://localhost:4321"],
        )

    def test_valid_https_origin(self):
        self.assertEqual(
            parse_trusted_origins("https://example.com", require_https=True),
            ["https://example.com"],
        )

    def test_deduplicates(self):
        self.assertEqual(
            parse_trusted_origins("https://a.com, https://a.com", require_https=True),
            ["https://a.com"],
        )

    def test_http_rejected_when_https_required(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_trusted_origins("http://example.com", require_https=True)

    def test_none_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_trusted_origins(None, require_https=False)

    def test_blank_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_trusted_origins("", require_https=False)

    def test_malformed_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_trusted_origins("not-a-url", require_https=False)


# ============================================================================
# Non-negative integer
# ============================================================================


class NonNegativeIntegerTests(SimpleTestCase):
    def test_zero_accepted(self):
        self.assertEqual(parse_non_negative_integer("0"), 0)

    def test_positive_accepted(self):
        self.assertEqual(parse_non_negative_integer("3600"), 3600)

    def test_none_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_non_negative_integer(None)

    def test_blank_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_non_negative_integer("")

    def test_negative_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_non_negative_integer("-1")

    def test_non_integer_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_non_negative_integer("abc")


# ============================================================================
# Password hashing
# ============================================================================


class PasswordHashingTests(SimpleTestCase):
    def test_only_pbkdf2_sha256_configured(self):
        self.assertEqual(
            settings.PASSWORD_HASHERS,
            ["django.contrib.auth.hashers.PBKDF2PasswordHasher"],
        )

    def test_make_password_produces_pbkdf2_sha256(self):
        hashed = make_password("test-password-123")
        self.assertTrue(hashed.startswith("pbkdf2_sha256$"))


# ============================================================================
# CORS absence
# ============================================================================


class CorsAbsenceTests(SimpleTestCase):
    def test_no_cors_allow_origin_header(self):
        """Arbitrary Origin does not cause an Access-Control-Allow-Origin."""
        c = Client()
        r = c.get("/api/v1/", HTTP_ORIGIN="https://evil.com")
        self.assertNotIn("Access-Control-Allow-Origin", r)

    def test_no_cors_middleware(self):
        self.assertNotIn("django-cors-headers", str(settings.MIDDLEWARE).lower())
        self.assertNotIn("corsheaders", str(settings.MIDDLEWARE).lower())


# ============================================================================
# Hostile Host header rejection
# ============================================================================


class HostileHostHeaderTests(SimpleTestCase):
    def test_allowed_host_accepted(self):
        c = Client()
        r = c.get("/api/v1/", HTTP_HOST="testserver")
        self.assertEqual(r.status_code, 200)

    def test_arbitrary_host_rejected(self):
        c = Client()
        r = c.get("/api/v1/", HTTP_HOST="evil.com")
        self.assertEqual(r.status_code, 400)


# ============================================================================
# Production-settings import and behaviour (subprocess)
# ============================================================================


class ProductionSettingsImportTests(SimpleTestCase):
    """Validate production settings under controlled dummy environment."""

    def _check_prod(self, **env_overrides):
        env = _prod_env(**env_overrides)
        return _manage("check", "--settings=config.settings.production", env=env)

    def test_valid_dummy_config_imports(self):
        rc, stdout, stderr = self._check_prod()
        self.assertEqual(rc, 0, f"stderr: {stderr}")

    def test_production_debug_is_false(self):
        env = _prod_env()
        rc, stdout, stderr = _manage(
            "shell",
            "--settings=config.settings.production",
            "-c",
            "from django.conf import settings; "
            "assert settings.DEBUG is False; "
            "print('DEBUG_OK')",
            env=env,
        )
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        self.assertIn("DEBUG_OK", stdout)

    def test_production_secret_required(self):
        env = _prod_env(DJANGO_SECRET_KEY="")
        rc, stdout, stderr = self._check_prod(**env)
        self.assertNotEqual(rc, 0)

    def test_production_secret_rejects_placeholder(self):
        env = _prod_env(
            DJANGO_SECRET_KEY="django-insecure-dev-key-do-not-use-in-production"
        )
        rc, stdout, stderr = self._check_prod(**env)
        self.assertNotEqual(rc, 0)

    def test_production_secret_rejects_short(self):
        env = _prod_env(DJANGO_SECRET_KEY="short")
        rc, stdout, stderr = self._check_prod(**env)
        self.assertNotEqual(rc, 0)

    def test_production_allowed_hosts_required(self):
        env = _prod_env(DJANGO_ALLOWED_HOSTS="")
        rc, stdout, stderr = self._check_prod(**env)
        self.assertNotEqual(rc, 0)

    def test_production_allowed_hosts_rejects_wildcard(self):
        env = _prod_env(DJANGO_ALLOWED_HOSTS="*")
        rc, stdout, stderr = self._check_prod(**env)
        self.assertNotEqual(rc, 0)

    def test_production_allowed_hosts_rejects_malformed(self):
        env = _prod_env(DJANGO_ALLOWED_HOSTS="@evil")
        rc, stdout, stderr = self._check_prod(**env)
        self.assertNotEqual(rc, 0)

    def test_production_csrf_https_required(self):
        env = _prod_env(CSRF_TRUSTED_ORIGINS="http://example.com")
        rc, stdout, stderr = self._check_prod(**env)
        self.assertNotEqual(rc, 0)

    def test_production_csrf_rejects_malformed(self):
        env = _prod_env(CSRF_TRUSTED_ORIGINS="not-an-origin")
        rc, stdout, stderr = self._check_prod(**env)
        self.assertNotEqual(rc, 0)

    def test_production_database_url_required(self):
        env = _prod_env(DATABASE_URL="")
        rc, stdout, stderr = self._check_prod(**env)
        self.assertNotEqual(rc, 0)


# ============================================================================
# Production cookie/header behaviour (subprocess)
# ============================================================================


class ProductionCookieHeaderTests(SimpleTestCase):
    """Verify production security settings via subprocess shell."""

    def _prod_shell(self, code, **overrides):
        env = _prod_env(**overrides)
        return _manage(
            "shell",
            "--settings=config.settings.production",
            "-c",
            code,
            env=env,
        )

    def test_secure_cookies(self):
        rc, stdout, stderr = self._prod_shell(
            "from django.conf import settings; "
            "assert settings.SESSION_COOKIE_SECURE is True; "
            "assert settings.CSRF_COOKIE_SECURE is True; "
            "assert settings.SESSION_COOKIE_HTTPONLY is True; "
            "assert settings.SESSION_COOKIE_SAMESITE == 'Lax'; "
            "assert settings.CSRF_COOKIE_SAMESITE == 'Lax'; "
            "print('COOKIES_OK')"
        )
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        self.assertIn("COOKIES_OK", stdout)

    def test_ssl_redirect_true(self):
        rc, stdout, stderr = self._prod_shell(
            "from django.conf import settings; "
            "assert settings.SECURE_SSL_REDIRECT is True; "
            "print('SSL_OK')"
        )
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        self.assertIn("SSL_OK", stdout)

    def test_response_headers(self):
        rc, stdout, stderr = self._prod_shell(
            "from django.conf import settings; "
            "assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True; "
            "assert settings.X_FRAME_OPTIONS == 'DENY'; "
            "assert settings.SECURE_REFERRER_POLICY"
            " == 'strict-origin-when-cross-origin'; "
            "assert settings.SECURE_CROSS_ORIGIN_OPENER_POLICY == 'same-origin'; "
            "print('HEADERS_OK')"
        )
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        self.assertIn("HEADERS_OK", stdout)

    def test_proxy_header(self):
        rc, stdout, stderr = self._prod_shell(
            "from django.conf import settings; "
            "assert settings.SECURE_PROXY_SSL_HEADER"
            " == ('HTTP_X_FORWARDED_PROTO', 'https'); "
            "print('PROXY_OK')"
        )
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        self.assertIn("PROXY_OK", stdout)

    def test_password_hasher_in_production(self):
        rc, stdout, stderr = self._prod_shell(
            "from django.conf import settings; "
            "assert settings.PASSWORD_HASHERS == "
            "['django.contrib.auth.hashers.PBKDF2PasswordHasher']; "
            "print('HASHER_OK')"
        )
        self.assertEqual(rc, 0, f"stderr: {stderr}")
        self.assertIn("HASHER_OK", stdout)


# ============================================================================
# Development HTTP behaviour (in-process)
# ============================================================================


class DevelopmentHttpTests(SimpleTestCase):
    def test_dev_session_cookie_not_secure(self):
        self.assertFalse(settings.SESSION_COOKIE_SECURE)

    def test_dev_ssl_redirect_false(self):
        self.assertFalse(settings.SECURE_SSL_REDIRECT)


# ============================================================================
# Test-settings isolation
# ============================================================================


class TestSettingsIsolationTests(SimpleTestCase):
    def test_test_settings_secret_is_deterministic(self):
        self.assertEqual(
            settings.SECRET_KEY,
            "test-secret-key-for-automated-tests-only-do-not-use-elsewhere",
        )

    def test_testsettings_include_testserver(self):
        self.assertIn("testserver", settings.ALLOWED_HOSTS)

    def test_testsettings_session_cookie_not_secure(self):
        self.assertFalse(settings.SESSION_COOKIE_SECURE)


# ============================================================================
# Request-size settings
# ============================================================================


class RequestSizeTests(SimpleTestCase):
    def test_data_upload_max_memory_size(self):
        self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 2_621_440)

    def test_file_upload_max_memory_size(self):
        self.assertEqual(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 2_621_440)

    def test_max_number_fields(self):
        self.assertEqual(settings.DATA_UPLOAD_MAX_NUMBER_FIELDS, 1_000)

    def test_max_number_files(self):
        self.assertEqual(settings.DATA_UPLOAD_MAX_NUMBER_FILES, 20)
