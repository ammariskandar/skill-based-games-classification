"""
Authentication API router — SBGC-217.

Session-backed login/status/logout endpoints.  Zero client-side JWTs: the
opaque Django ``sessionid`` is the only credential, and it is never echoed
back to the client in a JSON payload (the session cookie is set by Django's
SessionMiddleware).

The browser never reaches these endpoints directly — the Astro BFF relays
them server-to-server (see apps/frontend/src/pages/api/auth/).
"""

import uuid

from api.errors import STANDARD_ERROR_RESPONSES
from api.schemas import ApiErrorResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.views.decorators.debug import sensitive_post_parameters
from games.errors import ErrorCode
from ninja import Query, Router

from authentication.emails import email_is_registered
from authentication.schemas import (
    AuthStatusResponseSchema,
    CheckUsernameRequestSchema,
    CheckUsernameResponseSchema,
    ConfirmEmailRequestSchema,
    ConfirmEmailResponseSchema,
    LoginRequestSchema,
    SignUpRequestSchema,
    VerificationStatusResponseSchema,
    VerifyEmailRequestSchema,
    VerifyEmailResponseSchema,
)
from authentication.throttling import (
    clear_failed_login,
    get_client_ip,
    is_login_rate_limited,
    record_failed_login,
)
from authentication.tokens import (
    confirm_email_challenge,
    create_email_challenge,
    delete_challenge,
    get_challenge,
    increment_resend_attempt,
    is_signup_rate_limited,
    send_existing_account_email,
    verify_recaptcha,
)

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
