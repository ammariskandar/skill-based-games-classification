"""
Shared API schemas — SBGC-38.

Request/response contracts, error envelope definitions, and validation
policies shared across all API version routers.
"""

from functools import cached_property

from ninja import Schema
from pydantic import ConfigDict

# ---------------------------------------------------------------------------
# Request conventions
# ---------------------------------------------------------------------------


class ApiRequestSchema(Schema):
    """
    Base request schema.

    Rejects unknown/extra fields so that misspelled or unsupported keys
    produce a clear validation error rather than being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Generic root-level responses
# ---------------------------------------------------------------------------


class ApiRootResponse(Schema):
    """GET /api/v1/ public root payload."""

    name: str
    version: str


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------


class ApiErrorDetail(Schema):
    """One validation or error detail entry."""

    location: list[str | int]
    message: str
    type: str


class ApiError(Schema):
    """Standardised machine-readable error body."""

    code: str
    message: str
    details: list[ApiErrorDetail]

    @cached_property
    def _default_details(self) -> list[ApiErrorDetail]:
        """
        Return a new empty list on every access so callers that modify
        `details` in-place do not mutate a shared mutable default.
        """
        return []

    @staticmethod
    def default_details() -> list[ApiErrorDetail]:
        return []


class ApiErrorResponse(Schema):
    """Top-level error response envelope."""

    error: ApiError
