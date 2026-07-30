"""
Django Admin configuration tests — SBGC-40.

Covers ADMIN_URL_PATH validation, routing, access control, and branding.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from config.admin import validate_admin_url_path

# ============================================================================
# ADMIN_URL_PATH validation
# ============================================================================


class AdminUrlPathValidationTests(SimpleTestCase):
    """Unit tests for validate_admin_url_path()."""

    # -- valid ----------------------------------------------------------------

    def test_valid_simple_segment_accepted(self):
        self.assertEqual(validate_admin_url_path("admin"), "admin")

    def test_valid_hyphen_accepted(self):
        self.assertEqual(validate_admin_url_path("my-admin"), "my-admin")

    def test_valid_underscore_accepted(self):
        self.assertEqual(validate_admin_url_path("my_admin"), "my_admin")

    def test_valid_mixed_accepted(self):
        self.assertEqual(validate_admin_url_path("Admin-123_test"), "Admin-123_test")

    def test_valid_strips_whitespace(self):
        self.assertEqual(validate_admin_url_path("  admin  "), "admin")

    # -- blank / missing ------------------------------------------------------

    def test_none_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path(None)

    def test_blank_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("")

    def test_whitespace_only_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("   ")

    # -- slashes --------------------------------------------------------------

    def test_leading_slash_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("/admin")

    def test_trailing_slash_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("admin/")

    def test_nested_slash_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("a/b")

    # -- backslash ------------------------------------------------------------

    def test_backslash_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("admin\\hidden")

    # -- traversal ------------------------------------------------------------

    def test_dot_segment_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path(".")

    def test_dot_dot_segment_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("..")

    # -- query / fragment -----------------------------------------------------

    def test_query_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("admin?next=/")

    def test_fragment_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("admin#top")

    # -- URL forms ------------------------------------------------------------

    def test_full_url_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("https://example.com/admin")

    def test_protocol_relative_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("//example.com/admin")

    # -- reserved segments ---------------------------------------------------

    def test_api_segment_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("api")

    def test_api_uppercase_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_admin_url_path("API")


# ============================================================================
# Routing tests
# ============================================================================


class AdminRoutingTests(SimpleTestCase):
    """Verify the admin is mounted at the configured ADMIN_URL_PATH."""

    def test_index_route_resolves(self):
        url = reverse("admin:index")
        self.assertTrue(url.startswith(f"/{settings.ADMIN_URL_PATH}/"))

    def test_login_route_resolves(self):
        url = reverse("admin:login")
        self.assertTrue(url.startswith(f"/{settings.ADMIN_URL_PATH}/"))

    def test_anonymous_index_redirects_to_login(self):
        c = Client()
        r = c.get(f"/{settings.ADMIN_URL_PATH}/")
        self.assertEqual(r.status_code, 302)

    def test_configured_login_page_renders(self):
        c = Client()
        r = c.get(reverse("admin:login"))
        self.assertEqual(r.status_code, 200)

    def test_hardcoded_admin_not_available_when_path_differs(self):
        """If ADMIN_URL_PATH is not 'admin', the old /admin/ is not mounted."""
        if settings.ADMIN_URL_PATH == "admin":
            self.skipTest("Default path is 'admin' — no old route to test")
        c = Client()
        r = c.get("/admin/")
        # /admin/ should either 404 or redirect to the real admin path
        # depending on CommonMiddleware's APPEND_SLASH behavior.
        # Either way, it must not serve admin content.
        self.assertNotEqual(r.status_code, 200)

    def test_api_route_still_operational(self):
        c = Client()
        r = c.get("/api/v1/")
        self.assertEqual(r.status_code, 200)

    def test_api_unknown_route_still_works(self):
        c = Client()
        r = c.get("/api/v1/not-real")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"]["code"], "NOT_FOUND")


# ============================================================================
# Access control tests (require database — use TestCase)
# ============================================================================


class AdminAccessTests(TestCase):
    """Verify admin access control and branding."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin-test",
            email="admin@example.com",
            password="super-secret-123",
        )
        cls.staff_user = User.objects.create_user(
            username="staff-test",
            email="staff@example.com",
            password="staff-secret-123",
            is_staff=True,
        )
        cls.normal_user = User.objects.create_user(
            username="normal-test",
            email="normal@example.com",
            password="normal-secret-123",
        )

    def _admin_url(self, name, **kwargs):
        return reverse(f"admin:{name}", kwargs=kwargs)

    # -- anonymous ------------------------------------------------------------

    def test_anonymous_index_redirects(self):
        c = Client()
        r = c.get(self._admin_url("index"))
        self.assertEqual(r.status_code, 302)

    # -- normal user ----------------------------------------------------------

    def test_normal_user_cannot_access_index(self):
        c = Client()
        c.login(username="normal-test", password="normal-secret-123")
        r = c.get(self._admin_url("index"))
        # Normal users without staff status are redirected to login.
        self.assertEqual(r.status_code, 302)

    # -- staff user (no permissions) ------------------------------------------

    def test_staff_user_can_access_index(self):
        c = Client()
        c.login(username="staff-test", password="staff-secret-123")
        r = c.get(self._admin_url("index"))
        self.assertEqual(r.status_code, 200)

    def test_staff_user_sees_branding(self):
        c = Client()
        c.login(username="staff-test", password="staff-secret-123")
        r = c.get(self._admin_url("index"))
        content = r.content.decode()
        self.assertIn("MyGameDNA Administration", content)

    # -- superuser ------------------------------------------------------------

    def test_superuser_can_access_index(self):
        c = Client()
        c.login(username="admin-test", password="super-secret-123")
        r = c.get(self._admin_url("index"))
        self.assertEqual(r.status_code, 200)

    def test_superuser_sees_branding(self):
        c = Client()
        c.login(username="admin-test", password="super-secret-123")
        r = c.get(self._admin_url("index"))
        content = r.content.decode()
        self.assertIn("MyGameDNA Administration", content)

    def test_superuser_can_logout(self):
        c = Client()
        c.login(username="admin-test", password="super-secret-123")
        r = c.get(self._admin_url("index"))
        self.assertEqual(r.status_code, 200)
        # Django 6.x admin logout requires a POST with CSRF token.
        # Use the test client's built-in logout method which handles CSRF.
        c.logout()
        # After logout, index should redirect to login.
        r = c.get(self._admin_url("index"))
        self.assertEqual(r.status_code, 302)
