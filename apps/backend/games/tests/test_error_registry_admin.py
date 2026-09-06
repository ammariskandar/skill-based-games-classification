"""
Read-only Django Admin error registry — SBGC-100 / SBGC-108.

Verifies the unmanaged ``ErrorRegistryEntry`` admin catalog: superuser and
permission-granted staff access, rendering of every canonical code, anonymous
and un-granted denial, and immutable read-only permissions.  Read access is
granted via the ``security.view_errorregistryentry`` permission (SBGC-108).
"""

from __future__ import annotations

from html import escape

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.http import HttpRequest
from django.test import TestCase
from django.urls import reverse
from security.models import ErrorRegistryEntry

from games.errors import ERROR_REGISTRY, ErrorCode


class ErrorRegistryAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="registry-staff", password="pw", is_staff=True
        )
        cls.superuser = User.objects.create_superuser(
            username="registry-super", password="pw"
        )
        cls.url = reverse("admin:security_errorregistryentry_changelist")
        cls.view_permission = Permission.objects.get(codename="view_errorregistryentry")

    def test_admin_error_registry_denied_without_permission(self):
        # A staff member without the grantable view permission is denied.
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_admin_error_registry_accessible_by_staff_with_permission(self):
        self.staff.user_permissions.add(self.view_permission)
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_admin_error_registry_accessible_by_superuser(self):
        # Superusers bypass the grantable permission.
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_admin_error_registry_renders_all_codes(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for code in ErrorCode:
            self.assertIn(code.value, content)

    def test_admin_error_registry_surfaces_api_route_column(self):
        """Every row names the API route / page that can emit the code."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("API Route / Page", content)
        for metadata in ERROR_REGISTRY.values():
            self.assertTrue(metadata.surfaced_at)
            # Template auto-escapes HTML, so compare against the escaped text.
            self.assertIn(escape(metadata.surfaced_at), content)

    def test_admin_error_registry_denies_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.headers.get("Location", ""))

    def test_admin_permissions_immutable(self):
        model_admin = admin.site._registry[ErrorRegistryEntry]
        request = HttpRequest()
        request.user = self.superuser
        # Even superusers cannot add/change/delete a read-only catalog.
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertTrue(model_admin.has_view_permission(request))
