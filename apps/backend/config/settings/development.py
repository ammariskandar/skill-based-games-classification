"""
Development settings — SBGC-41.

Used by manage.py for local development (runserver, migrate, shell, etc.).

Imports shared base settings.  Uses permissive local defaults for
secret key, allowed hosts, and CSRF trusted origins.  Never use
these values in production.
"""

from config.database import build_database_config
from config.settings.base import *  # noqa: F403

DEBUG = True

# Django Ninja — SBGC-38
NINJA_API_DOCS_ENABLED = True

# Database — SBGC-39
DATABASES = build_database_config(DATABASE_URL, BASE_DIR, allow_sqlite_fallback=True)  # noqa: F405

# ---------------------------------------------------------------------------
# Security — SBGC-41 (development — permissive)
# ---------------------------------------------------------------------------

# Local development secret — explicitly marked insecure.
SECRET_KEY = env(  # noqa: F405
    "DJANGO_SECRET_KEY",
    default="django-insecure-dev-key-do-not-use-in-production",
)

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Local Astro/Vercel dev server origin for CSRF cookie-authenticated Admin.
CSRF_TRUSTED_ORIGINS = ["http://localhost:4321"]

# No CORS middleware — browser-to-Django access is not required.
# CORS_ALLOWED_ORIGINS is intentionally absent.

# No HTTPS enforcement in development.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# HSTS disabled in development.
SECURE_HSTS_SECONDS = 0
