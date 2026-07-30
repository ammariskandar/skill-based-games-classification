"""
Security configuration helpers — SBGC-41.

Pure validation functions for security-sensitive environment values.
Uses ``ImproperlyConfigured`` for startup failures; never echoes
secrets or full rejected values in error messages.
"""

from __future__ import annotations

import re

from django.core.exceptions import ImproperlyConfigured

# ---------------------------------------------------------------------------
# Secret key
# ---------------------------------------------------------------------------

# Development-only placeholder — never accept this in production.
_DEV_SECRET = "django-insecure-dev-key-do-not-use-in-production"

# Minimum acceptable secret length (arbitrary but prevents trivial values).
_MIN_SECRET_LENGTH = 20


def validate_secret_key(raw: str | None) -> str:
    """
    Return *raw* if it is a valid production secret key.

    Raises ``ImproperlyConfigured`` for missing, blank, known-placeholder,
    or trivially short values.  Error messages never contain the supplied
    value.
    """
    if raw is None:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must not be missing.")
    if not isinstance(raw, str):
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a string.")
    stripped = raw.strip()
    if not stripped:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must not be blank.")
    if stripped == _DEV_SECRET:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must not be the development placeholder."
        )
    if len(stripped) < _MIN_SECRET_LENGTH:
        raise ImproperlyConfigured(
            f"DJANGO_SECRET_KEY must be at least {_MIN_SECRET_LENGTH} characters."
        )
    return stripped


# ---------------------------------------------------------------------------
# Allowed hosts
# ---------------------------------------------------------------------------

# Allow: hostname, IPv4, IPv6 (bracketed), optional port.
# Disallow: scheme, path, query, fragment, credentials, wildcard, blank.
_HOST_RE = re.compile(
    r"^"
    r"(?!\*$)"  # not bare *
    r"[A-Za-z0-9]"  # start with alphanumeric
    r"[A-Za-z0-9.\-:\[\]]*"  # body
    r"[A-Za-z0-9\]]?"  # end with alphanumeric or ]
    r"$"
)


def parse_allowed_hosts(raw: str | None) -> list[str]:
    """
    Parse and validate a comma-separated ``DJANGO_ALLOWED_HOSTS`` value.

    Returns a deduplicated list of valid host strings.
    Raises ``ImproperlyConfigured`` for missing, blank, wildcard, or
    malformed entries.
    """
    if raw is None:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not be missing.")
    if not isinstance(raw, str):
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be a string.")
    stripped = raw.strip()
    if not stripped:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not be blank.")

    entries = [h.strip() for h in stripped.split(",") if h.strip()]
    if not entries:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not be blank.")

    seen: set[str] = set()
    result: list[str] = []

    for entry in entries:
        if entry == "*":
            raise ImproperlyConfigured(
                "DJANGO_ALLOWED_HOSTS must not contain a wildcard."
            )
        if "://" in entry:
            raise ImproperlyConfigured(
                "DJANGO_ALLOWED_HOSTS must not contain URLs (scheme detected)."
            )
        if "/" in entry:
            raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not contain paths.")
        if "?" in entry or "#" in entry:
            raise ImproperlyConfigured(
                "DJANGO_ALLOWED_HOSTS must not contain query strings or fragments."
            )
        if "@" in entry:
            raise ImproperlyConfigured(
                "DJANGO_ALLOWED_HOSTS must not contain credentials."
            )
        if not _HOST_RE.match(entry):
            raise ImproperlyConfigured(
                "DJANGO_ALLOWED_HOSTS contains a malformed host entry."
            )
        if entry not in seen:
            seen.add(entry)
            result.append(entry)

    return result


# ---------------------------------------------------------------------------
# CSRF trusted origins
# ---------------------------------------------------------------------------

_ORIGIN_RE = re.compile(r"^https?://[A-Za-z0-9]([A-Za-z0-9.\-]*[A-Za-z0-9])?(:\d+)?/?$")


def parse_trusted_origins(raw: str | None, *, require_https: bool) -> list[str]:
    """
    Parse and validate comma-separated ``CSRF_TRUSTED_ORIGINS``.

    Args:
        raw: Raw comma-separated value from the environment.
        require_https: If True, only ``https://`` origins are accepted.

    Returns a deduplicated list of valid origin strings.
    Raises ``ImproperlyConfigured`` for missing, blank, malformed,
    or HTTP-only origins when *require_https* is True.
    """
    if raw is None:
        raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must not be missing.")
    if not isinstance(raw, str):
        raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must be a string.")
    stripped = raw.strip()
    if not stripped:
        raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must not be blank.")

    entries = [o.strip() for o in stripped.split(",") if o.strip()]
    if not entries:
        raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must not be blank.")

    seen: set[str] = set()
    result: list[str] = []

    for origin in entries:
        if require_https and not origin.startswith("https://"):
            raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must use HTTPS origins.")
        if not _ORIGIN_RE.match(origin):
            raise ImproperlyConfigured(
                "CSRF_TRUSTED_ORIGINS contains a malformed origin. "
                "Expected scheme://host[:port] without path, query, or fragment."
            )
        if origin not in seen:
            seen.add(origin)
            result.append(origin)

    return result


# ---------------------------------------------------------------------------
# Non-negative integer
# ---------------------------------------------------------------------------


def parse_non_negative_integer(raw: str | None) -> int:
    """
    Parse *raw* as a non-negative integer.

    Returns the parsed ``int``.  Raises ``ImproperlyConfigured`` for
    missing, non-integer, or negative values.
    """
    if raw is None:
        raise ImproperlyConfigured("Value must not be missing.")
    if not isinstance(raw, str):
        raise ImproperlyConfigured("Value must be a string.")
    stripped = raw.strip()
    if not stripped:
        raise ImproperlyConfigured("Value must not be blank.")
    try:
        value = int(stripped)
    except ValueError:
        raise ImproperlyConfigured("Value must be a valid integer.") from None
    if value < 0:
        raise ImproperlyConfigured("Value must not be negative.")
    return value
