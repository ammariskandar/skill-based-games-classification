"""
Steam endpoint adapter errors — SBGC-53.

Typed exceptions for structured response validation failures.
Preserves transport exceptions — never wraps them.
"""

from __future__ import annotations


class SteamAdapterError(Exception):
    """Base exception for Steam endpoint adapter failures."""

    def __init__(self, message: str, *, code: str = "STEAM_ADAPTER_ERROR") -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class SteamMalformedPayloadError(SteamAdapterError):
    """Response structure did not match the expected schema."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STEAM_MALFORMED_PAYLOAD")


class SteamMissingRequiredFieldError(SteamAdapterError):
    """A required field was absent or blank in an otherwise valid response."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STEAM_MISSING_REQUIRED_FIELD")
