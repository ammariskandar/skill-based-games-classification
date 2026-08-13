"""
Steam image URL validation — SBGC-42 / SBGC-55.

Pure functions for validating Steam image URLs.  Never downloads, caches,
proxies, or persists image binaries.

Two distinct policies:

- ``validate_steam_image_url`` — canonical upstream payload validation
  for persisting header-image metadata (SBGC-55).  Structural only: HTTPS,
  no credentials, no IP literals/localhost/numeric hosts.
- ``validate_steam_cdn_url`` — strict trusted-host gate for any future
  fetch/proxy/download of image binaries (SBGC-42).  Requires an explicit
  allowlist; an empty allowlist rejects every URL.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Collection
from urllib.parse import urlparse

from games.services.steam.adapters import SteamMalformedPayloadError

# Reject numeric-only host representations (decimal, hex, octal IP forms).
_NUMERIC_HOST_RE = re.compile(r"^(?:0[xX][0-9a-fA-F]+|0[0-7]+|[0-9]+)$")

# ---------------------------------------------------------------------------
# Canonical upstream image-URL validation (metadata persistence)
# ---------------------------------------------------------------------------


def validate_steam_image_url(value: object) -> str | None:
    """Validate a Steam header-image URL from an upstream payload.

    Strict SBGC-53 malformed-metadata semantics:

    - ``None`` → ``None`` (no upstream image).
    - blank/whitespace string → ``None`` (absent field equivalent).
    - valid HTTPS URL → returned as-is (outer whitespace stripped).
    - **anything else** — non-string values and nonblank malformed
      strings (non-HTTPS scheme, credentials, missing hostname, custom
      port, IP literal, numeric host, localhost) — raises
      ``SteamMalformedPayloadError``.

    ``None`` therefore means exactly one thing: the upstream payload did
    not provide a usable image field.  Malformed nonblank upstream
    metadata is an error and is never silently normalized to absence.

    Never performs network access — structural validation only.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise SteamMalformedPayloadError(
            f"Steam image URL must be a string or null, got {type(value).__name__}."
        )

    v = value.strip()
    if not v:
        return None

    parsed = urlparse(v)

    # Scheme — HTTPS only (case-insensitive).
    if parsed.scheme.lower() != "https":
        raise SteamMalformedPayloadError(
            f"Steam image URL must use HTTPS, got {parsed.scheme!r}."
        )

    # Credentials — userinfo of any kind is rejected.
    if parsed.username or parsed.password or "@" in parsed.netloc:
        raise SteamMalformedPayloadError(
            "Steam image URL must not contain credentials."
        )

    # Hostname — required, and must be a public non-IP host.
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise SteamMalformedPayloadError(
            "Steam image URL must have a nonempty hostname."
        )

    # Custom ports are not part of the Steam image URL contract.
    if parsed.port is not None:
        raise SteamMalformedPayloadError(
            "Steam image URL must not contain a custom port."
        )

    try:
        _reject_non_public_host(hostname)
    except ValueError as exc:
        raise SteamMalformedPayloadError(
            f"Steam image URL host is not permitted: {exc}"
        ) from exc

    return v


# ---------------------------------------------------------------------------
# Strict trusted-host CDN gate (future binary fetch/proxy work)
# ---------------------------------------------------------------------------


def validate_steam_cdn_url(
    value: str,
    *,
    allowed_hosts: Collection[str],
) -> str:
    """
    Validate *value* as a trusted Steam CDN URL.

    Args:
        value: Raw URL string to validate.
        allowed_hosts: Exact hostnames permitted (e.g.
            ``{"cdn.cloudflare.steamstatic.com"}``).
            An empty collection means all URLs are rejected.

    Returns:
        The normalised URL string (scheme and hostname lower-cased).

    Raises:
        ValueError: For any violation of the CDN URL contract.
    """
    if not isinstance(value, str):
        raise ValueError("CDN URL must be a string.")
    if not value.strip():
        raise ValueError("CDN URL must not be blank.")

    # -- Character safety -------------------------------------------------------
    if re.search(r"[\x00-\x1f\x7f]", value):
        raise ValueError("CDN URL must not contain control characters.")

    # -- Parse ------------------------------------------------------------------
    parsed = urlparse(value)

    # Scheme.
    if parsed.scheme.lower() != "https":
        raise ValueError("CDN URL must use HTTPS.")
    if not parsed.scheme:
        raise ValueError("CDN URL must have an explicit scheme.")

    # Hostname (netloc without port/credentials).
    hostname = (parsed.hostname or "").lower()

    if not hostname:
        raise ValueError("CDN URL must have a nonempty hostname.")
    if "@" in parsed.netloc:
        raise ValueError("CDN URL must not contain credentials.")
    if parsed.port is not None:
        raise ValueError("CDN URL must not contain a custom port.")

    # Reject local / private / loopback / IP-literal destinations.
    _reject_non_public_host(hostname)

    # -- Allowlist check --------------------------------------------------------
    allowed = {h.strip().lower() for h in allowed_hosts if h.strip()}
    if not allowed:
        raise ValueError("CDN URL rejected — the CDN host allowlist is empty.")
    if hostname not in allowed:
        raise ValueError("CDN URL rejected — host is not in the trusted CDN allowlist.")

    # -- Path -------------------------------------------------------------------
    if not parsed.path or parsed.path == "/":
        raise ValueError("CDN URL must have a nonempty path.")

    # -- Fragment ---------------------------------------------------------------
    if parsed.fragment:
        raise ValueError("CDN URL must not contain a fragment.")

    # -- Rebuild normalised URL -------------------------------------------------
    return _rebuild_url(parsed, hostname)


def _rebuild_url(parsed, hostname: str) -> str:
    """Build a normalised URL string from parsed components."""
    result = f"https://{hostname}{parsed.path}"
    if parsed.query:
        result += f"?{parsed.query}"
    return result


def _reject_non_public_host(hostname: str) -> None:
    """Raise ``ValueError`` if *hostname* is localhost, a numeric-only
    host (decimal/hex/octal IP representation), or an IP literal."""
    if hostname in ("localhost", "localhost.localdomain"):
        raise ValueError("CDN URL must not use localhost.")
    # Reject numeric-only hosts before IP-literal check — these are
    # ambiguous decimal/hex/octal IP representations (e.g. 2130706433,
    # 0x7f000001, 017700000001) that ipaddress does not recognise.
    if _NUMERIC_HOST_RE.match(hostname):
        raise ValueError("CDN URL must not use a numeric host.")
    # Reject any IP literal (IPv4, IPv6, IPv4-mapped, etc.).
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass  # not an IP address — proceed
    else:
        raise ValueError("CDN URL must not use an IP literal.")


__all__ = ["validate_steam_image_url", "validate_steam_cdn_url"]
