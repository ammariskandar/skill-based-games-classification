"""
User-report ingestion, anti-abuse heuristics & moderation workflows — SBGC-223.

Owns the full manual-moderation domain:

* **Coalescing** — a ``(reporter, offender)`` pair holds at most one open report;
  repeat filings merge their reason flags rather than creating duplicate triage
  rows.
* **Anti-brigading** — a rolling 15-minute burst of >= 100 reports against one
  offender flags every open report in the window.
* **Repeat-offender snapshot** — whether the offender already had a dismissed or
  resolved report at submission time.
* **Moderation actions** — dismiss, forced username change, forced name/bio
  change, and the three-hour permanent-ban schedule (revoke sessions, lock the
  account, snapshot the deletion, email the offender).
* **Remediation handshakes** — completing a forced username or name/bio change
  transitions the governing report to ``RESOLVED``.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from authentication.schemas import USERNAME_FORMAT_MESSAGE, USERNAME_REGEX
from authentication.tokens import revoke_all_user_sessions
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from security.emails import send_permaban_notice
from security.models import (
    LOCKOUT_REPORT_STATUSES,
    OPEN_REPORT_STATUSES,
    ReportStatus,
    ScheduledAccountDeletion,
    UserReport,
)

BRIGADING_WINDOW = timedelta(minutes=15)
BRIGADING_THRESHOLD = 100
PERMABAN_DELAY = timedelta(hours=3)
OTHER_DESCRIPTION_MAX = 250

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class ReportValidationError(ValueError):
    """A report payload or moderation input violates a domain rule."""


class ReportNotFoundError(LookupError):
    """The target user or report does not exist."""


# ---------------------------------------------------------------------------
# Sanitisation helpers
# ---------------------------------------------------------------------------


def sanitize_plain_text(value: str | None, *, limit: int) -> str:
    """Strip control codes, reject angle brackets, trim, and cap *value*.

    Report free text is rendered in the Admin and in emails, so markup
    characters are hard-rejected rather than escaped.
    """
    if not value:
        return ""
    cleaned = _CONTROL_CHARS.sub("", value)
    if "<" in cleaned or ">" in cleaned:
        raise ReportValidationError("Angle brackets are not allowed.")
    return cleaned.strip()[:limit]


# ---------------------------------------------------------------------------
# Ingestion heuristics
# ---------------------------------------------------------------------------


def resolve_offender(offending_username: str) -> User:
    """Resolve the reported account by case-insensitive username."""
    offender = User.objects.filter(
        username__iexact=(offending_username or "").strip()
    ).first()
    if offender is None:
        raise ReportNotFoundError("User not found.")
    return offender


def is_repeat_offender(offender: User) -> bool:
    """True when the offender already has a dismissed or resolved report."""
    return UserReport.objects.filter(
        offending_user=offender,
        status__in=[ReportStatus.DISMISSED, ReportStatus.RESOLVED],
    ).exists()


def _brigading_count(offender: User, *, now: datetime | None = None) -> int:
    cutoff = (now or timezone.now()) - BRIGADING_WINDOW
    return UserReport.objects.filter(
        offending_user=offender,
        created_at__gte=cutoff,
    ).count()


def _flag_brigading(offender: User) -> bool:
    """Flag every open report within the window when the burst threshold trips."""
    if _brigading_count(offender) < BRIGADING_THRESHOLD:
        return False
    cutoff = timezone.now() - BRIGADING_WINDOW
    UserReport.objects.filter(
        offending_user=offender,
        status__in=OPEN_REPORT_STATUSES,
        created_at__gte=cutoff,
    ).update(possible_brigading=True)
    return True


def submit_user_report(
    *,
    reporting_user: User,
    offending_username: str,
    reason_username: bool = False,
    reason_name: bool = False,
    reason_bio: bool = False,
    reason_other: bool = False,
    other_description: str = "",
) -> tuple[UserReport, bool]:
    """File (or merge into) the reporter's open report against a user.

    Returns ``(report, created)``.  ``created`` is ``False`` when an existing
    open report was coalesced and merged in place.
    """
    if not any((reason_username, reason_name, reason_bio, reason_other)):
        raise ReportValidationError("Select at least one reason.")

    description = sanitize_plain_text(other_description, limit=OTHER_DESCRIPTION_MAX)
    if reason_other and not description:
        raise ReportValidationError("Please describe the issue for 'Other'.")

    offender = resolve_offender(offending_username)
    if offender.pk == reporting_user.pk:
        raise ReportValidationError("You cannot report yourself.")
    if getattr(offender, "is_staff", False):
        raise ReportValidationError("This account cannot be reported.")

    repeat_offender = is_repeat_offender(offender)

    with transaction.atomic():
        existing = (
            UserReport.objects.select_for_update()
            .filter(
                reporting_user=reporting_user,
                offending_user=offender,
                status__in=OPEN_REPORT_STATUSES,
            )
            .order_by("-created_at")
            .first()
        )

        if existing is None:
            report = UserReport.objects.create(
                offending_user=offender,
                reporting_user=reporting_user,
                reason_username=reason_username,
                reason_name=reason_name,
                reason_bio=reason_bio,
                reason_other=reason_other,
                other_description=description,
                repeat_offender_at_submission=repeat_offender,
            )
            created = True
        else:
            report = existing
            report.reason_username = report.reason_username or reason_username
            report.reason_name = report.reason_name or reason_name
            report.reason_bio = report.reason_bio or reason_bio
            report.reason_other = report.reason_other or reason_other
            if description:
                report.other_description = description
            report.repeat_offender_at_submission = (
                report.repeat_offender_at_submission or repeat_offender
            )
            report.save()
            created = False

        if _flag_brigading(offender):
            report.possible_brigading = True
            report.save(update_fields=["possible_brigading", "updated_at"])

    return report, created


# ---------------------------------------------------------------------------
# Moderation actions
# ---------------------------------------------------------------------------


def _log_action(
    report: UserReport, *, actor, new_status: str, reason: str
) -> UserReport:
    report.status = new_status
    report.action_reason = sanitize_plain_text(reason, limit=250)
    report.actioned_by = actor
    report.actioned_at = timezone.now()
    report.save(
        update_fields=[
            "status",
            "action_reason",
            "actioned_by",
            "actioned_at",
            "updated_at",
        ]
    )
    return report


def dismiss_report(report: UserReport, *, actor) -> UserReport:
    """Dismiss a report without penalising the offender."""
    return _log_action(
        report,
        actor=actor,
        new_status=ReportStatus.DISMISSED,
        reason=report.action_reason or "Dismissed by moderator.",
    )


def enforce_username_change(report: UserReport, *, actor, reason: str) -> UserReport:
    """Force the offender to pick a new username on their next request."""
    return _log_action(
        report,
        actor=actor,
        new_status=ReportStatus.PENDING_USERNAME_CHANGE,
        reason=reason,
    )


def enforce_bio_change(report: UserReport, *, actor, reason: str) -> UserReport:
    """Force the offender to edit their name/bio on their next request."""
    return _log_action(
        report,
        actor=actor,
        new_status=ReportStatus.PENDING_BIO_CHANGE,
        reason=reason,
    )


def schedule_permanent_ban(
    report: UserReport, *, actor, ban_reason: str
) -> ScheduledAccountDeletion:
    """Lock, revoke, email, and schedule a hard purge three hours out."""
    reason = sanitize_plain_text(ban_reason, limit=250)
    if not reason:
        raise ReportValidationError("A ban reason is required.")

    offender = report.offending_user
    now = timezone.now()

    with transaction.atomic():
        _log_action(
            report,
            actor=actor,
            new_status=ReportStatus.SCHEDULED_FOR_DELETION,
            reason=reason,
        )

        revoke_all_user_sessions(offender.pk)
        if offender.is_active:
            offender.is_active = False
            offender.save(update_fields=["is_active"])

        deletion, _ = ScheduledAccountDeletion.objects.update_or_create(
            user=offender,
            defaults={
                "user_email_snapshot": offender.email or "",
                "offending_username_snapshot": offender.username,
                "ban_reason": reason,
                "authorized_by": actor,
                "scheduled_for": now + PERMABAN_DELAY,
                "executed": False,
            },
        )

    send_permaban_notice(
        recipient_email=offender.email or "",
        username=offender.username,
        ban_reason=reason,
        reasons=report.reasons(),
    )
    return deletion


# ---------------------------------------------------------------------------
# Lockout & remediation
# ---------------------------------------------------------------------------


def active_lockout_status(user: User) -> str | None:
    """Return the most recent lockout status governing *user*, or ``None``."""
    report = (
        UserReport.objects.filter(
            offending_user=user,
            status__in=LOCKOUT_REPORT_STATUSES,
        )
        .order_by("-updated_at")
        .first()
    )
    return report.status if report is not None else None


def _resolve_lockout_reports(user: User, status: str) -> int:
    return UserReport.objects.filter(offending_user=user, status=status).update(
        status=ReportStatus.RESOLVED,
        actioned_at=timezone.now(),
        updated_at=timezone.now(),
    )


def username_remediation_target(user: User) -> UserReport | None:
    """Return the governing report when the user must change their username."""
    return UserReport.objects.filter(
        offending_user=user,
        status=ReportStatus.PENDING_USERNAME_CHANGE,
    ).first()


def complete_username_remediation(
    user: User,
    *,
    new_username: str,
    new_password: str,
) -> User:
    """Apply a forced username + password rotation and resolve the report."""
    candidate = (new_username or "").strip()
    if not USERNAME_REGEX.match(candidate):
        raise ReportValidationError(USERNAME_FORMAT_MESSAGE)
    if candidate.lower() == user.username.lower():
        raise ReportValidationError("Choose a different username.")
    if User.objects.filter(username__iexact=candidate).exclude(pk=user.pk).exists():
        raise ReportValidationError("That username is already taken.")
    if user.check_password(new_password):
        raise ReportValidationError("Choose a password you have not used here before.")

    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise ReportValidationError(" ".join(exc.messages)) from exc

    with transaction.atomic():
        user.username = candidate
        user.set_password(new_password)
        user.save(update_fields=["username", "password"])
        _resolve_lockout_reports(user, ReportStatus.PENDING_USERNAME_CHANGE)

    return user


def complete_bio_remediation(user: User) -> int:
    """Resolve the forced name/bio-change report(s) after a profile save."""
    return _resolve_lockout_reports(user, ReportStatus.PENDING_BIO_CHANGE)


__all__ = [
    "BRIGADING_THRESHOLD",
    "BRIGADING_WINDOW",
    "PERMABAN_DELAY",
    "ReportNotFoundError",
    "ReportValidationError",
    "active_lockout_status",
    "complete_bio_remediation",
    "complete_username_remediation",
    "dismiss_report",
    "enforce_bio_change",
    "enforce_username_change",
    "is_repeat_offender",
    "resolve_offender",
    "sanitize_plain_text",
    "schedule_permanent_ban",
    "submit_user_report",
    "username_remediation_target",
]
