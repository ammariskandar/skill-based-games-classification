"""
Security posture verification tests — SBGC-109.

Closes Epic SBGC-16 with app-layer assertions for the posture vectors that are
enforceable inside Django:

1. Responses never advertise a server or framework banner header, and the
   modern security headers configured in base.py are present.
2. The obfuscated admin login renders while the standard /admin/ path 404s
   (defence in depth; authorization remains the real boundary).
3. An unset DJANGO_OWNER_USERNAME fails closed — no account can be
   reactivated through a security lockout when the owner is not configured.
4. Least-privilege access on the Security registries: non-staff users are
   denied and the direct registry route requires the grantable permission.

Remaining vectors (supply-chain audits, migration drift, DatabaseCache table
provisioning) are enforced by scripts/verify-security-posture.sh.
"""

from __future__ import annotations

from unittest import mock

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse

from security.admin_hooks import HardenedUserAdmin
from security.models_cache import is_user_security_locked, set_user_security_locked


class HeaderPostureTests(TestCase):
    """Vector 1 — no banner leaks; modern security headers intact."""

    def test_responses_omit_server_and_powered_by_banners(self):
        # Django never adds these headers itself; this pins the invariant so a
        # future middleware or handler cannot regress it.
        admin_login = self.client.get(reverse("admin:login"))
        self.assertEqual(admin_login.status_code, 200)
        self.assertNotIn("Server", admin_login.headers)
        self.assertNotIn("X-Powered-By", admin_login.headers)

        # API 404 envelope responses are equally banner-free.
        api_miss = self.client.get("/api/v1/games/definitely-not-a-real-game-404/")
        self.assertEqual(api_miss.status_code, 404)
        self.assertNotIn("Server", api_miss.headers)
        self.assertNotIn("X-Powered-By", api_miss.headers)

    def test_modern_security_headers_present(self):
        # SBGC-105 header baseline applied to every response.
        response = self.client.get(reverse("admin:login"))
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(
            response.headers["Referrer-Policy"], "strict-origin-when-cross-origin"
        )
        self.assertEqual(
            response.headers["Cross-Origin-Opener-Policy"], "same-origin-allow-popups"
        )

    def test_obfuscated_admin_login_resolves_and_standard_admin_404s(self):
        # Defence in depth (SBGC-105/106): the standard path exposes nothing.
        self.assertEqual(self.client.get("/admin/login/").status_code, 404)
        login = self.client.get(reverse("admin:login"))
        self.assertEqual(login.status_code, 200)


@override_settings(DJANGO_OWNER_USERNAME="")
class OwnerEmptyDefaultTests(TestCase):
    """Vector 3 — unset owner fails closed (no open reactivation bypass)."""

    def setUp(self):
        cache.clear()
        self.superuser = User.objects.create_superuser(
            username="root", email="root@example.com", password="root-pass-123"
        )
        self.victim = User.objects.create_user(
            username="locked-user",
            email="locked-user@example.com",
            password="user-pass-123",
        )
        self.victim.is_active = False
        self.victim.save(update_fields=["is_active"])
        set_user_security_locked(self.victim.pk, "test")

    def _admin(self):
        return HardenedUserAdmin(User, admin.site)

    def _post_request(self, user):
        from django.test import RequestFactory

        request = RequestFactory().post("/")
        request.user = user
        return request

    def test_empty_owner_instantiates_without_crashing(self):
        modeladmin = self._admin()
        self.assertIsNotNone(modeladmin)

    def test_empty_owner_blocks_all_reactivation_attempts(self):
        """With no owner configured, no named user may lift a security lock."""
        modeladmin = self._admin()
        form = mock.Mock()
        form.changed_data = ["is_active"]
        self.victim.is_active = True
        with self.assertRaises(PermissionDenied):
            modeladmin.save_model(
                self._post_request(self.superuser), self.victim, form, change=True
            )
        # The lock marker survives the denied attempt.
        self.assertTrue(is_user_security_locked(self.victim.pk))


class RegistryLeastPrivilegeTests(TestCase):
    """Vector 4 — registries require staff + the grantable view permission."""

    def setUp(self):
        cache.clear()
        self.regular = User.objects.create_user(
            username="regular-gamer",
            email="regular-gamer@example.com",
            password="password123",
        )
        self.superuser = User.objects.create_superuser(
            username="root", email="root@example.com", password="root-pass-123"
        )

    def test_security_endpoints_deny_non_staff(self):
        self.client.force_login(self.regular)

        # Direct tech-stack registry route → 403 for a non-staff user.
        deps = self.client.get(reverse("security:dependency_registry"))
        self.assertEqual(deps.status_code, 403)

        # Admin-hosted error registry → non-staff is bounced to the admin login.
        error_registry = self.client.get(
            reverse("admin:security_errorregistryentry_changelist")
        )
        self.assertIn(error_registry.status_code, (302, 403))

    def test_superuser_can_open_both_security_registries(self):
        self.client.force_login(self.superuser)
        deps = self.client.get(reverse("security:dependency_registry"))
        self.assertEqual(deps.status_code, 200)
        error_registry = self.client.get(
            reverse("admin:security_errorregistryentry_changelist")
        )
        self.assertEqual(error_registry.status_code, 200)
