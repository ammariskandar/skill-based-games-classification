"""Admin adaptive-perimeter middleware — SBGC-106.

Intercepts requests under the obfuscated admin path to (a) hold flagged-VPN
logins in the waiting room while a challenge is PENDING, and (b) enforce
Read-Only mode once a PENDING challenge expires unreviewed.
"""

from __future__ import annotations

import re

from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse

from security.models import ReportStatus
from security.models_cache import (
    APPROVED,
    PENDING,
    READ_ONLY,
    REJECTED,
    get_challenge,
    is_read_only_due,
    update_challenge_status,
)

_BODY_TAG_RE = re.compile(r"(<body[^>]*>)", re.IGNORECASE)

_READ_ONLY_BANNER = (
    '<div style="position: sticky; top: 0; z-index: 1000; '
    "background: #fff3cd; color: #856404; padding: 0.75rem 1rem; "
    'border-bottom: 2px solid #ffc107; font-weight: 600;">'
    "\u26a0\ufe0f CAUTION: You are operating in Read-Only mode. All save, "
    "edit, and delete actions are disabled."
    "</div>"
)


class AdminSecurityMiddleware:
    def __init__(self, get_response) -> None:
        self.get_response = get_response
        admin_path = getattr(settings, "ADMIN_URL_PATH", "admin").strip("/")
        self._admin_prefix = f"/{admin_path}/"
        self._security_prefix = f"/{admin_path}/security/"
        self._exempt_paths = (
            f"/{admin_path}/login/",
            f"/{admin_path}/logout/",
            f"/{admin_path}/security/waiting-room/",
            f"/{admin_path}/security/challenge-status/",
        )

    def _is_admin_path(self, path: str) -> bool:
        return path.startswith(self._admin_prefix)

    def _is_exempt(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self._exempt_paths)

    def __call__(self, request):
        if not self._is_admin_path(request.path):
            return self.get_response(request)

        challenge = get_challenge(request.session.get("admin_vpn_challenge_id"))
        if challenge is None:
            return self.get_response(request)

        status = challenge.get("status")
        if status == PENDING:
            if is_read_only_due(challenge):
                update_challenge_status(challenge["challenge_id"], READ_ONLY)
                status = READ_ONLY
            elif not self._is_exempt(request.path):
                return HttpResponseRedirect(f"{self._security_prefix}waiting-room/")
            else:
                return self.get_response(request)

        if status == READ_ONLY:
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                return self._readonly_forbidden()
            response = self.get_response(request)
            return self._inject_readonly_banner(response)

        if status in (APPROVED, REJECTED):
            request.session.pop("admin_vpn_challenge_id", None)
            return self.get_response(request)

        return self.get_response(request)

    @staticmethod
    def _readonly_forbidden() -> HttpResponseForbidden:
        html = (
            "<!DOCTYPE html><html><head><title>403 Forbidden</title></head>"
            "<body><h1>403 Forbidden: Read-Only Mode</h1>"
            "<p>State-mutating administrative actions are prohibited. This "
            "session is restricted to Read-Only mode until explicitly approved "
            "by an administrator.</p></body></html>"
        )
        return HttpResponseForbidden(html)

    def _inject_readonly_banner(self, response):
        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type:
            return response

        charset = getattr(response, "charset", None) or "utf-8"
        content = response.content.decode(charset, errors="replace")
        injected, count = _BODY_TAG_RE.subn(
            lambda match: match.group(1) + _READ_ONLY_BANNER,
            content,
            count=1,
        )
        if count:
            response.content = injected.encode(charset)
        return response


class ModerationEnforcementMiddleware:
    """Enforce moderation lockouts for authenticated, non-staff users (SBGC-223).

    Always records the governing lockout status on ``request.moderation_lockout``
    so read views can surface it.  API requests outside the remediation
    allow-list are refused with a structured ``403``; page routes are left to the
    Astro frontend, which redirects based on the status it reads from the API.
    Staff and superusers bypass enforcement entirely.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        request.moderation_lockout = None

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or user.is_staff:
            return self.get_response(request)

        # Imported lazily so the middleware module does not pull the service
        # graph (and its model imports) into app-loading.
        from security.services.reporting import active_lockout_status

        status = active_lockout_status(user)
        request.moderation_lockout = status
        if status is None:
            return self.get_response(request)

        if self._is_allowed(request.path, status):
            return self.get_response(request)

        if request.path.startswith("/api/"):
            return self._forbidden(status)

        # Non-API (page) routes are handled by the Astro frontend; Django serves
        # no public pages for these users.
        return self.get_response(request)

    @staticmethod
    def _is_allowed(path: str, status: str) -> bool:
        # Auth + the remediation handshake are always reachable so the user can
        # identify themselves, log out, or complete the forced change.  The
        # Django auth router is mounted under the versioned prefix; the
        # unversioned ``/api/auth/`` path is the Astro BFF, which never reaches
        # Django and so must not be relied on here.
        if (
            path.startswith("/api/v1/auth/")
            or path.startswith("/api/v1/security/remediate/")
            or path == "/api/v1/security/lockout"
        ):
            return True
        # Bio/name lockout permits the profile read + self-update boundary.
        if status == ReportStatus.PENDING_BIO_CHANGE and path.startswith(
            "/api/v1/users/"
        ):
            return True
        return False

    @staticmethod
    def _forbidden(status: str) -> JsonResponse:
        return JsonResponse(
            {
                "error": {
                    "code": "MODERATION_LOCKOUT",
                    "message": (
                        "Your account is locked pending moderation remediation."
                    ),
                    "details": [],
                },
                "lockout": status,
            },
            status=403,
        )
