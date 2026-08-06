"""
Type-safe django-environ access — SBGC-53.

Narrow helpers that read environment variables with safe defaults,
avoiding the django-environ stub issue where ``default`` is typed
as ``NoValue``.  Only one local suppression per helper.
"""

from __future__ import annotations

import environ
from django.core.exceptions import ImproperlyConfigured


def env_str(env_obj: environ.Env, name: str, *, default: str) -> str:
    """Read a required string environment variable with a default."""
    value: object = env_obj(name, default=default)  # pyright: ignore[reportArgumentType]
    if not isinstance(value, str):
        raise ImproperlyConfigured(f"Environment variable {name} must be a string.")
    return value
