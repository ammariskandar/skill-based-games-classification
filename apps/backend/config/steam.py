"""
Steam environment-configuration adapter — SBGC-42.

Reads raw Django settings (supplied by environment-specific settings
modules) and produces a validated ``SteamClientConfig``.  Never makes
a network request or instantiates a ``SteamClient``.

Validation is delegated to ``SteamClientConfig.__post_init__`` to keep
a single validation path.

Parsing semantics
-----------------

- **Missing or blank** value → documented default.
- **Malformed numeric** value → ``ImproperlyConfigured`` (NaN, Infinity,
  and non-numeric strings are all rejected).
- **Out-of-range** value → ``ImproperlyConfigured``
  (zero, negative, or exceeding the documented maximum).
- **CDN host entries** are validated as exact DNS hostnames: no scheme,
  path, query, fragment, credentials, port, wildcard, IP literal, or
  localhost.  Entries are case-normalised and deduplicated.

Every configuration failure at the Django boundary raises
``ImproperlyConfigured``.  ``SteamClientConfig`` may raise ``ValueError``
only when instantiated directly outside this factory.
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection

from django.core.exceptions import ImproperlyConfigured
from games.services.steam.config import SteamClientConfig

# Sentinel for "not provided" keyword arguments — must be defined before
# the function signature that uses it as a default value.
_sentinel: object = object()


def steam_client_config_from_settings(
    *,
    steam_web_api_key: str | None = _sentinel,  # type: ignore[valid-type]
    steam_connect_timeout_seconds: str | None = _sentinel,  # type: ignore[valid-type]
    steam_read_timeout_seconds: str | None = _sentinel,  # type: ignore[valid-type]
    steam_max_retries: str | None = _sentinel,  # type: ignore[valid-type]
    steam_retry_backoff_seconds: str | None = _sentinel,  # type: ignore[valid-type]
    steam_max_response_bytes: str | None = _sentinel,  # type: ignore[valid-type]
    steam_cdn_allowed_hosts: str | None = _sentinel,  # type: ignore[valid-type]
    steam_retry_sleep_max_seconds: str | None = _sentinel,  # type: ignore[valid-type]
) -> SteamClientConfig:
    """
    Build a validated ``SteamClientConfig`` from Django settings.

    Reads the following settings (all strings from the environment):

    * ``STEAM_WEB_API_KEY``
    * ``STEAM_CONNECT_TIMEOUT_SECONDS``
    * ``STEAM_READ_TIMEOUT_SECONDS``
    * ``STEAM_MAX_RETRIES``
    * ``STEAM_RETRY_BACKOFF_SECONDS``
    * ``STEAM_MAX_RESPONSE_BYTES``
    * ``STEAM_CDN_ALLOWED_HOSTS``

    Keyword arguments override the corresponding Django setting and are
    intended for testing.  Callers in production code should rely on
    the default (read from settings).

    Returns:
        A fully validated ``SteamClientConfig`` instance.

    Raises:
        ImproperlyConfigured: Any malformed numeric value, out-of-range
            value, or invalid CDN host entry.  Every configuration failure
            at the Django boundary raises this exception.
    """
    from django.conf import settings

    # -- API key ---------------------------------------------------------------
    api_key_raw = _resolve(
        steam_web_api_key,
        getattr(settings, "STEAM_WEB_API_KEY", ""),
    )
    api_key: str | None = _normalise_api_key(api_key_raw)

    # -- Timeouts --------------------------------------------------------------
    connect = _resolve(
        steam_connect_timeout_seconds,
        getattr(settings, "STEAM_CONNECT_TIMEOUT_SECONDS", "3.05"),
    )
    connect_timeout = _parse_float(
        connect, label="STEAM_CONNECT_TIMEOUT_SECONDS", default=3.05
    )

    read = _resolve(
        steam_read_timeout_seconds,
        getattr(settings, "STEAM_READ_TIMEOUT_SECONDS", "10"),
    )
    read_timeout = _parse_float(read, label="STEAM_READ_TIMEOUT_SECONDS", default=10.0)

    # -- Retry -----------------------------------------------------------------
    retries = _resolve(
        steam_max_retries,
        getattr(settings, "STEAM_MAX_RETRIES", "2"),
    )
    max_retries = _parse_int(retries, label="STEAM_MAX_RETRIES", default=2)

    backoff = _resolve(
        steam_retry_backoff_seconds,
        getattr(settings, "STEAM_RETRY_BACKOFF_SECONDS", "0.25"),
    )
    retry_backoff = _parse_float(
        backoff, label="STEAM_RETRY_BACKOFF_SECONDS", default=0.25
    )

    # -- Response size ---------------------------------------------------------
    size = _resolve(
        steam_max_response_bytes,
        getattr(settings, "STEAM_MAX_RESPONSE_BYTES", "2097152"),
    )
    max_response_bytes = _parse_int(
        size, label="STEAM_MAX_RESPONSE_BYTES", default=2_097_152
    )

    # -- CDN hosts -------------------------------------------------------------
    hosts = _resolve(
        steam_cdn_allowed_hosts,
        getattr(settings, "STEAM_CDN_ALLOWED_HOSTS", ""),
    )
    cdn_allowed_hosts: Collection[str] = _parse_cdn_hosts(hosts)

    # -- Retry sleep cap ------------------------------------------------------
    sleep_raw = _resolve(
        steam_retry_sleep_max_seconds,
        getattr(settings, "STEAM_RETRY_SLEEP_MAX_SECONDS", "5.0"),
    )
    retry_sleep_max = _parse_float(
        sleep_raw, label="STEAM_RETRY_SLEEP_MAX_SECONDS", default=5.0
    )

    # -- Construct (validation via __post_init__) ------------------------------
    try:
        return SteamClientConfig(
            api_key=api_key,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            retry_sleep_max_seconds=retry_sleep_max,
            max_response_bytes=max_response_bytes,
            cdn_allowed_hosts=cdn_allowed_hosts,
        )
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(str(exc)) from exc


# ---------------------------------------------------------------------------
# Argument resolution
# ---------------------------------------------------------------------------


def _resolve(explicit: object, default: str) -> str:
    """Return *explicit* if it is not the sentinel, otherwise *default*."""
    if explicit is _sentinel:
        return default
    return explicit  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _normalise_api_key(raw: str | None) -> str | None:
    """Return a non-blank key or None."""
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped if stripped else None


def _parse_float(raw: str | None, *, label: str, default: float) -> float:
    """
    Parse *raw* as a finite float.

    Returns *default* when *raw* is absent or blank.
    Raises ``ImproperlyConfigured`` for non-numeric, NaN, or Infinity values.
    """
    if raw is None:
        return default
    stripped = raw.strip()
    if not stripped:
        return default
    try:
        value = float(stripped)
    except ValueError:
        raise ImproperlyConfigured(
            f"{label} must be a number, got {stripped!r}."
        ) from None
    if math.isnan(value):
        raise ImproperlyConfigured(f"{label} must not be NaN.")
    if math.isinf(value):
        raise ImproperlyConfigured(f"{label} must not be Infinity.")
    return value


def _parse_int(raw: str | None, *, label: str, default: int) -> int:
    """
    Parse *raw* as an integer.

    Returns *default* when *raw* is absent or blank.
    Raises ``ImproperlyConfigured`` for non-integer or float-looking values.
    """
    if raw is None:
        return default
    stripped = raw.strip()
    if not stripped:
        return default
    # Reject float-looking strings (e.g. "3.0") — integer-only.
    if "." in stripped:
        raise ImproperlyConfigured(f"{label} must be an integer, got {stripped!r}.")
    try:
        return int(stripped)
    except ValueError:
        raise ImproperlyConfigured(
            f"{label} must be an integer, got {stripped!r}."
        ) from None


# ---------------------------------------------------------------------------
# CDN hostname validation
# ---------------------------------------------------------------------------

# Per-label DNS validation: starts/ends alphanumeric, hyphens inside only,
# 1-63 characters per label.
_DNS_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")

_MAX_HOSTNAME_LENGTH = 253

_CDN_HOST_RESERVED = frozenset({"localhost", "localhost.localdomain"})


def _validate_cdn_host_entry(entry: str) -> None:
    """
    Validate a single CDN host entry.

    Raises ``ImproperlyConfigured`` for any violation.
    """
    if not isinstance(entry, str):
        raise ImproperlyConfigured("CDN host entry must be a string.")
    if not entry:
        raise ImproperlyConfigured("CDN host entry must not be blank.")

    # Scheme / URL forms.
    if "://" in entry:
        raise ImproperlyConfigured(
            "STEAM_CDN_ALLOWED_HOSTS must not contain URLs (scheme detected)."
        )
    if entry.startswith("//"):
        raise ImproperlyConfigured(
            "STEAM_CDN_ALLOWED_HOSTS must not contain protocol-relative URLs."
        )

    # Path / query / fragment.
    if "/" in entry:
        raise ImproperlyConfigured("STEAM_CDN_ALLOWED_HOSTS must not contain paths.")
    if "?" in entry or "#" in entry:
        raise ImproperlyConfigured(
            "STEAM_CDN_ALLOWED_HOSTS must not contain query strings or fragments."
        )

    # Credentials.
    if "@" in entry:
        raise ImproperlyConfigured(
            "STEAM_CDN_ALLOWED_HOSTS must not contain credentials."
        )

    # Port.
    if ":" in entry:
        raise ImproperlyConfigured("STEAM_CDN_ALLOWED_HOSTS must not contain a port.")

    # Wildcard.
    if "*" in entry:
        raise ImproperlyConfigured(
            "STEAM_CDN_ALLOWED_HOSTS must not contain a wildcard."
        )

    # Dot restrictions.
    if entry.startswith(".") or entry.endswith("."):
        raise ImproperlyConfigured(
            "STEAM_CDN_ALLOWED_HOSTS must not start or end with a dot."
        )
    if ".." in entry:
        raise ImproperlyConfigured(
            "STEAM_CDN_ALLOWED_HOSTS must not contain consecutive dots."
        )

    # Reserved hostnames.
    if entry.lower() in _CDN_HOST_RESERVED:
        raise ImproperlyConfigured(
            "STEAM_CDN_ALLOWED_HOSTS must not contain localhost."
        )

    # IP literal (IPv4 or IPv6).
    try:
        import ipaddress

        ipaddress.ip_address(entry)
        raise ImproperlyConfigured(
            "STEAM_CDN_ALLOWED_HOSTS must not contain IP literals."
        )
    except ValueError:
        pass  # not an IP address — proceed to DNS validation

    # DNS hostname length.
    if len(entry) > _MAX_HOSTNAME_LENGTH:
        raise ImproperlyConfigured(
            f"STEAM_CDN_ALLOWED_HOSTS entry exceeds {_MAX_HOSTNAME_LENGTH} characters."
        )

    # Per-label DNS validation.
    labels = entry.split(".")
    for label in labels:
        if not label:
            raise ImproperlyConfigured(
                "STEAM_CDN_ALLOWED_HOSTS must not contain empty labels."
            )
        if not _DNS_LABEL_RE.match(label):
            raise ImproperlyConfigured(
                "STEAM_CDN_ALLOWED_HOSTS contains a malformed host entry."
            )


def _parse_cdn_hosts(raw: str | None) -> tuple[str, ...]:
    """
    Parse comma-separated CDN hostnames, validate each entry, deduplicate.

    Returns a tuple of lower-cased, deduplicated, validated hostnames.
    An empty or blank *raw* value returns an empty tuple.

    Raises ``ImproperlyConfigured`` for any malformed entry.
    """
    if raw is None:
        return ()
    stripped = raw.strip()
    if not stripped:
        return ()
    entries = [h.strip() for h in stripped.split(",")]
    entries = [h for h in entries if h]  # remove blanks from e.g. trailing comma

    if not entries:
        return ()

    seen: set[str] = set()
    result: list[str] = []

    for entry in entries:
        _validate_cdn_host_entry(entry)
        lower = entry.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(lower)

    return tuple(result)
