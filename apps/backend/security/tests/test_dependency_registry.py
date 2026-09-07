"""
Tech-stack registry structural & authorization tests — SBGC-108.

Validates data structure integrity (uniqueness, non-empty fields, valid enum
types) without asserting any static CVE state, and verifies the staff-only
access-control contract for the dependency registry view.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from security.dependencies import (
    TECH_STACK_REGISTRY,
    DependencyItem,
    Ecosystem,
    LifecycleStatus,
)

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


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

    def test_manifest_packages_are_registered(self):
        """Every manifest-declared package has an architectural entry.

        Parses ``apps/backend/requirements.txt`` (production runtime),
        ``apps/backend/requirements-dev.txt`` (development/CI tools, which
        inherits the production manifest via ``-r``), and the ``dependencies``
        block of ``apps/frontend/package.json``, and asserts each declared
        package maps to a registry entry.  Adding a new dependency to either
        backend manifest (or frontend) without an architectural entry fails
        here, which forces the curation contract in ``security/dependencies.py``.
        """

        def _normalize(name: str) -> str:
            return name.strip().lower().replace("-", "_")

        def _parse_requirements(path: Path) -> set[str]:
            names: set[str] = set()
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-r"):
                    continue
                names.add(line.split("==", 1)[0].strip())
            return names

        manifest_names = _parse_requirements(_BACKEND_DIR / "requirements.txt")
        manifest_names |= _parse_requirements(_BACKEND_DIR / "requirements-dev.txt")

        frontend_package = json.loads(
            (_BACKEND_DIR.parent / "frontend" / "package.json").read_text()
        )
        manifest_names.update(frontend_package["dependencies"].keys())

        registry_names = {_normalize(item.name) for item in TECH_STACK_REGISTRY}
        missing = sorted(
            name for name in manifest_names if _normalize(name) not in registry_names
        )
        self.assertEqual(
            missing,
            [],
            f"Manifest packages without a TECH_STACK_REGISTRY entry: {missing}",
        )


class DependencyRegistryAccessTests(TestCase):
    def setUp(self):
        self.url = reverse("security:dependency_registry")
        self.staff = User.objects.create_user(
            username="staff-dep", password="staff-pass-123", is_staff=True
        )
        self.non_staff = User.objects.create_user(
            username="user-dep", password="user-pass-123"
        )
        self.superuser = User.objects.create_superuser(
            username="root-dep", email="root-dep@example.com", password="root-pass-123"
        )

    def _grant_view(self, user: User) -> None:
        permission = Permission.objects.get(codename="view_dependencyregistryentry")
        user.user_permissions.add(permission)

    def _grant_both_registry_views(self, user: User) -> None:
        self._grant_view(user)
        user.user_permissions.add(
            Permission.objects.get(codename="view_errorregistryentry")
        )

    def test_registry_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_registry_non_staff_forbidden(self):
        self.client.force_login(self.non_staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_registry_staff_without_permission_forbidden(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_registry_staff_authorized(self):
        self._grant_view(self.staff)
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for tool in ("django", "astro", "pip-audit"):
            self.assertIn(tool, content)

    def test_registry_superuser_authorized(self):
        # Superusers bypass the grantable permission entirely.
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("django", response.content.decode())

    def test_registry_admin_changelist_requires_permission(self):
        """Admin sidebar route enforces the same grant as the direct view."""
        admin_url = reverse("admin:security_dependencyregistryentry_changelist")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(admin_url).status_code, 403)
        self._grant_view(self.staff)
        self.assertEqual(self.client.get(admin_url).status_code, 200)

    def test_grantable_view_permission_exists(self):
        # The Security app exposes a real permission for the roles/permissions
        # picker so moderators can be granted read access via a Group.
        permission = Permission.objects.get(codename="view_dependencyregistryentry")
        self.assertEqual(permission.content_type.app_label, "security")
        error_view = Permission.objects.get(codename="view_errorregistryentry")
        self.assertEqual(error_view.content_type.app_label, "security")

    def test_security_registry_permissions_are_view_only(self):
        """Only read grants exist for the catalog models.

        The read-only registries must never surface add/change/delete grants in
        the roles/permissions picker: moderators can be handed view access and
        nothing else.
        """
        registry_content_types = Permission.objects.filter(
            content_type__app_label="security",
            content_type__model__in=("errorregistryentry", "dependencyregistryentry"),
        )
        codenames = {perm.codename for perm in registry_content_types.all()}
        self.assertEqual(
            codenames,
            {"view_errorregistryentry", "view_dependencyregistryentry"},
        )

    def test_registries_share_security_app_category(self):
        """Error + tech-stack registries share one non-Games Admin category.

        Sidebar visibility follows per-model view permissions, so the staff
        member must hold both grants to see both catalog entries.
        """
        self._grant_both_registry_views(self.staff)
        self.client.force_login(self.staff)
        request = RequestFactory().get("/")
        request.user = self.staff

        app_list = admin.site.get_app_list(request)
        by_label = {app["app_label"]: app for app in app_list}

        security_models = {
            model["object_name"] for model in by_label["security"]["models"]
        }
        self.assertIn("ErrorRegistryEntry", security_models)
        self.assertIn("DependencyRegistryEntry", security_models)

        # The error registry must not appear under the Games domain section.
        games_models = {
            model["object_name"]
            for model in by_label.get("games", {}).get("models", [])
        }
        self.assertNotIn("ErrorRegistryEntry", games_models)
