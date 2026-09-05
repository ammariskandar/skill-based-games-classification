"""
Authentication API router — SBGC-217.

Session-backed login/status/logout endpoints.  Zero client-side JWTs: the
opaque Django ``sessionid`` is the only credential, and it is never echoed
back to the client in a JSON payload (the session cookie is set by Django's
SessionMiddleware).

The browser never reaches these endpoints directly — the Astro BFF relays
them server-to-server (see apps/frontend/src/pages/api/auth/).
"""

import logging
import uuid

from api.errors import STANDARD_ERROR_RESPONSES
from api.schemas import ApiErrorResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.views.decorators.debug import sensitive_post_parameters
from games.errors import ErrorCode
from ninja import Query, Router

from authentication.emails import (
    email_is_registered,
    normalize_email,
    resolve_active_user_by_email,
)
from authentication.schemas import (
    AuthStatusResponseSchema,
    BurnResetTokenRequestSchema,
    CheckUsernameRequestSchema,
    CheckUsernameResponseSchema,
    ConfirmEmailRequestSchema,
    ConfirmEmailResponseSchema,
    ForgotPasswordRequestSchema,
    ForgotUsernameRequestSchema,
    GenericRecoveryResponseSchema,
    LoginRequestSchema,
    ResetActionSuccessResponseSchema,
    ResetPasswordConfirmRequestSchema,
    SignUpRequestSchema,
    VerificationStatusResponseSchema,
    VerifyEmailRequestSchema,
    VerifyEmailResponseSchema,
    VerifyResetTokenRequestSchema,
    VerifyResetTokenResponseSchema,
)
from authentication.throttling import (
    clear_failed_login,
    get_client_ip,
    is_login_rate_limited,
    record_failed_login,
)
from authentication.tokens import (
    burn_reset_session_nonce,
    claim_password_reset_token,
    confirm_email_challenge,
    create_email_challenge,
    create_password_reset_token,
    delete_challenge,
    get_challenge,
    get_reset_session,
    increment_resend_attempt,
    is_signup_rate_limited,
    revoke_all_user_sessions,
    send_existing_account_email,
    send_password_changed_notification,
    send_password_reset_email,
    send_username_recovery_email,
    verify_recaptcha,
)

logger = logging.getLogger(__name__)

auth_router = Router(tags=["Authentication"])

# Module-level singletons so Ninja Query defaults are not function calls in
# argument defaults (ruff B008).
_username_query = Query(...)  # pyright: ignore[reportCallIssue]
_challenge_id_query = Query(...)  # pyright: ignore[reportCallIssue]


def _json(status: int, code: str, message: str) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": code, "message": message, "details": []}},
        status=status,
    )


