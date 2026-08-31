"""
API error infrastructure — SBGC-38.

Provides:

- ApiException           project-level exception with safe public representation.
- build_error_response   serialises any handled error through the shared schema.
- register_handlers      attaches all exception handlers to a NinjaAPI instance.
"""

from __future__ import annotations

import logging
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse
from games.errors import ErrorCode
from ninja import NinjaAPI
from ninja.errors import (
    AuthenticationError,
    AuthorizationError,
    HttpError,
    ValidationError,
)
from ninja.responses import codes_4xx, codes_5xx

from api.schemas import ApiError, ApiErrorDetail, ApiErrorResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAPI error-response declarations
# ---------------------------------------------------------------------------

# Django Ninja 1.6.2 grouped status-code sets — frozenset objects usable as
# dict keys in response declarations.  Each key expands to every concrete
# status code in the group when Ninja generates the OpenAPI schema.
STANDARD_ERROR_RESPONSES = {
    codes_4xx: ApiErrorResponse,
    codes_5xx: ApiErrorResponse,
}

# ---------------------------------------------------------------------------
# Project exception
# ---------------------------------------------------------------------------


class ApiException(Exception):
    """
    Deliberately raised project API error.

    Attributes are constrained to produce a safe public error response.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[ApiErrorDetail] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------


def _response(
    status: int, code: str, message: str, details: Any = None
) -> HttpResponse:
    """Build a validated error HttpResponse from safe primitives."""
    if details is not None and not isinstance(details, list):
        details = list(details)
    error_body = ApiErrorResponse(
        error=ApiError(
            code=code,
            message=message,
            details=details or [],
        )
    )
    return HttpResponse(
        content=error_body.model_dump_json(),
        status=status,
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------


# -- ValidationError (raised by Ninja when request bodies fail schema checks) --

_VALIDATION_SAFE_FIELDS = frozenset({"loc", "msg", "type"})


def _sanitize_validation_errors(
    raw_errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep only location, message, and type from each Pydantic error."""
    safe: list[dict[str, Any]] = []
    for err in raw_errors:
        entry: dict[str, Any] = {}
        for field in ("loc", "msg", "type"):
            if field in err:
                entry[field] = err[field]
        # Normalise "msg" → "message" and "loc" → "location" for the schema
        if "loc" in entry:
            entry["location"] = entry.pop("loc")
        if "msg" in entry:
            entry["message"] = entry.pop("msg")
        if entry:
            safe.append(entry)
    return safe


def validation_error_handler(
    request: HttpRequest, exc: ValidationError
) -> HttpResponse:
    details = _sanitize_validation_errors(exc.errors)
    return _response(
        status=422,
        code=ErrorCode.VALIDATION_ERROR.value,
        message="Request validation failed.",
        details=details,
    )


# -- Authentication / Authorization --


def authentication_error_handler(
    request: HttpRequest, exc: AuthenticationError
) -> HttpResponse:
    return _response(
        status=401,
        code=ErrorCode.AUTHENTICATION_ERROR.value,
        message="Authentication credentials were not provided or are invalid.",
    )


def authorization_error_handler(
    request: HttpRequest, exc: AuthorizationError
) -> HttpResponse:
    return _response(
        status=403,
        code=ErrorCode.AUTHORIZATION_ERROR.value,
        message="You do not have permission to perform this action.",
    )


# -- Http404 --


def http404_handler(request: HttpRequest, exc: Http404) -> HttpResponse:
    return _response(
        status=404,
        code=ErrorCode.NOT_FOUND.value,
        message="The requested resource was not found.",
    )


# -- HttpError (deliberate HTTP-level error from endpoint code) --

_HTTP_ERROR_MAP: dict[int, str] = {
    400: ErrorCode.BAD_REQUEST.value,
    401: ErrorCode.AUTHENTICATION_ERROR.value,
    403: ErrorCode.AUTHORIZATION_ERROR.value,
    404: ErrorCode.NOT_FOUND.value,
    405: ErrorCode.METHOD_NOT_ALLOWED.value,
    409: ErrorCode.CONFLICT.value,
    422: ErrorCode.VALIDATION_ERROR.value,
    429: ErrorCode.RATE_LIMITED.value,
    503: ErrorCode.SERVICE_UNAVAILABLE.value,
}


def http_error_handler(request: HttpRequest, exc: HttpError) -> HttpResponse:
    status = exc.status_code
    code = _HTTP_ERROR_MAP.get(status, ErrorCode.HTTP_ERROR.value)
    return _response(status=status, code=code, message=str(exc))


# -- Unexpected Exception --


def _is_framework_validation_error(exc: Exception) -> bool:
    """
    Detect Django-Ninja's internal 'Invalid HTTP method' ValidationError
    when an unsupported method hits a router.

    Django Ninja 1.6.2 raises ninja.errors.ValidationError with a flat
    error list containing a message like "Invalid HTTP method".
    """
    if isinstance(exc, ValidationError):
        raw = exc.errors
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and "Invalid HTTP method" in str(
                    item.get("msg", "")
                ):
                    return True
    return False


def unexpected_exception_handler(request: HttpRequest, exc: Exception) -> HttpResponse:
    logger.error(
        "Unhandled API exception",
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={"path": getattr(request, "path", "<unknown>")},
    )
    return _response(
        status=500,
        code=ErrorCode.INTERNAL_SERVER_ERROR.value,
        message="An unexpected error occurred.",
    )


# -- Project ApiException --


def api_exception_handler(request: HttpRequest, exc: ApiException) -> HttpResponse:
    return _response(
        status=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_handlers(api: NinjaAPI) -> None:
    """
    Attach all standard exception handlers to *api*.

    Call once per NinjaAPI instance after construction.
    """
    # Django Ninja stubs type add_exception_handler with a restrictive generic
    # that does not match our handler callbacks.  Use a single registered
    # helper to own the framework-boundary cast.
    _register = _ninja_handler(api.add_exception_handler)  # pyright: ignore[reportArgumentType]
    _register(ApiException, api_exception_handler)
    _register(ValidationError, validation_error_handler)
    _register(AuthenticationError, authentication_error_handler)
    _register(AuthorizationError, authorization_error_handler)
    _register(HttpError, http_error_handler)
    _register(Http404, http404_handler)
    _register(Exception, unexpected_exception_handler)


def _ninja_handler(registrar: object):  # noqa: ANN202
    """Return *registrar* as a callable for handler registration.

    Django Ninja stubs' ``ExcHandler`` generic does not match our handler
    signatures.  One cast here avoids repeated per-call suppressions.
    """
    from collections.abc import Callable
    from typing import cast

    return cast(Callable[..., None], registrar)
