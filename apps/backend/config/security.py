"""
Security configuration helpers — SBGC-41 / SBGC-43.

Pure validation functions for security-sensitive environment values.
Uses ``ImproperlyConfigured`` for startup failures; never echoes
secrets or full rejected values in error messages.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

# ---------------------------------------------------------------------------
# Secret key — SBGC-43 (strengthened to align with Django security.W009)
# ---------------------------------------------------------------------------

# Development-only placeholder — never accept this in production.
_DEV_SECRET = "django-insecure-dev-key-do-not-use-in-production"

# Minimum acceptable secret length (Django W009 recommends 50).
_MIN_SECRET_LENGTH = 50

# Minimum unique characters (prevents repeated-character placeholders).
_MIN_UNIQUE_CHARS = 5

# Known insecure prefixes.
_INSECURE_PREFIXES = (
    "django-insecure-",
    "django-secret-",
)


def validate_secret_key(raw: str | None) -> str:
    """
    Return *raw* if it is a valid production secret key.

    Raises ``ImproperlyConfigured`` for missing, blank, short, low-entropy,
    known-insecure, or known-placeholder values.  Error messages never
    contain the supplied value.
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
    unique = len(set(stripped))
    if unique < _MIN_UNIQUE_CHARS:
        raise ImproperlyConfigured(
            f"DJANGO_SECRET_KEY must contain at least "
            f"{_MIN_UNIQUE_CHARS} unique characters."
        )
    lower = stripped.lower()
    for prefix in _INSECURE_PREFIXES:
        if lower.startswith(prefix):
            raise ImproperlyConfigured(
                "DJANGO_SECRET_KEY must not use an insecure prefix."
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
    if entry == "*":
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not contain a wildcard.")
    if "://" in entry:
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must not contain URLs (scheme detected)."
        )
    if ":" in entry:
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
    requirement.

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
# CSRF trusted origins — SBGC-43 (structured URL parsing)
# ---------------------------------------------------------------------------


def _validate_csrf_origin(origin: str, *, require_https: bool) -> str:
    """
    Validate a single CSRF trusted origin and return the normalised form.

    Normalises: scheme to lowercase, hostname to lowercase, trailing slash
    to absent.  Raises ``ImproperlyConfigured`` for any violation.
    """
    if not origin:
        raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS entry must not be blank.")

    parsed = urlparse(origin)

    # Scheme.
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must use http:// or https://.")
    if require_https and scheme != "https":
        raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must use HTTPS origins.")

    # Hostname (netloc without port/credentials).
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ImproperlyConfigured(
            "CSRF_TRUSTED_ORIGINS must contain a nonempty hostname."
        )

    # Reject credentials, query, fragment, path beyond root.
    if "@" in parsed.netloc:
        raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must not contain credentials.")
    if parsed.query:
        raise ImproperlyConfigured(
            "CSRF_TRUSTED_ORIGINS must not contain a query string."
        )
    if parsed.fragment:
        raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must not contain a fragment.")
    if parsed.path and parsed.path != "/":
        raise ImproperlyConfigured(
            "CSRF_TRUSTED_ORIGINS must not contain a path beyond root '/'."
        )

    # Port validation.
    port = parsed.port
    if port is not None:
        if port < 1 or port > 65535:
            raise ImproperlyConfigured(
                f"CSRF_TRUSTED_ORIGINS port must be 1–65535, got {port}."
            )

    # Hostname validation (reuse shared DNS label rules).
    _validate_host_entry(hostname)

    # Build normalised origin.
    if port:
        return f"{scheme}://{hostname}:{port}"
    return f"{scheme}://{hostname}"


def parse_trusted_origins(raw: str | None, *, require_https: bool) -> list[str]:
    """
    Parse and validate comma-separated ``CSRF_TRUSTED_ORIGINS``.

    Args:
        raw: Raw comma-separated value from the environment.
        require_https: If True, only ``https://`` origins are accepted.

    Returns a deduplicated list of validated, normalised origin strings.
    Raises ``ImproperlyConfigured`` for missing, blank, or malformed origins.
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

    for entry in entries:
        origin = _validate_csrf_origin(entry, require_https=require_https)
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


# ---------------------------------------------------------------------------
# Log level — SBGC-43
# ---------------------------------------------------------------------------

_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def validate_log_level(raw: str | None) -> str:
    """
    Validate *raw* as a supported Django log level.

    Returns the upper-cased level string.  Raises ``ImproperlyConfigured``
    for missing, blank, or unsupported values.
    """
    if raw is None:
        raise ImproperlyConfigured("DJANGO_LOG_LEVEL must not be missing.")
    if not isinstance(raw, str):
        raise ImproperlyConfigured("DJANGO_LOG_LEVEL must be a string.")
    stripped = raw.strip()
    if not stripped:
        raise ImproperlyConfigured("DJANGO_LOG_LEVEL must not be blank.")
    upper = stripped.upper()
    if upper not in _VALID_LOG_LEVELS:
        raise ImproperlyConfigured(
            f"DJANGO_LOG_LEVEL must be one of "
            f"{', '.join(sorted(_VALID_LOG_LEVELS))}, "
            f"got {stripped!r}."
        )
    return upper
