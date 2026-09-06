"""Security alert email dispatch — SBGC-106 / SBGC-186."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
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


# ---------------------------------------------------------------------------
# Superuser rotation notifications — SBGC-186
# ---------------------------------------------------------------------------


def _dedup_emails(*users: User | None) -> list[str]:
    """Return deduplicated, non-empty email addresses from *users*."""
    seen: set[str] = set()
    emails: list[str] = []
    for user in users:
        if user is None:
            continue
        email = (getattr(user, "email", "") or "").strip()
        if email and email not in seen:
            seen.add(email)
            emails.append(email)
    return emails


def _owner_user() -> User | None:
    username = (getattr(settings, "DJANGO_OWNER_USERNAME", "") or "").strip()
    if not username:
        return None
    return User.objects.filter(username=username, is_active=True).first()


def _active_superusers() -> list[User]:
    return list(User.objects.filter(is_superuser=True, is_active=True))


def dispatch_superuser_promotion_email(
    moderator: User, inactive_superuser: User
) -> None:
    """Notify all parties that a moderator was temporarily promoted."""
    context = {
        "moderator_username": moderator.get_username(),
        "inactive_username": inactive_superuser.get_username(),
        "inactivity_days": settings.SUPERUSER_INACTIVITY_DAYS,
    }
    body = render_to_string("emails/superuser_promoted.txt", context)
    recipients = _dedup_emails(moderator, _owner_user(), *_active_superusers())
    if not recipients:
        return
    send_mail(
        subject=(
            f"[SECURITY ALERT] Temporary superuser promotion: "
            f"{moderator.get_username()}"
        ),
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )


def dispatch_superuser_reversion_email(
    moderator: User, restored_superuser: User
) -> None:
    """Notify all parties that a temporary promotion was reverted."""
    context = {
        "moderator_username": moderator.get_username(),
        "restored_username": restored_superuser.get_username(),
    }
    body = render_to_string("emails/superuser_reverted.txt", context)
    recipients = _dedup_emails(
        moderator, restored_superuser, _owner_user(), *_active_superusers()
    )
    if not recipients:
        return
    send_mail(
        subject=(
            f"[SECURITY] Superuser {restored_superuser.get_username()} "
            f"restored; {moderator.get_username()} reverted"
        ),
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )


def dispatch_moderator_shortage_email(inactive_superuser: User) -> None:
    """Alert the owner and superusers that no moderator could be promoted."""
    context = {
        "inactive_username": inactive_superuser.get_username(),
        "inactivity_days": settings.SUPERUSER_INACTIVITY_DAYS,
    }
    body = render_to_string("emails/moderator_shortage_alert.txt", context)
    recipients = _dedup_emails(_owner_user(), *_active_superusers())
    if not recipients:
        return
    send_mail(
        subject=(
            f"[SECURITY ALERT] No moderator available to cover "
            f"{inactive_superuser.get_username()}"
        ),
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )
