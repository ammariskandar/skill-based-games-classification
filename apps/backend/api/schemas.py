"""
Shared API schemas — SBGC-38.

Request/response contracts, error envelope definitions, and validation
policies shared across all API version routers.
"""

from ninja import Schema
from pydantic import ConfigDict, Field

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
    details: list[ApiErrorDetail] = Field(default_factory=list)


class ApiErrorResponse(Schema):
    """Top-level error response envelope."""

    error: ApiError
