"""
PostgreSQL-specific test settings — SBGC-52.

Uses POSTGRES_TEST_DATABASE_URL for isolated PostgreSQL constraint,
migration, index, and transaction verification.  Never uses production
Neon or the developer's .env.

Do not use this module for SQLite tests, development, or production.
"""

import os

# Prevent base.py from reading the developer's real .env file.
os.environ["DJANGO_SKIP_DOTENV"] = "1"

from django.core.exceptions import ImproperlyConfigured

from config.database import build_database_config
from config.settings.base import *  # noqa: F403, E402

DEBUG = True

# Django Ninja
NINJA_API_DOCS_ENABLED = False

# Django Admin
ADMIN_URL_PATH = "test-admin"

# ---------------------------------------------------------------------------
# Database — requires POSTGRES_TEST_DATABASE_URL
# ---------------------------------------------------------------------------

_raw_url = os.environ.get("POSTGRES_TEST_DATABASE_URL", "").strip()
if not _raw_url:
    raise ImproperlyConfigured(
        "POSTGRES_TEST_DATABASE_URL is required for PostgreSQL tests. "
        "Set it to a disposable PostgreSQL connection string. "
        "Never use a production Neon URL."
    )

DATABASES = build_database_config(
    _raw_url,
    BASE_DIR,  # noqa: F405
    allow_sqlite_fallback=False,
    require_postgresql=True,
)

# ---------------------------------------------------------------------------
# Security — deterministic, no local .env
# ---------------------------------------------------------------------------

SECRET_KEY = "test-secret-key-for-postgresql-tests-only-do-not-use-elsewhere"

ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"]

CSRF_TRUSTED_ORIGINS = ["http://testserver"]

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# ---------------------------------------------------------------------------
# Steam — deterministic, never reads developer .env
# ---------------------------------------------------------------------------

STEAM_WEB_API_KEY = ""
STEAM_CONNECT_TIMEOUT_SECONDS = "3.05"
STEAM_READ_TIMEOUT_SECONDS = "10"
STEAM_MAX_RETRIES = "2"
STEAM_RETRY_BACKOFF_SECONDS = "0.25"
STEAM_MAX_RESPONSE_BYTES = "2097152"
STEAM_CDN_ALLOWED_HOSTS = ""
STEAM_RETRY_SLEEP_MAX_SECONDS = "5"

# ---------------------------------------------------------------------------
# WhiteNoise, logging, development seeding — disabled
# ---------------------------------------------------------------------------

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

LOGGING["root"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405

DEVELOPMENT_SEEDING_ENABLED = False
