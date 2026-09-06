"""
Tech-stack registry structural & authorization tests — SBGC-108.

Validates data structure integrity (uniqueness, non-empty fields, valid enum
types) without asserting any static CVE state, and verifies the staff-only
access-control contract for the dependency registry view.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from security.dependencies import (
    TECH_STACK_REGISTRY,
    DependencyItem,
    Ecosystem,
    LifecycleStatus,
)


class RegistryStructureTests(TestCase):
    def test_registry_entries_unique(self):
        names = [item.name for item in TECH_STACK_REGISTRY]
        self.assertEqual(len(names), len(set(names)), "Duplicate registry names.")

    def test_registry_fields_non_empty(self):
        self.assertTrue(TECH_STACK_REGISTRY, "Registry must not be empty.")
        for item in TECH_STACK_REGISTRY:
            for field in (
                "name",
                "version_spec",
                "affects_subsystem",
                "alternatives",
                "justification",
            ):
                value = getattr(item, field)
                self.assertIsInstance(value, str, f"{item.name}.{field} not a string")
                self.assertTrue(value.strip(), f"{item.name}.{field} is blank")

    def test_valid_ecosystems_and_lifecycle(self):
        for item in TECH_STACK_REGISTRY:
            self.assertIsInstance(item, DependencyItem)
            self.assertIsInstance(item.ecosystem, Ecosystem)
            self.assertIsInstance(item.lifecycle_status, LifecycleStatus)

    def test_multiple_ecosystems_represented(self):
        ecosystems = {item.ecosystem for item in TECH_STACK_REGISTRY}
        self.assertGreaterEqual(len(ecosystems), 4, "Registry is too narrow.")


class DependencyRegistryAccessTests(TestCase):
    def setUp(self):
        self.url = reverse("security:dependency_registry")
        self.staff = User.objects.create_user(
            username="staff-dep", password="staff-pass-123", is_staff=True
        )
        self.non_staff = User.objects.create_user(
            username="user-dep", password="user-pass-123"
        )

    def test_registry_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_registry_non_staff_forbidden(self):
        self.client.force_login(self.non_staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_registry_staff_authorized(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for tool in ("django", "astro", "pip-audit"):
            self.assertIn(tool, content)
