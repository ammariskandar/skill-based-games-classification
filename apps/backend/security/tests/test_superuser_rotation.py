"""
Superuser rotation & daily-login tracking tests — SBGC-186.

Covers the dual-superuser quota lifecycle: buffered daily login tracking,
inactivity demotion, moderator promotion with random tie-breaking, atomic
restoration on a returning superuser, the immutable Moderator group guard, and
the zero-moderator shortage path.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest import mock

from authentication.models import UserSecurityProfile
from config.testing import prod_test_env, run_manage
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings

from security.superuser_rotation import (
    evaluate_designated_superusers,
    flush_login_buffer_for_date,
    promote_moderator_for_inactive_superuser,
    restore_dormant_superuser_if_applicable,
)
from security.tracking import LOGIN_BUFFER_KEY, record_user_login_activity

_QUOTA_SETTINGS = {
    "DJANGO_OWNER_USERNAME": "owner",
    "DJANGO_SUPERUSER_1": "su1",
    "DJANGO_SUPERUSER_2": "su2",
    "MODERATOR_GROUP_NAME": "Moderator",
}


@override_settings(**_QUOTA_SETTINGS)
class RotationTestCase(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )
        self.su1 = User.objects.create_superuser(
            username="su1", email="su1@example.com", password="pw"
        )
        self.su2 = User.objects.create_superuser(
            username="su2", email="su2@example.com", password="pw"
        )
        # Default both designated superusers to recently active; tests opt into
        # inactivity via ``_make_inactive``.  Without a profile, ``last_login_date
        # is None`` would classify them as inactive.
        for superuser in (self.su1, self.su2):
            UserSecurityProfile.objects.create(
                user=superuser, last_login_date=date.today()
            )
        self.moderator_group, _ = Group.objects.get_or_create(name="Moderator")

    def _moderator(self, username: str, *, login_count: int = 0) -> User:
        user = User.objects.create_user(username=username, password="pw")
        user.groups.add(self.moderator_group)
        UserSecurityProfile.objects.create(user=user, daily_login_count=login_count)
        return user

    def _make_inactive(self, user: User, *, days: int = 200) -> None:
        profile, _ = UserSecurityProfile.objects.get_or_create(user=user)
        profile.last_login_date = date.today() - timedelta(days=days)
        profile.save(update_fields=["last_login_date"])

    def _non_owner_superusers(self) -> int:
        return (
            User.objects.filter(is_superuser=True, is_active=True)
            .exclude(username="owner")
            .count()
        )


@override_settings(**_QUOTA_SETTINGS)
class LoginBufferingTests(RotationTestCase):
    def setUp(self):
        super().setUp()
        # Buffering assertions use a profile-less user so the first flush
        # exercises the get_or_create + increment path unconditionally.
        self.fresh_user = User.objects.create_user(username="loginuser", password="pw")

    def test_distinct_day_is_counted_once(self):
        today = date.today()
        record_user_login_activity(self.fresh_user.pk)
        record_user_login_activity(self.fresh_user.pk)  # same day — deduped
        self.assertEqual(
            cache.get(LOGIN_BUFFER_KEY.format(date_str=today.isoformat())),
            [self.fresh_user.pk],
        )

        self.assertEqual(flush_login_buffer_for_date(today), 1)
        profile = UserSecurityProfile.objects.get(user=self.fresh_user)
        self.assertEqual(profile.daily_login_count, 1)
        self.assertEqual(profile.last_login_date, today)

        # A second flush of the already-consumed day is a no-op.
        self.assertEqual(flush_login_buffer_for_date(today), 0)
        profile.refresh_from_db()
        self.assertEqual(profile.daily_login_count, 1)

    def test_new_day_increments_cumulative_count(self):
        today = date.today()
        record_user_login_activity(self.fresh_user.pk)
        flush_login_buffer_for_date(today)

        # Simulate the next calendar day without real time: buffer directly.
        tomorrow = today + timedelta(days=1)
        cache.set(
            LOGIN_BUFFER_KEY.format(date_str=tomorrow.isoformat()),
            [self.fresh_user.pk],
        )
        self.assertEqual(flush_login_buffer_for_date(tomorrow), 1)

        profile = UserSecurityProfile.objects.get(user=self.fresh_user)
        self.assertEqual(profile.daily_login_count, 2)
        self.assertEqual(profile.last_login_date, tomorrow)

    def test_login_signal_wires_realtime_buffer(self):
        # force_login goes through django.contrib.auth.login(), firing the
        # user_logged_in receiver that buffers activity.
        self.client.force_login(self.su1)
        buffer = cache.get(LOGIN_BUFFER_KEY.format(date_str=date.today().isoformat()))
        self.assertIn(self.su1.pk, buffer or [])


@override_settings(**_QUOTA_SETTINGS)
class InactivityRotationTests(RotationTestCase):
    def test_inactive_designated_superuser_marked_dormant(self):
        self._make_inactive(self.su1, days=200)
        demoted = evaluate_designated_superusers(date.today())

        self.su1.refresh_from_db()
        self.assertFalse(self.su1.is_superuser)
        self.assertTrue(
            UserSecurityProfile.objects.get(user=self.su1).is_dormant_superuser
        )
        self.assertIn(self.su1, demoted)

    def test_active_superuser_is_not_rotated(self):
        demoted = evaluate_designated_superusers(date.today())
        self.assertEqual(demoted, [])
        self.su1.refresh_from_db()
        self.assertTrue(self.su1.is_superuser)

    def test_top_moderator_by_login_count_is_promoted(self):
        self._make_inactive(self.su1)
        top = self._moderator("top", login_count=5)
        other = self._moderator("other", login_count=3)

        evaluate_designated_superusers(date.today())

        top.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(top.is_superuser)
        self.assertTrue(
            UserSecurityProfile.objects.get(user=top).is_temporary_superuser
        )
        self.assertFalse(other.is_superuser)

    def test_tie_break_promotes_exactly_one_moderator(self):
        self._make_inactive(self.su1)
        first = self._moderator("first", login_count=4)
        second = self._moderator("second", login_count=4)

        result = promote_moderator_for_inactive_superuser(
            self.su1, UserSecurityProfile.objects.get(user=self.su1)
        )
        self.assertEqual(result, "promoted")

        first.refresh_from_db()
        second.refresh_from_db()
        promoted = [u for u in (first, second) if u.is_superuser]
        self.assertEqual(len(promoted), 1)

    def test_superuser_quota_never_exceeds_two(self):
        self._make_inactive(self.su1)
        self._make_inactive(self.su2)
        self._moderator("mod-a", login_count=2)
        self._moderator("mod-b", login_count=2)

        evaluate_designated_superusers(date.today())
        # Both designated superusers demoted; two moderators promoted.
        self.assertEqual(self._non_owner_superusers(), 2)

        # Returning dormant superuser collapses back toward the quota.
        self.su1.refresh_from_db()
        restore_dormant_superuser_if_applicable(self.su1)
        self.assertEqual(self._non_owner_superusers(), 1)
        self.su1.refresh_from_db()
        self.assertTrue(self.su1.is_superuser)


@override_settings(**_QUOTA_SETTINGS)
class RestorationTests(RotationTestCase):
    def test_restoration_demotes_temporary_and_restores_dormant(self):
        self._make_inactive(self.su1)
        moderator = self._moderator("mod-a", login_count=9)

        evaluate_designated_superusers(date.today())
        self.su1.refresh_from_db()
        self.assertFalse(self.su1.is_superuser)
        moderator.refresh_from_db()
        self.assertTrue(moderator.is_superuser)

        restored = restore_dormant_superuser_if_applicable(self.su1)
        self.assertTrue(restored)

        self.su1.refresh_from_db()
        moderator.refresh_from_db()
        self.assertTrue(self.su1.is_superuser)
        self.assertFalse(
            UserSecurityProfile.objects.get(user=self.su1).is_dormant_superuser
        )
        self.assertFalse(moderator.is_superuser)
        self.assertFalse(
            UserSecurityProfile.objects.get(user=moderator).is_temporary_superuser
        )

    def test_non_designated_user_is_ignored(self):
        regular = User.objects.create_user(username="regular", password="pw")
        self.assertFalse(restore_dormant_superuser_if_applicable(regular))


@override_settings(**_QUOTA_SETTINGS)
class ShortageTests(RotationTestCase):
    def test_zero_moderators_alerts_owner_and_changes_no_other_roles(self):
        self._make_inactive(self.su1)
        # Moderator group exists but has no eligible members.
        demoted = evaluate_designated_superusers(date.today())

        self.su1.refresh_from_db()
        self.assertFalse(self.su1.is_superuser)
        self.assertIn(self.su1, demoted)

        # No temporary superuser was created; su2 remains a superuser.
        self.assertFalse(
            UserSecurityProfile.objects.filter(is_temporary_superuser=True).exists()
        )
        self.su2.refresh_from_db()
        self.assertTrue(self.su2.is_superuser)

        self.assertTrue(any("no moderator" in m.subject.lower() for m in mail.outbox))


@override_settings(**_QUOTA_SETTINGS)
class GroupProtectionTests(RotationTestCase):
    def test_moderator_group_cannot_be_deleted(self):
        model_admin = admin.site._registry[Group]
        request = mock.Mock()
        request.user = self.owner
        self.assertFalse(
            model_admin.has_delete_permission(request, self.moderator_group)
        )
        # Other groups remain deletable.
        other = Group.objects.create(name="Other")
        self.assertTrue(model_admin.has_delete_permission(request, other))

    def test_moderator_group_cannot_be_renamed(self):
        model_admin = admin.site._registry[Group]
        request = mock.Mock()
        request.user = self.owner
        form = mock.Mock()
        form.changed_data = ["name"]

        self.moderator_group.name = "Renamed"
        with self.assertRaises(PermissionDenied):
            model_admin.save_model(request, self.moderator_group, form, change=True)


class ProductionQuotaGuardTests(TestCase):
    """SBGC-186 §2 — production requires distinct, non-empty quota handles."""

    def _run_production_check(self, **env_overrides):
        env = prod_test_env(**env_overrides)
        return run_manage("check", "--settings=config.settings.production", env=env)

    def test_missing_owner_rejected(self):
        proc = self._run_production_check(DJANGO_OWNER_USERNAME="")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("DJANGO_OWNER_USERNAME is required", proc.stderr)

    def test_duplicate_handles_rejected(self):
        proc = self._run_production_check(DJANGO_SUPERUSER_2="owner_test")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("distinct", proc.stderr)

    def test_valid_handles_accepted(self):
        proc = self._run_production_check()
        self.assertEqual(proc.returncode, 0, proc.stderr)
