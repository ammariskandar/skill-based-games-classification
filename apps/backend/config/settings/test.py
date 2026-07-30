"""
Test settings — SBGC-39 / SBGC-41.

Deterministic, secret-free, Neon-isolated settings for automated
backend tests and CI.  Always uses an in-memory SQLite database
regardless of whether a local .env file contains a Neon DATABASE_URL.

Do not use this module for development runserver, migrate, or shell.
"""

from config.settings.base import *  # noqa: F403

DEBUG = True

# Django Ninja — SBGC-38
NINJA_API_DOCS_ENABLED = True

# Django Admin — SBGC-40
ADMIN_URL_PATH = "test-admin"

# Database — SBGC-39 / test isolation
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "CONN_MAX_AGE": 0,
    }
}

# ---------------------------------------------------------------------------
# Security — SBGC-41 (test — deterministic, no local .env)
# ---------------------------------------------------------------------------

SECRET_KEY = "test-secret-key-for-automated-tests-only-do-not-use-elsewhere"

ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"]

CSRF_TRUSTED_ORIGINS = ["http://testserver"]

# No CORS middleware.

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
