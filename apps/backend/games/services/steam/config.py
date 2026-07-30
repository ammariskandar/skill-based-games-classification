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

    def __post_init__(self) -> None:
        """Validate field values at construction time."""
        # API key: None or a string (client normalises blank to absent at
        # request time; factory also strips before construction).
        if self.api_key is not None and not isinstance(self.api_key, str):
            raise TypeError("api_key must be a string or None.")

        # Timeouts.
        if not isinstance(self.connect_timeout, (int, float)):
            raise TypeError("connect_timeout must be a number.")
        if self.connect_timeout <= 0:
            raise ValueError("connect_timeout must be > 0.")
        if self.connect_timeout > 30:
            raise ValueError("connect_timeout must be ≤ 30.")

        if not isinstance(self.read_timeout, (int, float)):
            raise TypeError("read_timeout must be a number.")
        if self.read_timeout <= 0:
            raise ValueError("read_timeout must be > 0.")
        if self.read_timeout > 60:
            raise ValueError("read_timeout must be ≤ 60.")

        # Retries.
        if not isinstance(self.max_retries, int):
            raise TypeError("max_retries must be an integer.")
        if self.max_retries < 0 or self.max_retries > 3:
            raise ValueError("max_retries must be 0–3.")

        if not isinstance(self.retry_backoff, (int, float)):
            raise TypeError("retry_backoff must be a number.")
        if self.retry_backoff < 0:
            raise ValueError("retry_backoff must be ≥ 0.")

        # Response size.
        if not isinstance(self.max_response_bytes, int):
            raise TypeError("max_response_bytes must be an integer.")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be > 0.")

    def __repr__(self) -> str:
        """Safe repr — never includes the API key."""
        key_status = "present" if self.api_key else "absent"
        return (
            f"SteamClientConfig("
            f"api_key={key_status}, "
            f"connect_timeout={self.connect_timeout}, "
            f"read_timeout={self.read_timeout}, "
            f"max_retries={self.max_retries}, "
            f"retry_backoff={self.retry_backoff}, "
            f"max_response_bytes={self.max_response_bytes}, "
            f"cdn_allowed_hosts={list(self.cdn_allowed_hosts)!r})"
        )


__all__ = ["SteamClientConfig"]