@auth_router.post(
    "/login",
    response={
        200: AuthStatusResponseSchema,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="auth_login",
    summary="Authenticate a user",
    url_name="auth-login",
)
@sensitive_post_parameters("password")
def login_endpoint(request: HttpRequest, payload: LoginRequestSchema) -> JsonResponse:
    username = payload.username.strip()
    password = payload.password

    # 1. Enforce brute-force rate limiting (IP + username buckets).
    if is_login_rate_limited(request, username):
        response = JsonResponse(
            {
                "error": {
                    "code": ErrorCode.RATE_LIMITED.value,
                    "message": (
                        "Too many failed login attempts. "
                        "Please try again in 60 seconds."
                    ),
                    "details": [],
                }
            },
            status=429,
        )
        response["Retry-After"] = "60"
        return response

    # 2. Authenticate against Django's database authority.
    #    `authenticate` runs a dummy password hash for a missing user so the
    #    timing is equalized between existing and non-existent usernames.
    user = authenticate(request, username=username, password=password)

    if user is None or not user.is_active:
        record_failed_login(request, username)
        return JsonResponse(
            {
                "error": {
                    "code": ErrorCode.AUTHENTICATION_ERROR.value,
                    "message": "Invalid username or password.",
                    "details": [],
                }
            },
            status=401,
        )

    # 3. Success: reset buckets, establish the session, and cycle the key to
    #    defeat session fixation.
    clear_failed_login(request, username)
    login(request, user)
    request.session.cycle_key()

    return JsonResponse({"authenticated": True, "username": user.get_username()})


@auth_router.get(
    "/status",
    response={
        200: AuthStatusResponseSchema,
        **STANDARD_ERROR_RESPONSES,
    },
    operation_id="auth_status",
    summary="Return the current authentication state",
    url_name="auth-status",
)
def status_endpoint(request: HttpRequest) -> AuthStatusResponseSchema:
    if request.user.is_authenticated:
        return AuthStatusResponseSchema(
            authenticated=True, username=request.user.get_username()
        )
    return AuthStatusResponseSchema(authenticated=False, username=None)


@auth_router.post(
    "/logout",
    response={
        200: AuthStatusResponseSchema,
        **STANDARD_ERROR_RESPONSES,
    },
    operation_id="auth_logout",
    summary="Terminate the current session",
    url_name="auth-logout",
)
def logout_endpoint(request: HttpRequest) -> JsonResponse:
    logout(request)
    response = JsonResponse({"authenticated": False, "username": None})
    response.delete_cookie("sessionid")
    return response


# ── SBGC-218 sign-up endpoints ───────────────────────────────────────────


@auth_router.get(
    "/check-username",
    response={
        200: CheckUsernameResponseSchema,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="auth_check_username",
    summary="Check whether a username is available",
    url_name="auth-check-username",
)
def check_username(
    request, query: CheckUsernameRequestSchema = _username_query
) -> CheckUsernameResponseSchema:
    available = not User.objects.filter(username__iexact=query.username).exists()
    return CheckUsernameResponseSchema(available=available, username=query.username)


@auth_router.post(
    "/verify-email-request",
    response={
        200: VerifyEmailResponseSchema,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="auth_verify_email_request",
    summary="Request a pre-registration email verification challenge",
    url_name="auth-verify-email-request",
)
def verify_email_request(
    request: HttpRequest, payload: VerifyEmailRequestSchema
) -> JsonResponse:
    # Honeypot trap — a bot that populates the hidden field is rejected silently.
    if payload.company_website:
        return _json(400, ErrorCode.BAD_REQUEST.value, "Invalid request.")

    ip = get_client_ip(request)
    email = payload.email.strip().lower()

    if is_signup_rate_limited(ip, email):
        response = _json(
            429,
            ErrorCode.RATE_LIMITED.value,
            "Too many verification attempts. Please try again later.",
        )
        response["Retry-After"] = "1800"
        return response

    if not verify_recaptcha(payload.recaptcha_token, ip):
        return _json(400, ErrorCode.BAD_REQUEST.value, "Invalid request.")

    increment_resend_attempt(ip, email)

    # Zero email enumeration: return an identical generic challenge whether or
    # not the address is already registered — the distinction is email-only.
    # Gmail/Googlemail dot-aliases count as registered (same mailbox).
    if email_is_registered(email):
        send_existing_account_email(email)
        return JsonResponse(
            {
                "challenge_id": str(uuid.uuid4()),
                "message": "Verification email sent.",
            }
        )

    challenge_id = create_email_challenge(email)
    return JsonResponse(
        {"challenge_id": challenge_id, "message": "Verification email sent."}
    )


@auth_router.get(
    "/verification-status",
    response={
        200: VerificationStatusResponseSchema,
        **STANDARD_ERROR_RESPONSES,
    },
    operation_id="auth_verification_status",
    summary="Poll a pre-registration email challenge status",
    url_name="auth-verification-status",
)
def verification_status(
    request, challenge_id: str = _challenge_id_query
) -> VerificationStatusResponseSchema:
    data = get_challenge(challenge_id)
    return VerificationStatusResponseSchema(
        verified=bool(data and data.get("status") == "VERIFIED")
    )


@auth_router.post(
    "/confirm-email",
    response={
        200: ConfirmEmailResponseSchema,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="auth_confirm_email",
    summary="Confirm a pre-registration email via signed token",
    url_name="auth-confirm-email",
)
def confirm_email(request, payload: ConfirmEmailRequestSchema) -> JsonResponse:
    if not confirm_email_challenge(payload.token):
        return _json(
            400, ErrorCode.BAD_REQUEST.value, "Invalid or expired verification link."
        )
    return JsonResponse({"success": True})


@auth_router.post(
    "/signup",
    response={
        201: AuthStatusResponseSchema,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="auth_signup",
    summary="Register a verified account and establish a session",
    url_name="auth-signup",
)
@sensitive_post_parameters("password")
def signup_endpoint(request: HttpRequest, payload: SignUpRequestSchema) -> JsonResponse:
    # Honeypot trap.
    if payload.company_website:
        return _json(400, ErrorCode.BAD_REQUEST.value, "Invalid request.")

    # reCAPTCHA v3 score gate.
    if not verify_recaptcha(payload.recaptcha_token, get_client_ip(request)):
        return _json(400, ErrorCode.BAD_REQUEST.value, "Invalid request.")

    # Cryptographic backend guard: the challenge must exist, be VERIFIED, and
    # match the submitted email — DOM tampering cannot bypass this.
    email = payload.email.strip().lower()
    challenge = get_challenge(payload.challenge_id)
    if (
        not challenge
        or challenge.get("status") != "VERIFIED"
        or challenge.get("email") != email
    ):
        return _json(400, ErrorCode.EMAIL_NOT_VERIFIED.value, "Email not verified.")

    username_taken = User.objects.filter(username__iexact=payload.username).exists()
    # Gmail dot-aliases (john.smith@gmail.com vs johnsmith@gmail.com) resolve to
    # the same mailbox and must not be double-registered.
    email_taken = email_is_registered(email)
    if username_taken or email_taken:
        return _json(
            409,
            ErrorCode.CONFLICT.value,
            "An account already exists for this username or email.",
        )

    user = User.objects.create_user(
        username=payload.username,
        email=email,
        password=payload.password,
    )

    # Single-use challenge: delete it so the verification cannot be replayed.
    delete_challenge(payload.challenge_id)

    # Auto-login on registration and rotate the session key.
    login(request, user)
    request.session.cycle_key()

    return JsonResponse(
        {"authenticated": True, "username": user.get_username()}, status=201
    )


# ── SBGC-219 account recovery & one-chance password reset ───────────────────


def _recovery_rate_limited(request: HttpRequest, email: str) -> JsonResponse | None:
    """Return a 429 response when the recovery rate limit is hit, else None."""
    if not is_signup_rate_limited(get_client_ip(request), email):
        return None
    response = _json(
        429,
        ErrorCode.RATE_LIMITED.value,
        "Too many recovery requests. Please try again later.",
    )
    response["Retry-After"] = "1800"
    return response


@auth_router.post(
    "/forgot-username",
    response={
        200: GenericRecoveryResponseSchema,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="auth_forgot_username",
    summary="Email a username reminder when the address matches an account",
    url_name="auth-forgot-username",
)
def forgot_username_endpoint(
    request: HttpRequest, payload: ForgotUsernameRequestSchema
) -> JsonResponse:
    # Honeypot trap — a bot that populates the hidden field is rejected silently.
    if payload.company_website:
        logger.warning(
            "Recovery honeypot triggered on forgot-username (trap length %d).",
            len(payload.company_website),
        )
        return _json(400, ErrorCode.BAD_REQUEST.value, "Invalid request.")

    email = payload.email.strip().lower()

    rate_limited = _recovery_rate_limited(request, email)
    if rate_limited is not None:
        return rate_limited

    if not verify_recaptcha(payload.recaptcha_token, get_client_ip(request)):
        return _json(400, ErrorCode.BAD_REQUEST.value, "Invalid request.")

    increment_resend_attempt(get_client_ip(request), email)

    # Zero enumeration: a missing account silently skips the email and the
    # response body stays byte-identical to the success case.
    user = resolve_active_user_by_email(email)
    if user is not None:
        send_username_recovery_email(user)

    return JsonResponse(
        {
            "success": True,
            "message": (
                "If the provided details match an account, instructions have been sent."
            ),
        }
    )


@auth_router.post(
    "/forgot-password",
    response={
        200: GenericRecoveryResponseSchema,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="auth_forgot_password",
    summary="Email a one-chance reset link when username and email match",
    url_name="auth-forgot-password",
)
def forgot_password_endpoint(
    request: HttpRequest, payload: ForgotPasswordRequestSchema
) -> JsonResponse:
    # Honeypot trap.
    if payload.company_website:
        logger.warning(
            "Recovery honeypot triggered on forgot-password (trap length %d).",
            len(payload.company_website),
        )
        return _json(400, ErrorCode.BAD_REQUEST.value, "Invalid request.")

    email = payload.email.strip().lower()

    rate_limited = _recovery_rate_limited(request, email)
    if rate_limited is not None:
        return rate_limited

    if not verify_recaptcha(payload.recaptcha_token, get_client_ip(request)):
        return _json(400, ErrorCode.BAD_REQUEST.value, "Invalid request.")

    increment_resend_attempt(get_client_ip(request), email)

    # Dual-match requirement: username (case-insensitive) AND a canonical email
    # match against the stored record.  Gmail dot-aliases resolve because the
    # stored address is canonicalised before comparison.
    user = User.objects.filter(
        username__iexact=payload.username,
        is_active=True,
    ).first()
    email_matches = user is not None and normalize_email(user.email) == normalize_email(
        email
    )

    if user is not None and email_matches:
        token = create_password_reset_token(user)
        send_password_reset_email(user, token)

    return JsonResponse(
        {
            "success": True,
            "message": (
                "If the provided details match an account, instructions have been sent."
            ),
        }
    )


@auth_router.post(
    "/verify-reset-token",
    response={
        200: VerifyResetTokenResponseSchema,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="auth_verify_reset_token",
    summary="Exchange a signed reset token for a one-chance session nonce",
    url_name="auth-verify-reset-token",
)
def verify_reset_token_endpoint(
    request: HttpRequest, payload: VerifyResetTokenRequestSchema
) -> VerifyResetTokenResponseSchema:
    session_nonce = claim_password_reset_token(payload.token)
    if session_nonce is None:
        return VerifyResetTokenResponseSchema(valid=False, session_nonce=None)
    return VerifyResetTokenResponseSchema(valid=True, session_nonce=session_nonce)


@auth_router.post(
    "/burn-reset-token",
    response={
        200: ResetActionSuccessResponseSchema,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="auth_burn_reset_token",
    summary="Burn a claimed reset session (anti-abandonment invalidation)",
    url_name="auth-burn-reset-token",
)
def burn_reset_token_endpoint(
    request: HttpRequest, payload: BurnResetTokenRequestSchema
) -> JsonResponse:
    burn_reset_session_nonce(payload.session_nonce)
    return JsonResponse({"success": True})


@auth_router.post(
    "/reset-password-confirm",
    response={
        200: ResetActionSuccessResponseSchema,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="auth_reset_password_confirm",
    summary="Set a new password with a one-chance reset session nonce",
    url_name="auth-reset-password-confirm",
)
@sensitive_post_parameters("new_password")
def reset_password_confirm_endpoint(
    request: HttpRequest, payload: ResetPasswordConfirmRequestSchema
) -> JsonResponse:
    # Honeypot trap.
    if payload.company_website:
        return _json(400, ErrorCode.BAD_REQUEST.value, "Invalid request.")

    if not verify_recaptcha(payload.recaptcha_token, get_client_ip(request)):
        return _json(400, ErrorCode.BAD_REQUEST.value, "Invalid request.")

    # The nonce is the human-session credential: it exists only after the token
    # was claimed, and it is burned the moment it is redeemed.
    data = get_reset_session(payload.session_nonce)
    if not data:
        return _json(
            400,
            ErrorCode.EXPIRED_RESET_TOKEN.value,
            "This reset session has expired or has already been used.",
        )

    # One-chance guarantee: consume the nonce AND its parent token now, so a
    # reload, back-navigation, or duplicate submission cannot replay it.
    burn_reset_session_nonce(payload.session_nonce)

    user = User.objects.filter(pk=data.get("user_id"), is_active=True).first()
    if user is None:
        return _json(
            400,
            ErrorCode.EXPIRED_RESET_TOKEN.value,
            "This reset session has expired or has already been used.",
        )

    user.set_password(payload.new_password)
    user.save()

    # Kick every existing session for this user out of django_session.
    revoke_all_user_sessions(user.pk)
    # Alert the account owner.  No auto-login: the user signs in fresh.
    send_password_changed_notification(user)

    return JsonResponse({"success": True})
