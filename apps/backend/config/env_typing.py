"""
Type-safe django-environ access — SBGC-53 / SBGC-104.

Narrow helpers that read environment variables with safe defaults,
avoiding the django-environ stub issue where ``default`` is typed
as ``NoValue``.  Only one local suppression per helper.

SBGC-104 adds strict, deterministic boolean and list parsing so a
misconfigured ``DJANGO_DEBUG``, ``DB_SSL_REQUIRE``, or ``ALLOWED_HOSTS``
cannot silently flip security posture.
"""

from __future__ import annotations

import os

import environ
from django.core.exceptions import ImproperlyConfigured

# Accepted spellings for strict boolean parsing (lower-cased, trimmed).
_BOOL_TRUTHY = frozenset({"true", "1", "yes", "on"})
_BOOL_FALSY = frozenset({"false", "0", "no", "off", ""})


def get_env_bool(name: str, *, default: bool = False) -> bool:
    """Read *name* as a strict boolean.

    Accepts ``true/1/yes/on`` (case-insensitive) and
    ``false/0/no/off``.  An unset variable returns *default*; any other
    value raises ``ImproperlyConfigured`` so a typo fails fast instead of
    silently weakening a security flag.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalised = raw.strip().lower()
    if normalised in _BOOL_TRUTHY:
        return True
    if normalised in _BOOL_FALSY:
        return False
    raise ImproperlyConfigured(
        f"{name} must be a boolean (true/false/1/0/yes/no/on/off), got {raw!r}."
    )


def get_env_list(name: str, *, default: list[str] | None = None) -> list[str]:
    """Read *name* as a comma-separated list of trimmed, non-empty items."""
    raw = os.environ.get(name)
    if raw is None:
        return list(default) if default else []
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_str(env_obj: environ.Env, name: str, *, default: str) -> str:
    """Read a required string environment variable with a default."""
    value: object = env_obj(name, default=default)  # pyright: ignore[reportArgumentType]
    if not isinstance(value, str):
        raise ImproperlyConfigured(f"Environment variable {name} must be a string.")
    return value


def env_optional_str(env_obj: environ.Env, name: str) -> str | None:
    """Read an optional string env var (None if absent)."""
    value: object = env_obj(name, default=None)  # pyright: ignore[reportArgumentType]
    if value is None:
        return None
    if not isinstance(value, str):
        raise ImproperlyConfigured(
            f"Environment variable {name} must be a string if set."
        )
    return value
