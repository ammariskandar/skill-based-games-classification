"""Admin security views — SBGC-106 / SBGC-108."""

from __future__ import annotations

import logging
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from security.dependencies import TECH_STACK_REGISTRY
from security.models_cache import (
    APPROVED,
    PENDING,
    READ_ONLY,
    REJECTED,
    execute_security_lockout,
    get_challenge,
    is_read_only_due,
    update_challenge_status,
    verify_review_token,
    whitelist_user_ip,
)

logger = logging.getLogger("django.security")


def waiting_room(request: HttpRequest):
    challenge = get_challenge(request.session.get("admin_vpn_challenge_id"))
    if challenge is None:
        return redirect(reverse("admin:login"))

    remaining_seconds = max(
        0,
        int(float(challenge.get("expires_at", 0)) - timezone.now().timestamp()),
    )
    return render(
        request,
        "admin/waiting_room.html",
        {
            "challenge": challenge,
            "remaining_seconds": remaining_seconds,
            "admin_path": settings.ADMIN_URL_PATH,
        },
    )


def challenge_status(request: HttpRequest) -> JsonResponse:
    challenge = get_challenge(request.session.get("admin_vpn_challenge_id"))
    if challenge is None:
        return JsonResponse({"status": "EXPIRED", "expires_at": 0})

    # The polling endpoint is exempt from the middleware PENDING redirect, so
    # perform the unreviewed-expiry transition here on the first poll after the
    # 30-minute window elapses.
    if challenge.get("status") == PENDING and is_read_only_due(challenge):
        update_challenge_status(challenge["challenge_id"], READ_ONLY)
        challenge["status"] = READ_ONLY

    return JsonResponse(
        {
            "status": challenge.get("status"),
            "expires_at": challenge.get("expires_at", 0),
        }
    )


def review_login(request: HttpRequest):
    if not request.user.is_authenticated or not getattr(
        request.user, "is_superuser", False
    ):
        return redirect(reverse("admin:login"))

    reviewer = getattr(request.user, "username", "")

    token = request.POST.get("token") or request.GET.get("token", "")
    challenge_id = verify_review_token(token)
    if challenge_id is None:
        return render(
            request,
            "admin/review_login.html",
            {"error": "Invalid or expired review token."},
        )

    challenge = get_challenge(challenge_id)
    if challenge is None:
        return render(
            request,
            "admin/review_login.html",
            {"error": "Challenge not found or already resolved."},
        )

    context = {"challenge": challenge, "review_token": token}
    if request.method == "POST":
        action = request.POST.get("action")
        if challenge.get("status") != PENDING:
            context["error"] = "This challenge was already resolved."
            return render(request, "admin/review_login.html", context)
        if action == "approve":
            update_challenge_status(challenge_id, APPROVED)
            whitelist_user_ip(challenge["user_id"], challenge["ip_address"])
            logger.info(
                "Superuser %s approved VPN admin login for %s",
                reviewer,
                challenge.get("username"),
            )
            context["result"] = "APPROVED"
            return render(request, "admin/review_login.html", context)
        if action == "reject":
            update_challenge_status(challenge_id, REJECTED)
            try:
                target = User.objects.get(pk=challenge["user_id"])
            except User.DoesNotExist:
                context["error"] = "Target user no longer exists."
                return render(request, "admin/review_login.html", context)
            execute_security_lockout(target, "Admin login rejected by superuser review")
            logger.info(
                "Superuser %s rejected and locked user %s",
                reviewer,
                challenge.get("username"),
            )
            context["result"] = "REJECTED"
            return render(request, "admin/review_login.html", context)

    return render(request, "admin/review_login.html", context)


# ── SBGC-108 staff tech-stack registry ──────────────────────────────────────


def dependency_registry_view(request: HttpRequest) -> HttpResponse:
    """Render the tech stack catalog to authorized staff/superusers.

    Authorization mirrors the Django Admin boundary (SBGC-105/106 defence in
    depth): the caller must be an active staff member, and either a superuser
    (who always bypasses) or granted the ``security.view_dependencyregistryentry``
    permission through the Admin user/group permission picker (e.g. assigned to
    a Moderator role).  Anonymous callers are redirected to the admin login;
    authenticated callers without the grant receive 403.
    """
    user = request.user
    if not getattr(user, "is_authenticated", False):
        login_url = reverse("admin:login")
        return redirect(f"{login_url}?next={quote(request.path)}")

    can_view = bool(
        getattr(user, "is_active", False)  # pyright: ignore[reportAttributeAccessIssue]
        and getattr(user, "is_staff", False)  # pyright: ignore[reportAttributeAccessIssue]
        and (  # pyright: ignore[reportAttributeAccessIssue]
            getattr(user, "is_superuser", False)  # pyright: ignore[reportAttributeAccessIssue]
            or user.has_perm(  # pyright: ignore[reportAttributeAccessIssue]
                "security.view_dependencyregistryentry"
            )
        )
    )
    if not can_view:
        raise PermissionDenied(
            "Requires active staff access with the "
            "security.view_dependencyregistryentry permission."
        )

    return render(
        request,
        "admin/security/dependency_registry.html",
        {
            "dependencies": TECH_STACK_REGISTRY,
            "title": "Tech Stack & Dependency Registry",
            "is_nav_sidebar_enabled": True,
        },
    )
