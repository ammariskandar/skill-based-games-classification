"""
Steam CDN URL validation — SBGC-42.

Pure function for validating Steam CDN image URLs against a trusted host allowlist.
Never downloads, caches, proxies, or persists image binaries.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Collection
from urllib.parse import urlparse

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
    """Raise ``ValueError`` if *hostname* is localhost or an IP literal."""
    if hostname in ("localhost", "localhost.localdomain"):
        raise ValueError("CDN URL must not use localhost.")
    # Reject any IP literal (IPv4, IPv6, IPv4-mapped, etc.).
    try:
        ipaddress.ip_address(hostname)
        raise ValueError("CDN URL must not use an IP literal.")
    except ValueError:
        pass  # not an IP address — proceed


__all__ = ["validate_steam_cdn_url"]
