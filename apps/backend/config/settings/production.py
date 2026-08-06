"""
Production settings — SBGC-41 / SBGC-43.

Used by WSGI entry points for deployed environments (Gunicorn on Render).

All security-sensitive values are validated at settings-import time.
Missing or malformed values raise ImproperlyConfigured — production
never falls back to development defaults.

SBGC-43 additions:
- PostgreSQL-only database enforcement (no SQLite in production).
- Strengthened secret-key validation (50+ chars, 5+ unique, no insecure prefix).
- Non-default ADMIN_URL_PATH required.
- Structured CSRF trusted-origin parsing with hostname and port validation.
- Validated DJANGO_LOG_LEVEL (default INFO).
"""

from django.core.exceptions import ImproperlyConfigured

from config.database import build_database_config
from config.security import (
    parse_allowed_hosts,
    parse_non_negative_integer,
    parse_trusted_origins,
    validate_log_level,
    validate_secret_key,
)
from config.settings.base import *  # noqa: F403

DEBUG = False

# Django Ninja — SBGC-38
NINJA_API_DOCS_ENABLED = False

# ---------------------------------------------------------------------------
# Database — SBGC-43 (PostgreSQL-only enforcement)
# ---------------------------------------------------------------------------

DATABASES = build_database_config(
    DATABASE_URL,  # noqa: F405  # pyright: ignore[reportArgumentType]
    BASE_DIR,  # noqa: F405
    allow_sqlite_fallback=False,
    require_postgresql=True,
)

# ---------------------------------------------------------------------------
# Logging — SBGC-43
# ---------------------------------------------------------------------------

_log_level_raw = env("DJANGO_LOG_LEVEL", default="INFO")  # noqa: F405  # pyright: ignore[reportArgumentType]
_log_level = validate_log_level(_log_level_raw)  # pyright: ignore[reportArgumentType]

LOGGING["root"]["level"] = _log_level  # noqa: F405
LOGGING["loggers"]["django"]["level"] = _log_level  # noqa: F405

# ---------------------------------------------------------------------------
# Security — SBGC-41 / SBGC-43 (production — fail-closed)
# ---------------------------------------------------------------------------

# -- Secret key — SBGC-43 (strengthened) --------------------------------------

SECRET_KEY = validate_secret_key(env("DJANGO_SECRET_KEY", default=None))  # noqa: F405  # pyright: ignore[reportArgumentType]

# -- Admin path — SBGC-43 (production must be non-default) ---------------------

_ADMIN_RAW = env("ADMIN_URL_PATH", default=None)  # noqa: F405  # pyright: ignore[reportArgumentType]
if _ADMIN_RAW is None:
    raise ImproperlyConfigured("ADMIN_URL_PATH is required in production.")
if not isinstance(_ADMIN_RAW, str):
    raise ImproperlyConfigured("ADMIN_URL_PATH must be a string.")
_stripped_admin = _ADMIN_RAW.strip()
if not _stripped_admin:
    raise ImproperlyConfigured("ADMIN_URL_PATH must not be blank.")
if _stripped_admin.lower() == "admin":
    raise ImproperlyConfigured(
        "ADMIN_URL_PATH must not be the default 'admin' in production."
    )
ADMIN_URL_PATH = validate_admin_url_path(_stripped_admin)  # noqa: F405

# -- Allowed hosts ------------------------------------------------------------

_raw_hosts = env("DJANGO_ALLOWED_HOSTS", default=None)  # noqa: F405  # pyright: ignore[reportArgumentType]
ALLOWED_HOSTS = parse_allowed_hosts(_raw_hosts)  # pyright: ignore[reportArgumentType]

# -- CSRF — SBGC-43 (structured origin parsing) --------------------------------

_raw_csrf = env("CSRF_TRUSTED_ORIGINS", default=None)  # noqa: F405  # pyright: ignore[reportArgumentType]
CSRF_TRUSTED_ORIGINS = parse_trusted_origins(_raw_csrf, require_https=True)  # pyright: ignore[reportArgumentType]

# No CORS middleware — browser-to-Django access is not required.
# CORS_ALLOWED_ORIGINS is intentionally absent.

# -- HTTPS and proxy ----------------------------------------------------------

# Render forwards HTTPS via X-Forwarded-Proto.
# https://render.com/docs/deploy-django#production-settings
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# -- HSTS (staged) ------------------------------------------------------------

_hsts_raw = env("DJANGO_SECURE_HSTS_SECONDS", default="0")  # noqa: F405  # pyright: ignore[reportArgumentType]
SECURE_HSTS_SECONDS = parse_non_negative_integer(_hsts_raw)  # pyright: ignore[reportArgumentType]
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# -- Response protections -----------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
