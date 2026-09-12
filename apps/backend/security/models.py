"""
Security domain — admin perimeter catalogs (SBGC-108) and the user-reporting
moderation domain (SBGC-223).

The two ``managed = False`` registry models power read-only Admin catalogs and
have no tables.  ``UserReport`` and ``ScheduledAccountDeletion`` are real
persisted tables backing the reporting + remediation workflow.
"""

from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models


class ErrorRegistryEntry(models.Model):
    """Unmanaged virtual model exposing the canonical error-code registry.

    Renders from ``games.errors.ERROR_REGISTRY`` via
    ``security.admin.ErrorRegistryAdmin`` — nothing is ever persisted.
    """

    class Meta:
        managed = False
        verbose_name = "Error Registry"
        verbose_name_plural = "Error Registry"
        # A real ``security.view_errorregistryentry`` permission is created at
        # post_migrate so superusers always pass and moderators can be granted
        # read access through the Admin group/permission picker (SBGC-108).
        default_permissions = ("view",)

    def __str__(self) -> str:
        return "Error Registry"


class DependencyRegistryEntry(models.Model):
    """Unmanaged virtual model exposing the tech-stack dependency catalog.

    Renders from ``security.dependencies.TECH_STACK_REGISTRY`` via the
    staff-guarded catalog view — nothing is ever persisted.
    """

    class Meta:
        managed = False
        verbose_name = "Tech Stack Registry"
        verbose_name_plural = "Tech Stack Registry"
        # Real ``security.view_dependencyregistryentry`` permission (SBGC-108).
        default_permissions = ("view",)

    def __str__(self) -> str:
        return "Tech Stack Registry"


# ---------------------------------------------------------------------------
# User reporting & moderation — SBGC-223
# ---------------------------------------------------------------------------


class ReportReason(models.TextChoices):
    OFFENSIVE_USERNAME = (
        "offensive_username",
        "Offensive / Inappropriate Username",
    )
    OFFENSIVE_NAME = (
        "offensive_name",
        "Offensive / Inappropriate First / Last Name",
    )
    OFFENSIVE_BIO = "offensive_bio", "Offensive / Inappropriate Bio"
    OTHER = "other", "Other"


class ReportStatus(models.TextChoices):
    PENDING_REVIEW = "pending_review", "Pending Review"
    PENDING_USERNAME_CHANGE = (
        "pending_username_change",
        "Pending Username Change",
    )
    PENDING_BIO_CHANGE = (
        "pending_bio_change",
        "Pending First Name / Last Name / Bio Change",
    )
    SCHEDULED_FOR_DELETION = (
        "scheduled_for_deletion",
        "Scheduled for Permanent Ban / Account Deletion",
    )
    RESOLVED = "resolved", "Resolved"
    DISMISSED = "dismissed", "Dismissed"


#: Statuses that keep a report "open" for coalescing purposes.
OPEN_REPORT_STATUSES = frozenset(
    {
        ReportStatus.PENDING_REVIEW,
        ReportStatus.PENDING_USERNAME_CHANGE,
        ReportStatus.PENDING_BIO_CHANGE,
        ReportStatus.SCHEDULED_FOR_DELETION,
    }
)

#: Statuses that lock the offender out of ordinary navigation.
LOCKOUT_REPORT_STATUSES = frozenset(
    {
        ReportStatus.PENDING_USERNAME_CHANGE,
        ReportStatus.PENDING_BIO_CHANGE,
        ReportStatus.SCHEDULED_FOR_DELETION,
    }
)


class UserReport(models.Model):
    """One community report filed against a user (SBGC-223).

    A ``(reporting_user, offending_user)`` pair coalesces into a single open
    report: repeat submissions merge their reason flags instead of creating
    duplicate triage rows.  ``possible_brigading`` and
    ``repeat_offender_at_submission`` are computed snapshots captured at
    ingestion time.
    """

    offending_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_received",
        db_index=True,
    )
    reporting_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_filed",
        db_index=True,
    )

    reason_username = models.BooleanField(default=False)
    reason_name = models.BooleanField(default=False)
    reason_bio = models.BooleanField(default=False)
    reason_other = models.BooleanField(default=False)
    other_description = models.CharField(
        max_length=250,
        blank=True,
        default="",
        validators=[MaxLengthValidator(250)],
        help_text="Plain text description if 'Other' was selected.",
    )

    status = models.CharField(
        max_length=48,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING_REVIEW,
        db_index=True,
    )
    possible_brigading = models.BooleanField(
        default=False,
        db_index=True,
        help_text="System-flagged when a sudden spike in reports occurs.",
    )
    repeat_offender_at_submission = models.BooleanField(
        default=False,
        help_text=(
            "Snapshot flag indicating whether the offender had prior "
            "non-pending reports."
        ),
    )

    action_reason = models.CharField(
        max_length=250,
        blank=True,
        default="",
        help_text="Reason logged by staff when taking punitive action.",
    )
    actioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderation_actions_taken",
    )
    actioned_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "security_user_report"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["offending_user", "status"],
                name="idx_report_offender_status",
            ),
            models.Index(
                fields=["created_at", "offending_user"],
                name="idx_report_brigade_scan",
            ),
        ]

    def __str__(self) -> str:
        offender_id = self.offending_user_id  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
        return f"Report #{self.pk} against {offender_id}"

    def reasons(self) -> list[str]:
        """Return the human labels of every checked reason flag."""
        flags: tuple[tuple[bool, str], ...] = (
            (self.reason_username, str(ReportReason.OFFENSIVE_USERNAME.label)),
            (self.reason_name, str(ReportReason.OFFENSIVE_NAME.label)),
            (self.reason_bio, str(ReportReason.OFFENSIVE_BIO.label)),
            (self.reason_other, str(ReportReason.OTHER.label)),
        )
        return [label for checked, label in flags if checked]


class ScheduledAccountDeletion(models.Model):
    """A permaban whose hard purge runs three hours after the decision."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="deletion_schedule",
    )
    user_email_snapshot = models.EmailField(
        help_text="Retained email to notify the offender upon ban execution.",
    )
    offending_username_snapshot = models.CharField(max_length=150)
    ban_reason = models.CharField(max_length=250)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    scheduled_for = models.DateTimeField(
        db_index=True,
        help_text="Exact timestamp when the hard purge runs (T + 3 hours).",
    )
    executed = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "security_scheduled_account_deletion"

    def __str__(self) -> str:
        return f"Deletion of {self.offending_username_snapshot} at {self.scheduled_for}"
