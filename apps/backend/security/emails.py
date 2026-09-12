"""
Moderation email dispatch — SBGC-223.

Plain-text transactional notices for the permaban workflow:

* ``send_permaban_notice`` — sent to the offender immediately when a moderator
  confirms a permanent ban.
* ``send_reporter_gratitude_email`` — sent to each unique reporter once the
  three-hour hard purge has executed.

Both render from ``templates/emails/*.txt`` and are dispatched through Django's
configured email backend so tests can assert on the locmem outbox.
"""

from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_permaban_notice(
    *,
    recipient_email: str,
    username: str,
    ban_reason: str,
    reasons: list[str],
) -> None:
    """Notify the offender that their account is scheduled for deletion."""
    if not recipient_email:
        return
    body = render_to_string(
        "emails/account_permaban_notice.txt",
        {
            "username": username,
            "ban_reason": ban_reason,
            "reasons": reasons,
            "site_name": "MyGameDNA",
        },
    )
    send_mail(
        subject="Your MyGameDNA account has been permanently banned",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        fail_silently=True,
    )


def send_reporter_gratitude_email(*, recipient_email: str) -> None:
    """Thank a reporter after enforcement action removed the reported account."""
    if not recipient_email:
        return
    body = render_to_string(
        "emails/reporter_action_notice.txt",
        {"site_name": "MyGameDNA"},
    )
    send_mail(
        subject="Thank you for your report",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        fail_silently=True,
    )


__all__ = ["send_permaban_notice", "send_reporter_gratitude_email"]
