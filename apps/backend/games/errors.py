"""
Canonical API error code registry — SBGC-100.

Single source of truth for every machine-readable error code the public
Django Ninja API can emit: the code string, its default HTTP status, its
category, where it is surfaced (route / page), an operator-facing
description, and a representative payload.

The codes below are the *actual* codes emitted by the registered exception
handlers (``api/errors.py``) and the domain endpoints.  They are the
contract — the registry documents them; it does not invent new ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    """Coarse grouping of error codes for operator triage."""

    PUBLIC_API = "Public API"
    VALIDATION = "Validation"
    INGESTION = "Ingestion & Sync"
    SYSTEM = "System & Security"


class ErrorCode(StrEnum):
    """Machine-readable error codes emitted by the public API envelope."""

    GAME_NOT_FOUND = "GAME_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    BAD_REQUEST = "BAD_REQUEST"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    CONFLICT = "CONFLICT"
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    EXPIRED_RESET_TOKEN = "EXPIRED_RESET_TOKEN"
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


@dataclass(frozen=True)
class ErrorMetadata:
    """Registry metadata for one canonical error code."""

    code: ErrorCode
    http_status: int
    category: ErrorCategory
    # Where the code is surfaced — concrete API routes (e.g.
    # "POST /api/v1/auth/signup"), a global layer (e.g. request validation), or
    # a frontend BFF proxy.  Rendered as the "API Route / Page" admin column.
    surfaced_at: str
    description: str
    sample_details: list[dict[str, Any]] | dict[str, Any]


ERROR_REGISTRY: dict[ErrorCode, ErrorMetadata] = {
    ErrorCode.GAME_NOT_FOUND: ErrorMetadata(
        code=ErrorCode.GAME_NOT_FOUND,
        http_status=404,
        category=ErrorCategory.PUBLIC_API,
        surfaced_at="Games API — /api/v1/games/…",
        description=(
            "Target game slug does not exist or is not publicly listable "
            "(draft, archived, non-game)."
        ),
        sample_details=[],
    ),
    ErrorCode.VALIDATION_ERROR: ErrorMetadata(
        code=ErrorCode.VALIDATION_ERROR,
        http_status=422,
        category=ErrorCategory.VALIDATION,
        surfaced_at="Global — all /api/v1/* requests",
        description=(
            "Request parameters or body payload failed Pydantic/Ninja "
            "validation constraints."
        ),
        sample_details=[
            {
                "location": ["query", "page"],
                "message": "Input should be greater than or equal to 1",
                "type": "greater_than_equal",
            }
        ],
    ),
    ErrorCode.AUTHENTICATION_ERROR: ErrorMetadata(
        code=ErrorCode.AUTHENTICATION_ERROR,
        http_status=401,
        category=ErrorCategory.SYSTEM,
        surfaced_at="Auth API — POST /api/v1/auth/login (and global auth gate)",
        description=("Authentication credentials were not provided or are invalid."),
        sample_details=[],
    ),
    ErrorCode.AUTHORIZATION_ERROR: ErrorMetadata(
        code=ErrorCode.AUTHORIZATION_ERROR,
        http_status=403,
        category=ErrorCategory.SYSTEM,
        surfaced_at="Global — protected /api/v1/* routes",
        description=(
            "The authenticated caller is not permitted to perform the requested action."
        ),
        sample_details=[],
    ),
    ErrorCode.NOT_FOUND: ErrorMetadata(
        code=ErrorCode.NOT_FOUND,
        http_status=404,
        category=ErrorCategory.PUBLIC_API,
        surfaced_at="Global — /api/v1/* catch-all + Django Http404",
        description=(
            "The requested resource does not exist at this route "
            "(generic 404, e.g. Django Http404)."
        ),
        sample_details=[],
    ),
    ErrorCode.BAD_REQUEST: ErrorMetadata(
        code=ErrorCode.BAD_REQUEST,
        http_status=400,
        category=ErrorCategory.VALIDATION,
        surfaced_at="Auth API — /api/v1/auth/* honeypot & reCAPTCHA guards",
        description=(
            "The request is malformed or semantically invalid (for example "
            "an invalid Steam App ID or an invalid refresh target)."
        ),
        sample_details=[],
    ),
    ErrorCode.METHOD_NOT_ALLOWED: ErrorMetadata(
        code=ErrorCode.METHOD_NOT_ALLOWED,
        http_status=405,
        category=ErrorCategory.PUBLIC_API,
        surfaced_at="Global — /api/v1/* wrong HTTP method",
        description=("The HTTP method is not supported for this route."),
        sample_details=[],
    ),
    ErrorCode.CONFLICT: ErrorMetadata(
        code=ErrorCode.CONFLICT,
        http_status=409,
        category=ErrorCategory.INGESTION,
        surfaced_at="Auth API — POST /api/v1/auth/signup (duplicate username/email)",
        description=("The request conflicts with the current state of the resource."),
        sample_details=[],
    ),
    ErrorCode.EMAIL_NOT_VERIFIED: ErrorMetadata(
        code=ErrorCode.EMAIL_NOT_VERIFIED,
        http_status=400,
        category=ErrorCategory.VALIDATION,
        surfaced_at="Auth API — POST /api/v1/auth/signup",
        description=(
            "The pre-registration email challenge is missing, expired, or "
            "has not been confirmed through the emailed verification link."
        ),
        sample_details=[],
    ),
    ErrorCode.EXPIRED_RESET_TOKEN: ErrorMetadata(
        code=ErrorCode.EXPIRED_RESET_TOKEN,
        http_status=400,
        category=ErrorCategory.VALIDATION,
        surfaced_at="Auth API — POST /api/v1/auth/reset-password-confirm",
        description=(
            "The one-chance password-reset session nonce is missing, expired, "
            "or has already been consumed (reload/back-navigation after claim "
            "or reuse of a burned token)."
        ),
        sample_details=[],
    ),
    ErrorCode.RATE_LIMITED: ErrorMetadata(
        code=ErrorCode.RATE_LIMITED,
        http_status=429,
        category=ErrorCategory.INGESTION,
        surfaced_at=(
            "Auth API — /api/v1/auth/login, /verify-email-request, "
            "/forgot-username, /forgot-password; Steam import/refresh"
        ),
        description=(
            "A rate limit was encountered (for example Steam API throttling "
            "during import or metadata refresh)."
        ),
        sample_details=[],
    ),
    ErrorCode.SERVICE_UNAVAILABLE: ErrorMetadata(
        code=ErrorCode.SERVICE_UNAVAILABLE,
        http_status=503,
        category=ErrorCategory.INGESTION,
        surfaced_at="Frontend BFF — /api/auth/* proxies; Steam import/refresh",
        description=(
            "An upstream dependency (for example the Steam API) is "
            "temporarily unavailable."
        ),
        sample_details=[],
    ),
    ErrorCode.HTTP_ERROR: ErrorMetadata(
        code=ErrorCode.HTTP_ERROR,
        http_status=400,
        category=ErrorCategory.SYSTEM,
        surfaced_at="Global — unhandled HttpError fallback (/api/v1/*)",
        description=(
            "Generic fallback code for an HttpError whose status code is "
            "not mapped to a specific canonical code."
        ),
        sample_details=[],
    ),
    ErrorCode.INTERNAL_SERVER_ERROR: ErrorMetadata(
        code=ErrorCode.INTERNAL_SERVER_ERROR,
        http_status=500,
        category=ErrorCategory.SYSTEM,
        surfaced_at="Global — /api/v1/* unhandled exceptions",
        description=(
            "Unhandled backend exception. Internal traceback is suppressed "
            "in responses and logged server-side."
        ),
        sample_details=[],
    ),
}
