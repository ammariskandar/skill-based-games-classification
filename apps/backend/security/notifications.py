"""Security alert email dispatch — SBGC-106."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.urls import reverse


def notify_superusers_of_vpn_login(
    request,
    user: User,
    challenge: dict,
    review_token: str,
) -> None:
    """Email every active superuser a one-click review link for the challenge."""
    review_path = reverse("security:review_login")
    review_url = request.build_absolute_uri(f"{review_path}?token={review_token}")

    subject = f"[SECURITY ALERT] Suspicious Admin Login from VPN: {user.username}"
    body = (
        "Administrator Notice:\n\n"
        f"User '{user.username}' ({user.email}) has initiated a login to "
        "Django Admin from a flagged VPN/Datacenter IP address.\n\n"
        "Login Metadata:\n"
        f"- IP Address: {challenge.get('ip_address', '')}\n"
        f"- User Agent: {challenge.get('user_agent', '')}\n"
        f"- Timestamp: {challenge.get('created_at', '')} UTC\n\n"
        "To approve or reject this administrative session, click the link below:\n"
        f"{review_url}\n\n"
        "If unreviewed, this session will degrade to Read-Only mode in 30 "
        "minutes.\n"
    )

    recipients = list(
        User.objects.filter(is_superuser=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not recipients:
        return

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )
