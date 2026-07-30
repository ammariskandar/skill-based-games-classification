"""
Steam service error taxonomy — SBGC-42.

Service-specific exceptions independent from Django Ninja's error handling.
Every exception carries safe public information only — no API key, request URL,
raw response body, or upstream HTML.
"""

from __future__ import annotations


class SteamError(Exception):
    """Base exception for all Steam service errors."""

    def __init__(self, message: str, *, code: str = "STEAM_ERROR") -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class SteamConfigurationError(SteamError):
    """Invalid or missing client configuration."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STEAM_CONFIGURATION_ERROR")


# -- Request-level errors -----------------------------------------------------


class SteamRequestError(SteamError):
    """Network-level failure before a response was received."""

    def __init__(self, message: str, *, code: str = "STEAM_REQUEST_ERROR") -> None:
        super().__init__(message, code=code)


class SteamConnectionError(SteamRequestError):
    """DNS, connection-refused, or TLS failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STEAM_CONNECTION_ERROR")


class SteamTimeoutError(SteamRequestError):
    """Connect or read timeout."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STEAM_TIMEOUT_ERROR")


class SteamRedirectError(SteamRequestError):
    """Unexpected 3xx response — redirects are never followed."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        self.status = status
        super().__init__(message, code="STEAM_REDIRECT_ERROR")


# -- Response-level errors ----------------------------------------------------


class SteamResponseError(SteamError):
    """A response was received but could not be processed."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "STEAM_RESPONSE_ERROR",
        status: int | None = None,
    ) -> None:
        self.status = status
        super().__init__(message, code=code)


class SteamAuthenticationError(SteamResponseError):
    """401 or 403 — invalid or insufficient API key."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message, code="STEAM_AUTHENTICATION_ERROR", status=status)


class SteamRateLimitedError(SteamResponseError):
    """429 — too many requests."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, code="STEAM_RATE_LIMITED", status=status)


class SteamNotFoundError(SteamResponseError):
    """404 — resource not found."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message, code="STEAM_NOT_FOUND", status=status)


class SteamUpstreamError(SteamResponseError):
    """5xx or unmapped 4xx from Steam."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message, code="STEAM_UPSTREAM_ERROR", status=status)


class SteamInvalidResponseError(SteamResponseError):
    """Invalid content-type, malformed JSON, or unexpected root type."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message, code="STEAM_INVALID_RESPONSE", status=status)


class SteamResponseTooLargeError(SteamError):
    """Response body exceeded the configured size limit."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STEAM_RESPONSE_TOO_LARGE")


__all__ = [
    "SteamError",
    "SteamConfigurationError",
    "SteamRequestError",
    "SteamConnectionError",
    "SteamTimeoutError",
    "SteamRedirectError",
    "SteamResponseError",
    "SteamAuthenticationError",
    "SteamRateLimitedError",
    "SteamNotFoundError",
    "SteamUpstreamError",
    "SteamInvalidResponseError",
    "SteamResponseTooLargeError",
]
