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

# Per-label DNS validation: starts/ends alphanumeric, hyphens inside only,
# 1-63 characters per label.
_DNS_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")

_MAX_HOSTNAME_LENGTH = 253


def _validate_host_entry(entry: str) -> None:
    """
    Validate a single ``ALLOWED_HOSTS`` entry in-place.

    Raises ``ImproperlyConfigured`` with a safe message on failure.
    """
    # -- obvious rejections first --------------------------------------------
    if entry == "*":
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not contain a wildcard.")
    if "://" in entry:
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must not contain URLs (scheme detected)."
        )
    if ":" in entry:
        # ALLOWED_HOSTS entries are hostnames, not origins or network
        # addresses.  Rejecting ports catches operator mistakes and keeps
        # deployment host configuration canonical and predictable.
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not contain a port.")
    if "/" in entry:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not contain paths.")
    if "?" in entry or "#" in entry:
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must not contain query strings or fragments."
        )
    if "@" in entry:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not contain credentials.")
    if entry.startswith(".") or entry.endswith("."):
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must not start or end with a dot."
        )
    if ".." in entry:
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must not contain consecutive dots."
        )

    # -- IPv4 literal --------------------------------------------------------
    try:
        import ipaddress

        ipaddress.IPv4Address(entry)
        return  # valid IPv4 — no further label checks needed
    except ValueError:
        pass  # not an IPv4 literal; fall through to DNS validation

    # -- DNS hostname --------------------------------------------------------
    if len(entry) > _MAX_HOSTNAME_LENGTH:
        raise ImproperlyConfigured(
            f"DJANGO_ALLOWED_HOSTS entry exceeds {_MAX_HOSTNAME_LENGTH} characters."
        )

    labels = entry.split(".")
    for label in labels:
        if not label:
            raise ImproperlyConfigured(
                "DJANGO_ALLOWED_HOSTS must not contain empty labels."
            )
        if not _DNS_LABEL_RE.match(label):
            raise ImproperlyConfigured(
                "DJANGO_ALLOWED_HOSTS contains a malformed host entry."
            )


def parse_allowed_hosts(raw: str | None) -> list[str]:
    """
    Parse and validate a comma-separated ``DJANGO_ALLOWED_HOSTS`` value.

    Returns a deduplicated list of valid host strings.

    Supported forms: DNS hostnames and IPv4 literals.
    IPv6 literals are deliberately outside the current Render deployment
    requirement.  IPv6 support would require an intentional parser extension
    and tests.

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
        _validate_host_entry(entry)
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
