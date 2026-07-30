"""
Production settings.

Used by WSGI/ASGI entry points for deployed environments.

Imports shared base settings. Production security hardening
(secret enforcement, host enforcement, secure cookies, CORS, rate limits)
belongs to SBGC-39 and SBGC-41.
"""

from config.settings.base import *  # noqa: F403

DEBUG = False

# Django Ninja — SBGC-38
# Interactive API docs are disabled in production.
# OpenAPI schema remains available at /api/v1/openapi.json.
NINJA_API_DOCS_ENABLED = False
