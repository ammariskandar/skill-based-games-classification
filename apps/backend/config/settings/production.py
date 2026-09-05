"""
Production settings — SBGC-41 / SBGC-43 / SBGC-104.

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

SBGC-104 additions:
- DJANGO_DEBUG must never be truthy in production (fail-fast).
- RECAPTCHA_SECRET_KEY and STEAM_WEB_API_KEY are required (fail-fast).
- Strict boolean parsing for DB_SSL_REQUIRE (and DJANGO_DEBUG guard).
"""

from django.core.exceptions import ImproperlyConfigured

from config.database import build_database_config
from config.env_typing import (
    env_optional_str,
    env_str,
    get_env_bool,
)
from config.security import (
    parse_allowed_hosts,
    parse_non_negative_integer,
    parse_trusted_origins,
    validate_log_level,
    validate_secret_key,
)
from config.settings.base import *  # noqa: F403

DEBUG = False

# -- Debug invariant — SBGC-104 ----------------------------------------------
# Production must never run with DEBUG enabled.  Reject a truthy DJANGO_DEBUG
# at import time rather than silently ignoring the operator's request.
if get_env_bool("DJANGO_DEBUG", default=False):
    raise ImproperlyConfigured("DJANGO_DEBUG must not be enabled in production.")

# Django Ninja — SBGC-38
NINJA_API_DOCS_ENABLED = False

# ---------------------------------------------------------------------------
# Database — SBGC-43 (PostgreSQL-only enforcement)
# ---------------------------------------------------------------------------

DATABASES = build_database_config(
    DATABASE_URL,  # noqa: F405
    BASE_DIR,  # noqa: F405
    allow_sqlite_fallback=False,
    require_postgresql=True,
    ssl_require=get_env_bool("DB_SSL_REQUIRE", default=True),
)

# ---------------------------------------------------------------------------
# Logging — SBGC-43
# ---------------------------------------------------------------------------

_log_level_raw = env_str(env, "DJANGO_LOG_LEVEL", default="INFO")  # noqa: F405
_log_level = validate_log_level(_log_level_raw)

LOGGING["root"]["level"] = _log_level  # noqa: F405
LOGGING["loggers"]["django"]["level"] = _log_level  # noqa: F405

# ---------------------------------------------------------------------------
# Security — SBGC-41 / SBGC-43 (production — fail-closed)
# ---------------------------------------------------------------------------

# -- Secret key — SBGC-43 (strengthened) --------------------------------------

SECRET_KEY = validate_secret_key(env_optional_str(env, "DJANGO_SECRET_KEY"))  # noqa: F405

# -- Admin path — SBGC-43 (production must be non-default) ---------------------

_ADMIN_RAW = env_optional_str(env, "ADMIN_URL_PATH")  # noqa: F405
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

_raw_hosts = env_optional_str(env, "DJANGO_ALLOWED_HOSTS")  # noqa: F405
ALLOWED_HOSTS = parse_allowed_hosts(_raw_hosts)

# -- CSRF — SBGC-43 (structured origin parsing) --------------------------------

_raw_csrf = env_optional_str(env, "CSRF_TRUSTED_ORIGINS")  # noqa: F405
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

# ---------------------------------------------------------------------------
# External service credentials — SBGC-104 (required in production)
# ---------------------------------------------------------------------------

# reCAPTCHA v3 secret: without it the score gate silently bypasses (DEBUG-only
# behaviour), which must never happen in production.
_recaptcha_secret = env_optional_str(env, "RECAPTCHA_SECRET_KEY")  # noqa: F405
if not _recaptcha_secret or not _recaptcha_secret.strip():
    raise ImproperlyConfigured("RECAPTCHA_SECRET_KEY must be set in production.")

# SBGC-106 — reCAPTCHA v3 site key: the admin login page needs it to render the
# challenge that feeds the enforced score gate.  Missing it would make every
# admin login fail silently at reCAPTCHA time, so fail fast instead.
_recaptcha_site_key = env_optional_str(env, "RECAPTCHA_SITE_KEY")  # noqa: F405
if not _recaptcha_site_key or not _recaptcha_site_key.strip():
    raise ImproperlyConfigured("RECAPTCHA_SITE_KEY must be set in production.")

# Steam Web API key: declared as a Render secret; authenticated Steam calls
# (metadata refresh / import) require it.
_steam_api_key = env_optional_str(env, "STEAM_WEB_API_KEY")  # noqa: F405
if not _steam_api_key or not _steam_api_key.strip():
    raise ImproperlyConfigured("STEAM_WEB_API_KEY must be set in production.")

# -- HSTS (production-only) — SBGC-105 --------------------------------------
# Full-strength HSTS by default (1 year, includeSubDomains, preload).  The
# duration remains env-configurable for staged rollouts, but production's
# default is no longer zero.
_hsts_raw = env_str(env, "DJANGO_SECURE_HSTS_SECONDS", default="31536000")  # noqa: F405
SECURE_HSTS_SECONDS = parse_non_negative_integer(_hsts_raw)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# -- Response protections -----------------------------------------------------
# nosniff / Referrer-Policy / X-Frame-Options (SAMEORIGIN) / COOP
# (same-origin-allow-popups) are defined once in base.py (all environments)
# and inherited here — see SBGC-105.
