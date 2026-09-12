"""
Security API router — SBGC-223.

Public report ingestion and the authenticated forced-username remediation
handshake.  The HTTP layer stays thin: it validates the request, delegates to
``security.services.reporting``, and maps domain errors to explicit statuses.
"""

from __future__ import annotations

from api.errors import STANDARD_ERROR_RESPONSES, ApiException
from api.schemas import ApiErrorResponse, ApiRequestSchema
from django.contrib.auth import update_session_auth_hash
from ninja import Field, Router, Schema

from security.services.reporting import (
    ReportNotFoundError,
    ReportValidationError,
    active_lockout_status,
    complete_username_remediation,
    submit_user_report,
    username_remediation_target,
)

router = Router(tags=["Security"])


class UserReportIn(ApiRequestSchema):
    offending_username: str = Field(..., min_length=1, max_length=150)
    reason_username: bool = False
    reason_name: bool = False
    reason_bio: bool = False
    reason_other: bool = False
    other_description: str = Field(default="", max_length=250)


class UserReportAck(Schema):
    success: bool = True
    message: str = "Report submitted successfully."


class RemediationContextOut(Schema):
    username: str
    email: str


class LockoutStatusOut(Schema):
    status: str | None = None
    username: str | None = None


class UsernameRemediationIn(ApiRequestSchema):
    new_username: str = Field(..., min_length=4, max_length=20)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)


class UsernameRemediationOut(Schema):
    success: bool = True
    username: str
    message: str = "Your username and password have been updated."


@router.post(
    "/reports/user",
    response={200: UserReportAck, 422: ApiErrorResponse, **STANDARD_ERROR_RESPONSES},
    summary="File a user report",
    description=(
        "File or merge a report against another user.  A reporter holds at most "
        "one open report per offending user; repeat filings merge their reason "
        "flags instead of creating duplicate triage rows (SBGC-223)."
    ),
)
def report_user(request, payload: UserReportIn):
    if not request.user.is_authenticated:
        raise ApiException(401, "AUTHENTICATION_ERROR", "Authentication required.")

    try:
        submit_user_report(
            reporting_user=request.user,
            offending_username=payload.offending_username,
            reason_username=payload.reason_username,
            reason_name=payload.reason_name,
            reason_bio=payload.reason_bio,
            reason_other=payload.reason_other,
            other_description=payload.other_description,
        )
    except ReportNotFoundError as exc:
        raise ApiException(404, "NOT_FOUND", str(exc)) from exc
    except ReportValidationError as exc:
        raise ApiException(422, "VALIDATION_ERROR", str(exc)) from exc

    return UserReportAck()


@router.get(
    "/lockout",
    response={200: LockoutStatusOut, **STANDARD_ERROR_RESPONSES},
    summary="Report the caller's moderation lockout status",
    description=(
        "Returns the authenticated caller's active lockout status (or null when "
        "unlocked) so the Astro perimeter can route them to the correct "
        "remediation surface (SBGC-223)."
    ),
)
def lockout_status(request):
    if not request.user.is_authenticated:
        raise ApiException(401, "AUTHENTICATION_ERROR", "Authentication required.")
    return LockoutStatusOut(
        status=active_lockout_status(request.user),
        username=request.user.username,
    )


@router.get(
    "/remediate/username",
    response={
        200: RemediationContextOut,
        403: ApiErrorResponse,
        **STANDARD_ERROR_RESPONSES,
    },
    summary="Forced username remediation context",
)
def remediation_context(request):
    if not request.user.is_authenticated:
        raise ApiException(401, "AUTHENTICATION_ERROR", "Authentication required.")
    if username_remediation_target(request.user) is None:
        raise ApiException(
            403,
            "AUTHORIZATION_ERROR",
            "Your account is not under a username-change lockout.",
        )
    return RemediationContextOut(
        username=request.user.username,
        email=request.user.email or "",
    )


@router.post(
    "/remediate/username",
    response={
        200: UsernameRemediationOut,
        422: ApiErrorResponse,
        **STANDARD_ERROR_RESPONSES,
    },
    summary="Complete a forced username change",
    description=(
        "Apply the forced username + password rotation for a locked-out account "
        "and resolve the governing report (SBGC-223)."
    ),
)
def remediate_username(request, payload: UsernameRemediationIn):
    if not request.user.is_authenticated:
        raise ApiException(401, "AUTHENTICATION_ERROR", "Authentication required.")

    if payload.new_password != payload.confirm_password:
        raise ApiException(422, "VALIDATION_ERROR", "Passwords do not match.")

    if username_remediation_target(request.user) is None:
        raise ApiException(
            403,
            "AUTHORIZATION_ERROR",
            "Your account is not under a username-change lockout.",
        )

    try:
        user = complete_username_remediation(
            request.user,
            new_username=payload.new_username,
            new_password=payload.new_password,
        )
    except ReportValidationError as exc:
        raise ApiException(422, "VALIDATION_ERROR", str(exc)) from exc

    # The password changed, so re-hash the active session to avoid logging the
    # user out of the request that just rotated it.
    update_session_auth_hash(request, user)

    return UsernameRemediationOut(username=user.username)
