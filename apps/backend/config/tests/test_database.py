"""
Database configuration tests — SBGC-39.

Covers SQLite fallback, PostgreSQL parsing, production/no-fallback
behaviour, error safety, and a real database connectivity probe.
"""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.database import build_database_config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FAKE_BASE = Path("/fake/apps/backend")

_FAKE_PG_URL = (
    "postgresql://test_user:test_password@example.neon.tech/"
    "test_db?sslmode=require&channel_binding=require"
)


# ============================================================================
# SQLite fallback
# ============================================================================


class SqliteFallbackTests(SimpleTestCase):
    """SQLite fallback when DATABASE_URL is absent."""

    def test_missing_url_selects_sqlite(self):
        cfg = build_database_config(None, _FAKE_BASE, allow_sqlite_fallback=True)
        db = cfg["default"]
        self.assertEqual(db["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(db["NAME"], _FAKE_BASE / "db.sqlite3")
        self.assertEqual(db["CONN_MAX_AGE"], 0)

    def test_empty_url_selects_sqlite(self):
        cfg = build_database_config("", _FAKE_BASE, allow_sqlite_fallback=True)
        self.assertEqual(cfg["default"]["ENGINE"], "django.db.backends.sqlite3")

    def test_whitespace_url_selects_sqlite(self):
        cfg = build_database_config("   ", _FAKE_BASE, allow_sqlite_fallback=True)
        self.assertEqual(cfg["default"]["ENGINE"], "django.db.backends.sqlite3")

    def test_fallback_path_is_sqlite3(self):
        cfg = build_database_config(None, _FAKE_BASE, allow_sqlite_fallback=True)
        self.assertEqual(cfg["default"]["NAME"], _FAKE_BASE / "db.sqlite3")


# ============================================================================
# Production / no-fallback
# ============================================================================


class NoFallbackTests(SimpleTestCase):
    """Production behaviour — missing URL must fail."""

    def test_missing_raises_improperly_configured(self):
        with self.assertRaises(ImproperlyConfigured):
            build_database_config(None, _FAKE_BASE, allow_sqlite_fallback=False)

    def test_empty_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            build_database_config("", _FAKE_BASE, allow_sqlite_fallback=False)

    def test_safe_message_no_credentials(self):
        with self.assertRaises(ImproperlyConfigured) as cm:
            build_database_config(None, _FAKE_BASE, allow_sqlite_fallback=False)
        msg = str(cm.exception).lower()
        self.assertIn("database_url", msg)
        self.assertNotIn("test_user", msg)
        self.assertNotIn("test_password", msg)


# ============================================================================
# PostgreSQL fake URL
# ============================================================================


class PostgreSqlFakeUrlTests(SimpleTestCase):
    """PostgreSQL configuration from a fake Neon URL."""

    def test_engine_is_postgresql(self):
        cfg = build_database_config(
            _FAKE_PG_URL, _FAKE_BASE, allow_sqlite_fallback=True
        )
        self.assertEqual(cfg["default"]["ENGINE"], "django.db.backends.postgresql")

    def test_name(self):
        cfg = build_database_config(
            _FAKE_PG_URL, _FAKE_BASE, allow_sqlite_fallback=True
        )
        self.assertEqual(cfg["default"]["NAME"], "test_db")

    def test_host(self):
        cfg = build_database_config(
            _FAKE_PG_URL, _FAKE_BASE, allow_sqlite_fallback=True
        )
        self.assertEqual(cfg["default"]["HOST"], "example.neon.tech")

    def test_user(self):
        cfg = build_database_config(
            _FAKE_PG_URL, _FAKE_BASE, allow_sqlite_fallback=True
        )
        self.assertEqual(cfg["default"]["USER"], "test_user")

    def test_password_parsed(self):
        cfg = build_database_config(
            _FAKE_PG_URL, _FAKE_BASE, allow_sqlite_fallback=True
        )
        self.assertEqual(cfg["default"]["PASSWORD"], "test_password")

    def test_sslmode(self):
        cfg = build_database_config(
            _FAKE_PG_URL, _FAKE_BASE, allow_sqlite_fallback=True
        )
        self.assertEqual(cfg["default"]["OPTIONS"]["sslmode"], "require")

    def test_channel_binding(self):
        cfg = build_database_config(
            _FAKE_PG_URL, _FAKE_BASE, allow_sqlite_fallback=True
        )
        self.assertEqual(cfg["default"]["OPTIONS"]["channel_binding"], "require")

    def test_connect_timeout(self):
        cfg = build_database_config(
            _FAKE_PG_URL, _FAKE_BASE, allow_sqlite_fallback=True
        )
        self.assertEqual(cfg["default"]["OPTIONS"]["connect_timeout"], 10)

    def test_conn_max_age_zero(self):
        cfg = build_database_config(
            _FAKE_PG_URL, _FAKE_BASE, allow_sqlite_fallback=True
        )
        self.assertEqual(cfg["default"]["CONN_MAX_AGE"], 0)


# ============================================================================
# Explicit SQLite URL
# ============================================================================


class ExplicitSqliteUrlTests(SimpleTestCase):
    """Explicit SQLite URL parsing."""

    def test_explicit_sqlite_url(self):
        cfg = build_database_config(
            "sqlite:///my.db", _FAKE_BASE, allow_sqlite_fallback=True
        )
        self.assertEqual(cfg["default"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(cfg["default"]["CONN_MAX_AGE"], 0)


# ============================================================================
# Invalid input
# ============================================================================


class InvalidInputTests(SimpleTestCase):
    """Malformed or unsupported URLs."""

    def test_malformed_url_raises_improperly_configured(self):
        with self.assertRaises(ImproperlyConfigured):
            build_database_config(
                "%%%not-a-url", _FAKE_BASE, allow_sqlite_fallback=True
            )

    def test_unsupported_engine_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            build_database_config(
                "mysql://u:p@h/d", _FAKE_BASE, allow_sqlite_fallback=True
            )

    def test_error_contains_no_original_url(self):
        # A URL with an unsupported scheme triggers our validation,
        # not django-environ's parser.
        with self.assertRaises(ImproperlyConfigured) as cm:
            build_database_config(
                "mysql://u:p@h/d", _FAKE_BASE, allow_sqlite_fallback=True
            )
        msg = str(cm.exception).lower()
        self.assertNotIn("mysql://", msg)


# ============================================================================
# Real connectivity probe (under Django test database)
# ============================================================================


class RealConnectivityTests(SimpleTestCase):
    """SELECT 1 against the configured test database."""

    databases = "__all__"

    def test_select_one(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone(), (1,))

    def test_vendor_matches(self):
        from django.conf import settings
        from django.db import connection

        configured_engine = settings.DATABASES["default"]["ENGINE"]
        if "sqlite" in configured_engine:
            self.assertEqual(connection.vendor, "sqlite")
        elif "postgresql" in configured_engine:
            self.assertEqual(connection.vendor, "postgresql")
