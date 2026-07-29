"""
Production settings.

Used by WSGI/ASGI entry points for deployed environments.

Imports shared base settings. Production security hardening
(secret enforcement, host enforcement, secure cookies, CORS, rate limits)
belongs to SBGC-39 and SBGC-41.
"""

from config.settings.base import *  # noqa: F403

DEBUG = False
