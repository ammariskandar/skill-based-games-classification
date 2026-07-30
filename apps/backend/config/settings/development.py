"""
Development settings.

Used by manage.py for local development (runserver, migrate, shell, etc.).

Imports shared base settings and enables debug mode.
"""

from config.settings.base import *  # noqa: F403

DEBUG = True

# Django Ninja — SBGC-38
# Enable interactive API docs in development only.
NINJA_API_DOCS_ENABLED = True
