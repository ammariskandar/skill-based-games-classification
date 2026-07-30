"""
Test settings — SBGC-39.

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
# Use a deterministic non-default path so routing tests can verify
# that /admin/ (the hard-coded legacy path) does NOT resolve.
ADMIN_URL_PATH = "test-admin"

# Database — SBGC-39 / test isolation
# Use an in-memory SQLite database for every test run.
# Never connect to Neon, never read DATABASE_URL for the test database,
# never prompt, and never create a PostgreSQL test database.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "CONN_MAX_AGE": 0,
    }
}
