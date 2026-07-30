"""
Steam service configuration — SBGC-42.

Immutable configuration for the synchronous Steam HTTP client.
Never contains a real API key in committed code.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SteamClientConfig:
    """Immutable configuration for ``SteamClient``."""

    # -- API key ---------------------------------------------------------------

    api_key: str | None = None
    """Steam Web API key.  Optional at construction; required only when
    ``requires_api_key=True`` is passed to a request method."""

    # -- Trusted origins -------------------------------------------------------

    api_origin: str = "https://api.steampowered.com"
    store_origin: str = "https://store.steampowered.com"

    # -- Timeouts (seconds) ----------------------------------------------------

    connect_timeout: float = 3.05
    """Connection timeout in seconds.  Must be > 0 and ≤ 30."""

    read_timeout: float = 10.0
    """Read timeout in seconds.  Must be > 0 and ≤ 60."""

    # -- Retry -----------------------------------------------------------------

    max_retries: int = 2
    """Maximum retry count for idempotent requests (0–3)."""

    retry_backoff: float = 0.25
    """Backoff factor for urllib3 Retry (seconds)."""

    # -- Response-size limit ---------------------------------------------------

    max_response_bytes: int = 2_097_152  # 2 MiB
    """Maximum response body size in bytes before ``SteamResponseTooLargeError``."""

    # -- CDN allowlist ---------------------------------------------------------

    cdn_allowed_hosts: Collection[str] = field(default_factory=tuple)
    """Exact CDN hostnames permitted for ``validate_steam_cdn_url()``.
    Empty means all CDN URLs are rejected until configured."""


__all__ = ["SteamClientConfig"]
