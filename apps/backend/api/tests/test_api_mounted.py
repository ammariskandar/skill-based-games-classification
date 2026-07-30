"""
Mounted API behaviour tests — SBGC-38.

Verifies URL-level behaviour: root response, OpenAPI schema, docs
availability, unknown-path fallback, and method-not-allowed handling.
"""

from django.test import Client, SimpleTestCase


class ApiRootTests(SimpleTestCase):
    """GET /api/v1/ behaviour."""

    def test_root_returns_200(self):
        c = Client()
        r = c.get("/api/v1/")
        self.assertEqual(r.status_code, 200)

    def test_root_json_content_type(self):
        c = Client()
        r = c.get("/api/v1/")
        self.assertIn("application/json", r["Content-Type"])

    def test_root_exact_response(self):
        c = Client()
        r = c.get("/api/v1/")
        self.assertEqual(r.json(), {"name": "MyGameDNA API", "version": "1.0.0"})


class OpenApiSchemaTests(SimpleTestCase):
    """GET /api/v1/openapi.json behaviour."""

    def test_openapi_returns_200(self):
        c = Client()
        r = c.get("/api/v1/openapi.json")
        self.assertEqual(r.status_code, 200)

    def test_openapi_title(self):
        c = Client()
        r = c.get("/api/v1/openapi.json")
        self.assertEqual(r.json()["info"]["title"], "MyGameDNA API")

    def test_openapi_version(self):
        c = Client()
        r = c.get("/api/v1/openapi.json")
        self.assertEqual(r.json()["info"]["version"], "1.0.0")

    def test_openapi_api_root_operation_exists(self):
        c = Client()
        r = c.get("/api/v1/openapi.json")
        paths = r.json()["paths"]
        # Ninja mounts under /api/v1/, so the root operation path is /api/v1/
        self.assertIn("/api/v1/", paths)
        self.assertIn("get", paths["/api/v1/"])

    def test_openapi_standard_error_schema_exists(self):
        c = Client()
        r = c.get("/api/v1/openapi.json")
        schemas = r.json()["components"]["schemas"]
        self.assertIn("ApiErrorResponse", schemas)


class DocsTests(SimpleTestCase):
    """Interactive docs availability."""

    def test_docs_returns_200_in_development(self):
        c = Client()
        r = c.get("/api/v1/docs")
        self.assertEqual(r.status_code, 200)

    def test_docs_html_references_local_assets(self):
        """Swagger UI should use local static assets from the 'ninja' app."""
        c = Client()
        r = c.get("/api/v1/docs")
        content = r.content.decode()
        # Should reference local static path, not external CDN.
        self.assertIn("static/ninja", content)
        self.assertNotIn("cdn.jsdelivr.net", content)
        self.assertNotIn("unpkg.com", content)


class UnknownPathTests(SimpleTestCase):
    """Catch-all fallback for unknown API paths."""

    def test_unknown_path_returns_404(self):
        c = Client()
        r = c.get("/api/v1/not-real")
        self.assertEqual(r.status_code, 404)

    def test_unknown_path_json_content_type(self):
        c = Client()
        r = c.get("/api/v1/not-real")
        self.assertEqual(r["Content-Type"], "application/json")

    def test_unknown_path_standard_envelope(self):
        c = Client()
        r = c.get("/api/v1/not-real")
        body = r.json()
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

    def test_unknown_path_does_not_echo_path(self):
        c = Client()
        r = c.get("/api/v1/not-real")
        body = r.content.decode()
        self.assertNotIn("not-real", body.lower())


class MethodNotAllowedTests(SimpleTestCase):
    """POST /api/v1/ — no POST handler exists on the root router."""

    def test_post_root_returns_405(self):
        c = Client()
        r = c.post("/api/v1/")
        self.assertEqual(r.status_code, 405)

    def test_post_root_405_behavior_documented(self):
        """
        Record the actual 405 response format produced by Django Ninja 1.6.2.

        Django Ninja routes HTTP method mismatches through Django's built-in
        HTTP 405 handler, which returns an HTML response. Ninja's exception
        handlers do not intercept this because Django resolves the method
        mismatch at the URL-routing layer before Ninja's dispatcher runs.

        This is a documented framework limitation — we do not subclass
        private Ninja internals or add broad response-rewriting middleware
        to force JSON envelope consistency for 405 responses.
        """
        c = Client()
        r = c.post("/api/v1/")
        # Django 405 responses are HTML by default.
        content_type = r.get("Content-Type", "")
        self.assertIn("text/html", content_type)
