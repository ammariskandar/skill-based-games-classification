"""
Game suggestion API router — SBGC-240.

A single authenticated write path that emails a user's game suggestion to the
operator.  The HTTP layer stays thin: it validates the request, applies the
per-user and per-IP throttles, delegates URL validation and message assembly to
``games.services.suggestions``, and maps mail failures to an explicit 503.
Nothing is written to the database.
"""

from __future__ import annotations

import logging

from api.errors import STANDARD_ERROR_RESPONSES, ApiException
from api.schemas import ApiErrorResponse, ApiRequestSchema
from ninja import Field, Router, Schema
from security.throttling import (
    build_throttle_response,
    check_rate_limit_atomic,
    enforce_ip_rate_limit,
    hash_identifier,
)

from games.errors import ErrorCode
from games.services.suggestions import (
    SuggestionValidationError,
    send_game_suggestion,
    validate_storefront_url,
)

logger = logging.getLogger(__name__)

router = Router(tags=["Suggestions"])


class GameSuggestionIn(ApiRequestSchema):
    """User-submitted game suggestion payload."""

    name: str = Field(..., min_length=1, max_length=50)
    storefront_url: str = Field(default="", max_length=250)
    remarks: str = Field(default="", max_length=250)


class GameSuggestionAck(Schema):
    """Acknowledgement that the suggestion was emailed to the operator."""

    success: bool = True
    message: str = "Suggestion submitted successfully."


@router.post(
    "",
    response={
        200: GameSuggestionAck,
        422: ApiErrorResponse,
        **STANDARD_ERROR_RESPONSES,
    },
    operation_id="submit_game_suggestion",
    summary="Submit a game suggestion",
    description=(
        "Accept an authenticated user's game suggestion, rate-limit it per user "
        "(1 / 60s) and per IP (3 / 60s), and email it to the operator's "
        "suggestion inbox.  Nothing is persisted."
    ),
    url_name="game-suggestion",
)
def submit_game_suggestion(request, payload: GameSuggestionIn):
    if not request.user.is_authenticated:
        raise ApiException(401, "AUTHENTICATION_ERROR", "Authentication required.")

    name = payload.name.strip()
    if not name:
        raise ApiException(422, "VALIDATION_ERROR", "A name is required.")

    # Domain validation runs before the throttle so a malformed submission does
    # not consume the caller's single allowed slot.
    try:
        storefront_url = validate_storefront_url(payload.storefront_url)
    except SuggestionValidationError as exc:
        raise ApiException(422, "VALIDATION_ERROR", str(exc)) from exc

    user_scope = f"target:{hash_identifier(request.user.username)}:suggestion"
    limited, retry_after = check_rate_limit_atomic(
        user_scope, limit=1, window_seconds=60
    )
    if limited:
        return build_throttle_response(
            429,
            ErrorCode.RATE_LIMITED,
            f"Please wait {retry_after} seconds before submitting another suggestion.",
            retry_after,
        )

    ip_limited = enforce_ip_rate_limit(
        request,
        scope="suggestion",
        limit=3,
        window_seconds=60,
        message="Too many suggestions from this IP. Please try again shortly.",
    )
    if ip_limited is not None:
        return ip_limited

    try:
        send_game_suggestion(
            username=request.user.username,
            email=request.user.email or "",
            name=name,
            storefront_url=storefront_url,
            remarks=payload.remarks,
        )
    except Exception as exc:
        logger.exception("Failed to dispatch game suggestion email")
        raise ApiException(
            503,
            "SERVICE_UNAVAILABLE",
            "We couldn't send your suggestion right now. Please try again shortly.",
        ) from exc

    return GameSuggestionAck()
