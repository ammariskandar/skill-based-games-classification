"""
Read-only Django Admin error registry — SBGC-100.

Verifies the unmanaged ``ErrorRegistryEntry`` admin catalog: staff access,
rendering of every canonical code, anonymous denial, and immutable
read-only permissions.
"""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import TestCase
from django.urls import reverse

from games.errors import ERROR_REGISTRY, ErrorCode
from games.models import ErrorRegistryEntry


class ErrorRegistryAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="registry-staff", password="pw", is_staff=True
        )
        cls.superuser = User.objects.create_superuser(
            username="registry-super", password="pw"
        )
        cls.url = reverse("admin:games_errorregistryentry_changelist")

    def test_admin_error_registry_accessible_by_staff(self):
        self.client.force_login(self.staff)
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
            self.assertIn(metadata.surfaced_at, content)

    def test_admin_error_registry_denies_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.headers.get("Location", ""))

    def test_admin_permissions_immutable(self):
        model_admin = admin.site._registry[ErrorRegistryEntry]
        request = HttpRequest()
        request.user = self.staff
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
