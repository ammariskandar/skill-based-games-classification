"""
Adaptive zero-trust admin perimeter tests — SBGC-106.

Covers admin path obfuscation, the VPN/datacenter subnet matcher, the
waiting-room state machine, superuser approval/rejection, owner-exclusive
reactivation, and high-risk write / delete throttling.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.messages.storage.cookie import CookieStorage
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from security.admin_hooks import HardenedUserAdmin
from security.ip_engine import IPSubnetMatcher
from security.models_cache import (
    APPROVED,
    CHALLENGE_KEY_PREFIX,
    PENDING,
    REJECTED,
    get_challenge,
    is_ip_whitelisted,
    is_user_security_locked,
    set_user_security_locked,
)
from security.throttling_admin import HardenedModelAdmin


class AdminObfuscationTests(TestCase):
    def test_obfuscated_admin_path_resolves(self):
        response = self.client.get(reverse("admin:login"))
        self.assertEqual(response.status_code, 200)
        # The reCAPTCHA v3 challenge is rendered because RECAPTCHA_SITE_KEY is
        # set in test settings.
        self.assertContains(response, "grecaptcha")

    def test_standard_admin_path_returns_404(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 404)


class VPNSubnetMatcherTests(TestCase):
    def test_vpn_subnet_matcher_accuracy(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "vpn-ipv4.txt").write_text(
                "# test\n198.51.100.0/24\n10.0.0.0/8\n"
            )
            (data_dir / "vpn-ipv6.txt").write_text("# test\n2001:db8::/32\n")

            matcher = IPSubnetMatcher()
            matcher.load_subnets(data_dir)

            self.assertTrue(matcher.is_vpn_or_datacenter("198.51.100.42"))
            self.assertTrue(matcher.is_vpn_or_datacenter("10.255.255.255"))
            self.assertTrue(matcher.is_vpn_or_datacenter("2001:db8::1"))
            self.assertFalse(matcher.is_vpn_or_datacenter("8.8.8.8"))
            self.assertFalse(matcher.is_vpn_or_datacenter("2001:4860:4860::8888"))
            self.assertFalse(matcher.is_vpn_or_datacenter("not-an-ip"))


class VPNLoginChallengeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.superuser = User.objects.create_superuser(
            username="owner",
            email="owner@example.com",
            password="owner-pass-123",
        )
        self.staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="staff-pass-123",
            is_staff=True,
        )
        self.client = Client(REMOTE_ADDR="198.51.100.42")

    def _login_from_flagged_ip(self):
        with mock.patch("security.models_cache.is_flagged_ip", return_value=True):
            return self.client.post(
                reverse("admin:login"),
                {
                    "username": "staff",
                    "password": "staff-pass-123",
                    "recaptcha_token": "test-recaptcha-token",
                    "next": reverse("admin:index"),
                },
            )

    def _extract_review_token(self, body: str) -> str:
        marker = "?token="
        index = body.index(marker)
        return body[index + len(marker) :].strip().split()[0]

    def test_vpn_login_triggers_waiting_room(self):
        response = self._login_from_flagged_ip()
        self.assertEqual(response.status_code, 302)

        challenge_id = self.client.session["admin_vpn_challenge_id"]
        challenge = get_challenge(challenge_id)
        assert challenge is not None
        self.assertEqual(challenge["status"], PENDING)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Suspicious Admin Login", str(mail.outbox[0].subject))

        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("security/waiting-room/", response["Location"])

    def test_waiting_room_expiration_transitions_to_readonly(self):
        self._login_from_flagged_ip()
        challenge_id = self.client.session["admin_vpn_challenge_id"]

        challenge = get_challenge(challenge_id)
        assert challenge is not None
        challenge["read_only_at"] = 0
        cache.set(f"{CHALLENGE_KEY_PREFIX}{challenge_id}", challenge, timeout=3600)

        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Read-Only mode")

        response = self.client.post(reverse("admin:index"))
        self.assertEqual(response.status_code, 403)

    def test_superuser_approval_clears_gate(self):
        self._login_from_flagged_ip()
        challenge_id = self.client.session["admin_vpn_challenge_id"]
        token = self._extract_review_token(str(mail.outbox[0].body))

        reviewer = Client()
        reviewer.force_login(self.superuser)
        response = reviewer.post(
            reverse("security:review_login"),
            {"action": "approve", "token": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "APPROVED")

        challenge = get_challenge(challenge_id)
        assert challenge is not None
        self.assertEqual(challenge["status"], APPROVED)
        self.assertTrue(is_ip_whitelisted(self.staff.pk, "198.51.100.42"))

        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)

    def test_superuser_reject_locks_user(self):
        self._login_from_flagged_ip()
        challenge_id = self.client.session["admin_vpn_challenge_id"]
        token = self._extract_review_token(str(mail.outbox[0].body))

        reviewer = Client()
        reviewer.force_login(self.superuser)
        reviewer.post(
            reverse("security:review_login"),
            {"action": "reject", "token": token},
        )

        challenge = get_challenge(challenge_id)
        assert challenge is not None
        self.assertEqual(challenge["status"], REJECTED)

        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)
        self.assertTrue(is_user_security_locked(self.staff.pk))
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(DJANGO_OWNER_USERNAME="owner")
class OwnerExclusiveUnlockTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="owner-pass-123"
        )
        self.other = User.objects.create_superuser(
            username="other", email="other@example.com", password="other-pass-123"
        )
        self.victim = User.objects.create_user(
            username="victim", email="victim@example.com", password="victim-pass-123"
        )
        self.victim.is_active = False
        self.victim.save(update_fields=["is_active"])
        set_user_security_locked(self.victim.pk, "test")

    def _admin(self):
        return HardenedUserAdmin(User, admin.site)

    def _request(self, user):
        request = RequestFactory().post("/")
        request.user = user
        return request

    def test_owner_exclusive_unlock(self):
        modeladmin = self._admin()
        form = mock.Mock()
        form.changed_data = ["is_active"]

        # A non-owner superuser cannot reactivate a security-locked account.
        self.victim.is_active = True
        with self.assertRaises(PermissionDenied):
            modeladmin.save_model(
                self._request(self.other), self.victim, form, change=True
            )

        # The owner can reactivate and clears the lock marker.
        self.victim.is_active = True
        modeladmin.save_model(self._request(self.owner), self.victim, form, change=True)
        self.assertFalse(is_user_security_locked(self.victim.pk))


@override_settings(ADMIN_THROTTLING_ENABLED=True)
class ThrottlingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.editor = User.objects.create_user(
            username="editor",
            email="editor@example.com",
            password="editor-pass-123",
            is_staff=True,
        )

    def _request(self):
        request = RequestFactory().post("/")
        request.user = self.editor
        request._messages = CookieStorage(request)  # type: ignore[reportAttributeAccessIssue]
        return request

    def test_high_risk_action_throttling(self):
        modeladmin = HardenedUserAdmin(User, admin.site)
        request = self._request()
        form = mock.Mock()
        form.changed_data = []

        # First save passes and records the pacing timestamp.
        self.assertTrue(modeladmin._check_write_pacing(request))
        modeladmin.save_model(request, self.editor, form, change=True)

        # A second save within the cooldown is rejected.
        self.assertFalse(modeladmin._check_write_pacing(request))

    def test_delete_cooling_period(self):
        modeladmin = HardenedModelAdmin(User, admin.site)
        request = self._request()

        for _ in range(5):
            self.assertTrue(modeladmin._check_delete_quota(request, count=1))

        # The 6th delete is blocked and activates the 5-minute cooling period.
        self.assertFalse(modeladmin._check_delete_quota(request, count=1))
        self.assertIsNotNone(cache.get(f"admin_delete_cooling:{self.editor.pk}"))
