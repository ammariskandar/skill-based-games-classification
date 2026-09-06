"""Admin security views — SBGC-106."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

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
