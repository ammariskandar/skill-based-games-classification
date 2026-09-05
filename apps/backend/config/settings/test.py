"""
Test settings — SBGC-39 / SBGC-41 / SBGC-43.

Deterministic, secret-free, Neon-isolated settings for automated
backend tests and CI.  Always uses an in-memory SQLite database
regardless of whether a local .env file contains a Neon DATABASE_URL.

Do not use this module for development runserver, migrate, or shell.
"""

import os

# Prevent base.py from reading the developer's real .env file.
# Must be set before importing config.settings.base.
os.environ["DJANGO_SKIP_DOTENV"] = "1"

from config.settings.base import *  # noqa: F403, E402

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

# SBGC-106 — a non-empty site key renders the reCAPTCHA challenge into the
# admin login template so the obfuscated-path test can assert it is enabled.
RECAPTCHA_SITE_KEY = "test-recaptcha-site-key"

# SBGC-106 — disable admin write/delete throttling in the shared test suite so
# the LocMemCache pacing counters never leak across unrelated admin tests.
# The throttle logic is tested directly in security.tests.test_admin_security.
ADMIN_THROTTLING_ENABLED = False

# No CORS middleware.

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Steam — SBGC-42 (test — deterministic, never reads developer .env)
# These raw string values are consumed by steam_client_config_from_settings().
# The test suite overrides them individually when testing parse/validation.
STEAM_WEB_API_KEY = ""
STEAM_CONNECT_TIMEOUT_SECONDS = "3.05"
STEAM_READ_TIMEOUT_SECONDS = "10"
STEAM_MAX_RETRIES = "2"
STEAM_RETRY_BACKOFF_SECONDS = "0.25"
STEAM_MAX_RESPONSE_BYTES = "2097152"
STEAM_CDN_ALLOWED_HOSTS = ""
STEAM_RETRY_SLEEP_MAX_SECONDS = "5"

# SBGC-43 — WhiteNoise non-manifest storage (no collectstatic in tests).
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# SBGC-43 — logging (deterministic test level, suppress noise).
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405
