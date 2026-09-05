"""
Authentication API router — SBGC-217.

Session-backed login/status/logout endpoints.  Zero client-side JWTs: the
opaque Django ``sessionid`` is the only credential, and it is never echoed
back to the client in a JSON payload (the session cookie is set by Django's
SessionMiddleware).

The browser never reaches these endpoints directly — the Astro BFF relays
them server-to-server (see apps/frontend/src/pages/api/auth/).
"""

from api.errors import STANDARD_ERROR_RESPONSES
from api.schemas import ApiErrorResponse
from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, JsonResponse
from django.views.decorators.debug import sensitive_post_parameters
from games.errors import ErrorCode
from ninja import Router

from authentication.schemas import AuthStatusResponseSchema, LoginRequestSchema
from authentication.throttling import (
    clear_failed_login,
    is_login_rate_limited,
    record_failed_login,
)

auth_router = Router(tags=["Authentication"])


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
