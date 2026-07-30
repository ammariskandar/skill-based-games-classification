"""
Production settings — SBGC-41.

Used by WSGI/ASGI entry points for deployed environments.

All security-sensitive values are validated at settings-import time.
Missing or malformed values raise ImproperlyConfigured — production
never falls back to development defaults.
"""

from config.database import build_database_config
from config.security import (
    parse_allowed_hosts,
    parse_non_negative_integer,
    parse_trusted_origins,
    validate_secret_key,
)
from config.settings.base import *  # noqa: F403

DEBUG = False

# Django Ninja — SBGC-38
NINJA_API_DOCS_ENABLED = False

# Database — SBGC-39
DATABASES = build_database_config(DATABASE_URL, BASE_DIR, allow_sqlite_fallback=False)  # noqa: F405

# ---------------------------------------------------------------------------
# Security — SBGC-41 (production — fail-closed)
# ---------------------------------------------------------------------------

# -- Secret key ---------------------------------------------------------------

SECRET_KEY = validate_secret_key(env("DJANGO_SECRET_KEY", default=None))  # noqa: F405

# -- Allowed hosts ------------------------------------------------------------

_raw_hosts = env("DJANGO_ALLOWED_HOSTS", default=None)  # noqa: F405
ALLOWED_HOSTS = parse_allowed_hosts(_raw_hosts)

# -- CSRF ---------------------------------------------------------------------

_raw_csrf = env("CSRF_TRUSTED_ORIGINS", default=None)  # noqa: F405
CSRF_TRUSTED_ORIGINS = parse_trusted_origins(_raw_csrf, require_https=True)

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

_hsts_raw = env("DJANGO_SECURE_HSTS_SECONDS", default="0")  # noqa: F405
SECURE_HSTS_SECONDS = parse_non_negative_integer(_hsts_raw)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# -- Response protections -----------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
