"""
Steam service configuration — SBGC-42 / SBGC-168.

Immutable configuration for the synchronous Steam HTTP client.
Never contains a real API key in committed code.

SBGC-168 changes:
- Origins moved to games.services.steam.constants (immutable code constants).
- Added retry_sleep_max_seconds (caps backoff_max and retry_after_max).
- Added maximum_attempts and configured_operation_budget_seconds.
- Strengthened validation: NaN, infinity, and booleans are rejected.
"""

from __future__ import annotations

import math
from collections.abc import Collection
from dataclasses import dataclass, field

_MAX_CONNECT_TIMEOUT = 30.0
_MAX_READ_TIMEOUT = 60.0
_MAX_RETRY_SLEEP = 10
_MAX_OPERATION_BUDGET = 120.0


def _is_finite_float(value: object) -> bool:
    """True if *value* is a finite float or int, not bool, not NaN/inf."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _is_strict_int(value: object) -> bool:
    """True if *value* is an int, not bool."""
    if isinstance(value, bool):
        return False
    return isinstance(value, int)


@dataclass(frozen=True)
class SteamClientConfig:
    """Immutable configuration for ``SteamClient``."""

    # -- API key ---------------------------------------------------------------

    api_key: str | None = None
    """Steam Web API key.  Optional at construction; required only when
    ``requires_api_key=True`` is passed to a request method."""

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

    retry_sleep_max_seconds: int = 5
    """Ceiling for backoff_max and retry_after_max (0–10).  Integer —
    urllib3 ``retry_after_max`` is typed ``int`` and ``backoff_max``
    accepts ``float``, so an integer satisfies both contracts."""

    # -- Response-size limit ---------------------------------------------------

    max_response_bytes: int = 2_097_152  # 2 MiB
    """Maximum response body size in bytes before ``SteamResponseTooLargeError``."""

    # -- CDN allowlist ---------------------------------------------------------

    cdn_allowed_hosts: Collection[str] = field(default_factory=tuple)
    """Exact CDN hostnames permitted for ``validate_steam_cdn_url()``.
    Empty means all CDN URLs are rejected until configured."""

    # -- Derived ---------------------------------------------------------------

    @property
    def maximum_attempts(self) -> int:
        """1 + max_retries (the total number of request attempts)."""
        return 1 + self.max_retries

    @property
    def configured_operation_budget_seconds(self) -> float:
        """
        Configured worst-case timeout/sleep budget in seconds.

        = maximum_attempts * (connect_timeout + read_timeout)
          + max_retries * retry_sleep_max_seconds

        This is a budget ceiling, not a strict wall-clock deadline.
        DNS, TLS, scheduling, and library overhead can add elapsed time.
        """
        return (
            self.maximum_attempts * (self.connect_timeout + self.read_timeout)
            + self.max_retries * self.retry_sleep_max_seconds
        )

    def __post_init__(self) -> None:
        """Validate field values at construction time."""
        # API key: None or a string.
        if self.api_key is not None and not isinstance(self.api_key, str):
            raise TypeError("api_key must be a string or None.")

        # Timeouts — must be finite floats, not bool/NaN/inf.
        if not _is_finite_float(self.connect_timeout):
            raise TypeError("connect_timeout must be a finite number.")
        if self.connect_timeout <= 0:
            raise ValueError("connect_timeout must be > 0.")
        if self.connect_timeout > _MAX_CONNECT_TIMEOUT:
            raise ValueError(f"connect_timeout must be ≤ {_MAX_CONNECT_TIMEOUT}.")

        if not _is_finite_float(self.read_timeout):
            raise TypeError("read_timeout must be a finite number.")
        if self.read_timeout <= 0:
            raise ValueError("read_timeout must be > 0.")
        if self.read_timeout > _MAX_READ_TIMEOUT:
            raise ValueError(f"read_timeout must be ≤ {_MAX_READ_TIMEOUT}.")

        # Retries — strictly int, 0–3.
        if not isinstance(self.max_retries, int) or isinstance(self.max_retries, bool):
            raise TypeError("max_retries must be an integer.")
        if self.max_retries < 0 or self.max_retries > 3:
            raise ValueError("max_retries must be 0–3.")

        # Backoff — finite float, ≥ 0.
        if not _is_finite_float(self.retry_backoff):
            raise TypeError("retry_backoff must be a finite number.")
        if self.retry_backoff < 0:
            raise ValueError("retry_backoff must be ≥ 0.")

        # Sleep cap — strict int, 0–10 (urllib3 retry_after_max is typed int).
        if not _is_strict_int(self.retry_sleep_max_seconds):
            raise TypeError("retry_sleep_max_seconds must be an integer.")
        if self.retry_sleep_max_seconds < 0:
            raise ValueError("retry_sleep_max_seconds must be ≥ 0.")
        if self.retry_sleep_max_seconds > _MAX_RETRY_SLEEP:
            raise ValueError(f"retry_sleep_max_seconds must be ≤ {_MAX_RETRY_SLEEP}.")

        # Response size — strictly int, > 0.
        if not isinstance(self.max_response_bytes, int) or isinstance(
            self.max_response_bytes, bool
        ):
            raise TypeError("max_response_bytes must be an integer.")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be > 0.")

        # Operation budget.
        budget = self.configured_operation_budget_seconds
        if budget > _MAX_OPERATION_BUDGET:
            raise ValueError(
                f"Configured operation budget ({budget:.1f}s) exceeds "
                f"maximum ({_MAX_OPERATION_BUDGET}s)."
            )

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
            f"retry_sleep_max_seconds={self.retry_sleep_max_seconds}, "
            f"max_response_bytes={self.max_response_bytes}, "
            f"cdn_allowed_hosts={list(self.cdn_allowed_hosts)!r})"
        )


__all__ = ["SteamClientConfig"]
