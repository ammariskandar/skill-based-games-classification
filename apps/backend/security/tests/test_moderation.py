"""
User-reporting, moderation & remediation tests — SBGC-223.

Covers the ingestion/deduplication boundary, the anti-brigading and
repeat-offender heuristics, the moderation Admin desk (dismiss + take-action
interventions), the lockout middleware, the forced-remediation handshakes, and
the three-hour async purge command.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from security.admin import UserReportAdmin
from security.models import (
    ReportStatus,
    ScheduledAccountDeletion,
    UserReport,
)
from security.services.reporting import (
    ReportValidationError,
    complete_username_remediation,
    sanitize_plain_text,
    submit_user_report,
)

REPORT_URL = "/api/v1/security/reports/user"
REMEDIATE_URL = "/api/v1/security/remediate/username"


def _user(username: str, **kwargs) -> User:
    defaults = {"email": f"{username}@example.com", "password": "pw-strong-123"}
    defaults.update(kwargs)
    return User.objects.create_user(username=username, **defaults)


def _submit(reporter: User, offender: User, **kwargs) -> tuple[UserReport, bool]:
    return submit_user_report(
        reporting_user=reporter,
        offending_username=offender.username,
        **kwargs,
    )


def _bulk_open_reports(offender: User, count: int, *, prefix: str = "filer") -> None:
    """Create *count* already-open reports from distinct reporters."""
    reporters = [User(username=f"{prefix}-{i}") for i in range(count)]
    User.objects.bulk_create(reporters)
    UserReport.objects.bulk_create(
        [
            UserReport(
                offending_user=offender,
                reporting_user=reporter,
                reason_username=True,
            )
            for reporter in reporters
        ]
    )


# ---------------------------------------------------------------------------
# Ingestion API & validation
# ---------------------------------------------------------------------------


class ReportIngestionApiTests(TestCase):
    def setUp(self):
        self.reporter = _user("reporter")
        self.offender = _user("offender")

    def _post(self, payload: dict, client: Client | None = None):
        client = client or self.client
        client.force_login(self.reporter)
        return client.post(
            REPORT_URL,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_valid_report_creates_row_and_returns_ack(self):
        response = self._post(
            {"offending_username": "offender", "reason_username": True}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"success": True, "message": "Report submitted successfully."},
        )
        row = UserReport.objects.get()
        self.assertEqual(row.offending_user, self.offender)
        self.assertEqual(row.reporting_user, self.reporter)
        self.assertTrue(row.reason_username)
        self.assertEqual(row.status, ReportStatus.PENDING_REVIEW)

    def test_unauthenticated_report_is_rejected(self):
        response = Client().post(
            REPORT_URL,
            data=json.dumps(
                {"offending_username": "offender", "reason_username": True}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(UserReport.objects.count(), 0)

    def test_self_report_is_rejected(self):
        response = self._post(
            {"offending_username": "reporter", "reason_username": True}
        )
        self.assertEqual(response.status_code, 422)

    def test_unknown_offender_is_not_found(self):
        response = self._post({"offending_username": "ghost", "reason_username": True})
        self.assertEqual(response.status_code, 404)

    def test_no_reason_selected_is_rejected(self):
        response = self._post({"offending_username": "offender"})
        self.assertEqual(response.status_code, 422)

    def test_other_requires_a_description(self):
        response = self._post({"offending_username": "offender", "reason_other": True})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(UserReport.objects.count(), 0)

    def test_other_description_rejects_angle_brackets(self):
        response = self._post(
            {
                "offending_username": "offender",
                "reason_other": True,
                "other_description": "<script>alert(1)</script>",
            }
        )
        self.assertEqual(response.status_code, 422)

    def test_other_description_over_250_is_rejected_by_schema(self):
        response = self._post(
            {
                "offending_username": "offender",
                "reason_other": True,
                "other_description": "x" * 251,
            }
        )
        self.assertEqual(response.status_code, 422)

    def test_unknown_field_is_rejected(self):
        response = self._post(
            {
                "offending_username": "offender",
                "reason_username": True,
                "internal_id": 3,
            }
        )
        self.assertEqual(response.status_code, 422)

    def test_staff_account_cannot_be_reported(self):
        staff = _user("staff-target", is_staff=True)
        response = self._post(
            {"offending_username": staff.username, "reason_username": True}
        )
        self.assertEqual(response.status_code, 422)


# ---------------------------------------------------------------------------
# Deduplication / coalescing
# ---------------------------------------------------------------------------


class DeduplicationTests(TestCase):
    def setUp(self):
        self.reporter = _user("dedup-reporter")
        self.offender = _user("dedup-offender")

    def test_repeated_filings_coalesce_into_one_open_report(self):
        _, created_1 = _submit(self.reporter, self.offender, reason_username=True)
        _, created_2 = _submit(self.reporter, self.offender, reason_bio=True)
        report, created_3 = _submit(self.reporter, self.offender, reason_name=True)

        self.assertTrue(created_1)
        self.assertFalse(created_2)
        self.assertFalse(created_3)
        self.assertEqual(UserReport.objects.count(), 1)
        self.assertTrue(report.reason_username)
        self.assertTrue(report.reason_bio)
        self.assertTrue(report.reason_name)

    def test_coalesce_updates_existing_description(self):
        _submit(
            self.reporter,
            self.offender,
            reason_other=True,
            other_description="First note",
        )
        report, _ = _submit(
            self.reporter,
            self.offender,
            reason_other=True,
            other_description="Second note",
        )
        report.refresh_from_db()
        self.assertEqual(report.other_description, "Second note")
        self.assertEqual(UserReport.objects.count(), 1)

    def test_closed_report_allows_a_fresh_open_row(self):
        UserReport.objects.create(
            offending_user=self.offender,
            reporting_user=self.reporter,
            reason_username=True,
            status=ReportStatus.DISMISSED,
        )
        _, created = _submit(self.reporter, self.offender, reason_bio=True)
        self.assertTrue(created)
        self.assertEqual(UserReport.objects.count(), 2)

    def test_distinct_reporters_each_get_their_own_row(self):
        other = _user("dedup-other-reporter")
        _submit(self.reporter, self.offender, reason_username=True)
        _submit(other, self.offender, reason_bio=True)
        self.assertEqual(UserReport.objects.count(), 2)


# ---------------------------------------------------------------------------
# Anti-brigading & repeat offender
# ---------------------------------------------------------------------------


class AntiAbuseHeuristicTests(TestCase):
    def setUp(self):
        self.offender = _user("abuse-target")

    def test_burst_flags_every_open_report_in_the_window(self):
        _bulk_open_reports(self.offender, 104, prefix="brigade")
        incoming_reporter = _user("brigade-incoming")

        report, _ = _submit(incoming_reporter, self.offender, reason_username=True)

        self.assertTrue(report.possible_brigading)
        self.assertEqual(
            UserReport.objects.filter(
                offending_user=self.offender, possible_brigading=True
            ).count(),
            105,
        )

    def test_reports_below_threshold_are_not_flagged(self):
        _bulk_open_reports(self.offender, 10, prefix="quiet")
        report, _ = _submit(
            _user("quiet-incoming"), self.offender, reason_username=True
        )
        self.assertFalse(report.possible_brigading)

    def test_prior_dismissed_report_flags_repeat_offender(self):
        UserReport.objects.create(
            offending_user=self.offender,
            reporting_user=_user("history-dismissed"),
            reason_bio=True,
            status=ReportStatus.DISMISSED,
        )
        report, _ = _submit(
            _user("new-reporter-dismissed"), self.offender, reason_username=True
        )
        self.assertTrue(report.repeat_offender_at_submission)

    def test_prior_resolved_report_flags_repeat_offender(self):
        UserReport.objects.create(
            offending_user=self.offender,
            reporting_user=_user("history-resolved"),
            reason_bio=True,
            status=ReportStatus.RESOLVED,
        )
        report, _ = _submit(
            _user("new-reporter-resolved"), self.offender, reason_username=True
        )
        self.assertTrue(report.repeat_offender_at_submission)

    def test_only_pending_history_is_not_a_repeat_offender(self):
        UserReport.objects.create(
            offending_user=self.offender,
            reporting_user=_user("history-pending"),
            reason_bio=True,
            status=ReportStatus.PENDING_REVIEW,
        )
        report, _ = _submit(
            _user("new-reporter-pending"), self.offender, reason_username=True
        )
        self.assertFalse(report.repeat_offender_at_submission)


# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------


class SanitizationTests(TestCase):
    def test_angle_brackets_are_rejected(self):
        with self.assertRaises(ReportValidationError):
            sanitize_plain_text("<b>bold</b>", limit=250)

    def test_control_codes_are_stripped(self):
        self.assertEqual(
            sanitize_plain_text("a\x00b\x1fc\x7fd", limit=250),
            "abcd",
        )

    def test_value_is_trimmed_and_capped(self):
        self.assertEqual(sanitize_plain_text("  spaced  ", limit=250), "spaced")
        self.assertEqual(len(sanitize_plain_text("y" * 400, limit=250)), 250)

    def test_empty_input_returns_empty_string(self):
        self.assertEqual(sanitize_plain_text(None, limit=250), "")
        self.assertEqual(sanitize_plain_text("   ", limit=250), "")


# ---------------------------------------------------------------------------
# Lockout middleware
# ---------------------------------------------------------------------------


class LockoutMiddlewareTests(TestCase):
    def _locked_user(self, status: str) -> User:
        user = _user(f"locked-{status}")
        UserReport.objects.create(
            offending_user=user,
            reporting_user=_user(f"reporter-for-{status}"),
            reason_username=True,
            status=status,
        )
        return user

    def test_username_lockout_blocks_generic_api(self):
        user = self._locked_user(ReportStatus.PENDING_USERNAME_CHANGE)
        self.client.force_login(user)
        response = self.client.get("/api/v1/games/anything")
        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertEqual(body["error"]["code"], "MODERATION_LOCKOUT")
        self.assertEqual(body["lockout"], "pending_username_change")

    def test_username_lockout_blocks_users_api(self):
        user = self._locked_user(ReportStatus.PENDING_USERNAME_CHANGE)
        self.client.force_login(user)
        response = self.client.get(f"/api/v1/users/{user.username}")
        self.assertEqual(response.status_code, 403)

    def test_username_lockout_allows_auth_and_remediation(self):
        user = self._locked_user(ReportStatus.PENDING_USERNAME_CHANGE)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/v1/auth/status").status_code, 200)
        self.assertEqual(self.client.get(REMEDIATE_URL).status_code, 200)

    def test_bio_lockout_allows_users_api_but_blocks_others(self):
        user = self._locked_user(ReportStatus.PENDING_BIO_CHANGE)
        self.client.force_login(user)
        self.assertNotEqual(
            self.client.get(f"/api/v1/users/{user.username}").status_code, 403
        )
        self.assertEqual(self.client.get("/api/v1/games/anything").status_code, 403)

    def test_scheduled_deletion_blocks_generic_api(self):
        user = self._locked_user(ReportStatus.SCHEDULED_FOR_DELETION)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/v1/games/anything").status_code, 403)

    def test_staff_bypasses_lockout(self):
        user = _user("staff-locked", is_staff=True)
        UserReport.objects.create(
            offending_user=user,
            reporting_user=_user("staff-reporter"),
            reason_username=True,
            status=ReportStatus.PENDING_USERNAME_CHANGE,
        )
        self.client.force_login(user)
        self.assertNotEqual(self.client.get("/api/v1/games/anything").status_code, 403)

    def test_unlocked_user_is_unaffected(self):
        self.client.force_login(_user("free-user"))
        self.assertNotEqual(self.client.get("/api/v1/games/anything").status_code, 403)

    def test_anonymous_api_request_is_unaffected(self):
        response = Client().get("/api/v1/games/anything")
        self.assertNotEqual(response.status_code, 403)

    def test_lockout_endpoint_reports_status_and_is_reachable(self):
        user = self._locked_user(ReportStatus.PENDING_USERNAME_CHANGE)
        self.client.force_login(user)
        response = self.client.get("/api/v1/security/lockout")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending_username_change")
        self.assertEqual(response.json()["username"], user.username)

    def test_lockout_endpoint_returns_null_when_unlocked(self):
        self.client.force_login(_user("lockout-clean"))
        response = self.client.get("/api/v1/security/lockout")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["status"])

    def test_lockout_endpoint_requires_authentication(self):
        self.assertEqual(Client().get("/api/v1/security/lockout").status_code, 401)


# ---------------------------------------------------------------------------
# Forced remediation handshakes
# ---------------------------------------------------------------------------


class RemediationServiceTests(TestCase):
    def setUp(self):
        self.user = _user("remediate-me", password="old-password-123")
        self.report = UserReport.objects.create(
            offending_user=self.user,
            reporting_user=_user("remediation-reporter"),
            reason_username=True,
            status=ReportStatus.PENDING_USERNAME_CHANGE,
        )

    def test_username_change_updates_credentials_and_resolves_report(self):
        updated = complete_username_remediation(
            self.user,
            new_username="clean-name",
            new_password="fresh-password-456",
        )
        self.assertEqual(updated.username, "clean-name")
        self.assertTrue(updated.check_password("fresh-password-456"))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ReportStatus.RESOLVED)

    def test_identical_username_is_rejected(self):
        with self.assertRaises(ReportValidationError):
            complete_username_remediation(
                self.user,
                new_username=self.user.username,
                new_password="fresh-password-456",
            )

    def test_taken_username_is_rejected(self):
        _user("already-taken")
        with self.assertRaises(ReportValidationError):
            complete_username_remediation(
                self.user,
                new_username="already-taken",
                new_password="fresh-password-456",
            )

    def test_invalid_username_format_is_rejected(self):
        with self.assertRaises(ReportValidationError):
            complete_username_remediation(
                self.user,
                new_username="ab",
                new_password="fresh-password-456",
            )

    def test_reused_password_is_rejected(self):
        with self.assertRaises(ReportValidationError):
            complete_username_remediation(
                self.user,
                new_username="clean-name",
                new_password="old-password-123",
            )

    def test_bio_remediation_resolves_only_bio_lockouts(self):
        from security.services.reporting import complete_bio_remediation

        bio_user = _user("bio-remediate")
        bio_report = UserReport.objects.create(
            offending_user=bio_user,
            reporting_user=_user("bio-reporter"),
            reason_bio=True,
            status=ReportStatus.PENDING_BIO_CHANGE,
        )
        self.assertEqual(complete_bio_remediation(bio_user), 1)
        bio_report.refresh_from_db()
        self.assertEqual(bio_report.status, ReportStatus.RESOLVED)


class RemediationApiTests(TestCase):
    def setUp(self):
        self.user = _user("api-remediate", password="old-password-123")
        self.report = UserReport.objects.create(
            offending_user=self.user,
            reporting_user=_user("api-remediation-reporter"),
            reason_username=True,
            status=ReportStatus.PENDING_USERNAME_CHANGE,
        )

    def test_context_returns_current_identity(self):
        self.client.force_login(self.user)
        response = self.client.get(REMEDIATE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], self.user.username)

    def test_context_without_lockout_is_forbidden(self):
        self.client.force_login(_user("not-locked"))
        self.assertEqual(self.client.get(REMEDIATE_URL).status_code, 403)

    def test_successful_remediation_keeps_the_session(self):
        self.client.force_login(self.user)
        response = self.client.post(
            REMEDIATE_URL,
            data=json.dumps(
                {
                    "new_username": "api-clean-name",
                    "new_password": "fresh-password-456",
                    "confirm_password": "fresh-password-456",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "api-clean-name")
        # The password rotation cycles the session key, so Django must emit a
        # replacement sessionid cookie for the BFF to relay (SBGC-223).
        self.assertIn("sessionid", response.cookies)
        # The password rotation re-hashes the active session instead of logging
        # the user out of the request that performed it.
        status_response = self.client.get("/api/v1/auth/status")
        self.assertTrue(status_response.json()["authenticated"])

    def test_mismatched_confirmation_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            REMEDIATE_URL,
            data=json.dumps(
                {
                    "new_username": "api-clean-name",
                    "new_password": "fresh-password-456",
                    "confirm_password": "different-password-789",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

    def test_weak_password_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            REMEDIATE_URL,
            data=json.dumps(
                {
                    "new_username": "api-clean-name",
                    "new_password": "short",
                    "confirm_password": "short",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)


# ---------------------------------------------------------------------------
# Moderation Admin desk
# ---------------------------------------------------------------------------


class ModerationAdminTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="moderator-owner",
            email="owner@example.com",
            password="owner-password-123",
        )
        self.reporter = _user("admin-reporter")
        self.offender = _user("admin-offender")
        self.report = UserReport.objects.create(
            offending_user=self.offender,
            reporting_user=self.reporter,
            reason_username=True,
            other_description="Offensive handle",
        )
        self.model_admin = UserReportAdmin(UserReport, AdminSite())

    def _take_action_url(self) -> str:
        return f"/test-admin/security/userreport/{self.report.pk}/take-action/"

    def test_admin_desk_exposes_expected_columns(self):
        self.assertIn("offending_link", self.model_admin.list_display)
        self.assertIn("brigading_badge", self.model_admin.list_display)
        self.assertIn("status", self.model_admin.list_filter)

    def test_changelist_renders_action_and_alert_badges(self):
        self.report.possible_brigading = True
        self.report.repeat_offender_at_submission = True
        self.report.reason_bio = True
        self.report.reason_other = True
        self.report.save(
            update_fields=[
                "possible_brigading",
                "repeat_offender_at_submission",
                "reason_bio",
                "reason_other",
            ]
        )
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:security_userreport_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BRIGADING SUSPECTED")
        self.assertContains(response, "Take action")
        # Reason badges must render as markup, not escaped HTML.
        self.assertContains(response, "border-radius:9999px")
        self.assertNotContains(response, "&lt;span")
        self.assertContains(response, "Offensive / Inappropriate Bio")
        self.assertContains(response, "Other")

    def test_take_action_page_renders(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self._take_action_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Permanently Ban")
        self.assertContains(response, self.offender.username)

    def test_action_requires_staff(self):
        self.client.force_login(self.reporter)
        response = self.client.get(self._take_action_url())
        self.assertIn(response.status_code, (302, 403))

    def test_dismiss_intervention(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            self._take_action_url(), {"intervention": "dismiss"}
        )
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ReportStatus.DISMISSED)
        self.assertEqual(self.report.actioned_by, self.superuser)

    def test_username_intervention(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            self._take_action_url(),
            {"intervention": "username", "action_reason": "Offensive handle"},
        )
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ReportStatus.PENDING_USERNAME_CHANGE)

    def test_bio_intervention(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            self._take_action_url(),
            {"intervention": "bio", "action_reason": "Offensive bio"},
        )
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ReportStatus.PENDING_BIO_CHANGE)

    def test_permaban_guard_rejects_wrong_phrase(self):
        self.client.force_login(self.superuser)
        for phrase in ("yes", "ban", "PERMABAN"):
            response = self.client.post(
                self._take_action_url(),
                {
                    "intervention": "permaban",
                    "confirm_phrase": phrase,
                    "ban_reason": "Repeated abuse",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.report.refresh_from_db()
            self.assertEqual(self.report.status, ReportStatus.PENDING_REVIEW)
            self.assertEqual(ScheduledAccountDeletion.objects.count(), 0)

    def test_permaban_with_correct_phrase_schedules_deletion(self):
        self.client.force_login(self.superuser)
        before = timezone.now()
        response = self.client.post(
            self._take_action_url(),
            {
                "intervention": "permaban",
                "confirm_phrase": "permaban",
                "ban_reason": "Repeated abuse",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ReportStatus.SCHEDULED_FOR_DELETION)

        self.offender.refresh_from_db()
        self.assertFalse(self.offender.is_active)

        schedule = ScheduledAccountDeletion.objects.get()
        self.assertEqual(schedule.user, self.offender)
        self.assertFalse(schedule.executed)
        self.assertGreaterEqual(
            schedule.scheduled_for, before + timedelta(hours=3) - timedelta(minutes=1)
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.offender.email])

    def test_permaban_requires_a_reason(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            self._take_action_url(),
            {
                "intervention": "permaban",
                "confirm_phrase": "permaban",
                "ban_reason": "   ",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ScheduledAccountDeletion.objects.count(), 0)

    def test_invalid_intervention_is_rejected(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            self._take_action_url(), {"intervention": "nonsense"}
        )
        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ReportStatus.PENDING_REVIEW)


# ---------------------------------------------------------------------------
# Three-hour purge command
# ---------------------------------------------------------------------------


class ScheduledDeletionCommandTests(TestCase):
    def setUp(self):
        self.offender = _user("purge-target")
        self.reporters = [_user("purge-reporter-1"), _user("purge-reporter-2")]
        for reporter in self.reporters:
            UserReport.objects.create(
                offending_user=self.offender,
                reporting_user=reporter,
                reason_username=True,
            )

    def _schedule(self, *, due: bool) -> ScheduledAccountDeletion:
        when = timezone.now() + (timedelta(minutes=-5) if due else timedelta(hours=3))
        return ScheduledAccountDeletion.objects.create(
            user=self.offender,
            user_email_snapshot=self.offender.email,
            offending_username_snapshot=self.offender.username,
            ban_reason="Repeated abuse",
            scheduled_for=when,
        )

    def test_due_schedule_purges_account_and_thanks_reporters(self):
        self._schedule(due=True)
        mail.outbox.clear()

        call_command("process_scheduled_account_deletions")

        self.assertFalse(User.objects.filter(pk=self.offender.pk).exists())
        self.assertEqual(ScheduledAccountDeletion.objects.count(), 0)
        recipients = {message.to[0] for message in mail.outbox}
        self.assertEqual(recipients, {reporter.email for reporter in self.reporters})

    def test_future_schedule_is_left_untouched(self):
        self._schedule(due=False)
        mail.outbox.clear()

        call_command("process_scheduled_account_deletions")

        self.assertTrue(User.objects.filter(pk=self.offender.pk).exists())
        self.assertEqual(ScheduledAccountDeletion.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_executed_schedule_is_not_reprocessed(self):
        schedule = self._schedule(due=True)
        schedule.executed = True
        schedule.save(update_fields=["executed"])
        mail.outbox.clear()

        call_command("process_scheduled_account_deletions")

        self.assertTrue(User.objects.filter(pk=self.offender.pk).exists())
        self.assertEqual(len(mail.outbox), 0)
