"""
Mounted API behaviour tests — SBGC-38.

Verifies URL-level behaviour: root response, OpenAPI schema, docs
availability, unknown-path fallback, method-not-allowed handling,
and OpenAPI response-contract correctness — SBGC-167.
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
        self.assertIn("/api/v1/", paths)
        self.assertIn("get", paths["/api/v1/"])

    def test_openapi_standard_error_schema_exists(self):
        c = Client()
        r = c.get("/api/v1/openapi.json")
        schemas = r.json()["components"]["schemas"]
        self.assertIn("ApiErrorResponse", schemas)

    def test_openapi_no_invalid_group_keys_4_or_5(self):
        """The invalid group keys "4" and "5" are absent from OpenAPI — SBGC-167."""
        c = Client()
        r = c.get("/api/v1/openapi.json")
        schema = r.json()
        for path_url, methods in schema.get("paths", {}).items():
            for method, operation in methods.items():
                for key in operation.get("responses", {}):
                    self.assertNotEqual(
                        key,
                        "4",
                        f"Invalid key '4' found in {path_url} {method}",
                    )
                    self.assertNotEqual(
                        key,
                        "5",
                        f"Invalid key '5' found in {path_url} {method}",
                    )

    def test_openapi_response_keys_are_valid_http_statuses(self):
        """Every response key is a valid integer HTTP status code — SBGC-167."""
        c = Client()
        r = c.get("/api/v1/openapi.json")
        paths = r.json()["paths"]
        for _, methods in paths.items():
            for _method, operation in methods.items():
                if "responses" not in operation:
                    continue
                for key in operation["responses"]:
                    http_status = int(key)
                    self.assertGreaterEqual(http_status, 100)
                    self.assertLess(http_status, 600)

    def test_openapi_has_representative_error_keys(self):
        """Concrete 4xx/5xx keys appear; the 200 schema is preserved — SBGC-167."""
        c = Client()
        r = c.get("/api/v1/openapi.json")
        root_responses = r.json()["paths"]["/api/v1/"]["get"]["responses"]
        response_keys = set(root_responses.keys())
        self.assertIn("200", response_keys)
        self.assertIn("400", response_keys)
        self.assertIn("404", response_keys)
        self.assertIn("500", response_keys)


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

    # -- Nested catch-all paths (under mounted routers) --

    def _assert_unknown_returns_not_found_envelope(self, path: str):
        c = Client()
        r = c.get(path)
        self.assertEqual(r.status_code, 404, f"{path} should return 404")
        body = r.json()
        self.assertEqual(body["error"]["code"], "NOT_FOUND")
        last_segment = path.rstrip("/").rsplit("/", 1)[-1]
        self.assertNotIn(last_segment, r.content.decode().lower())

    def test_unknown_under_games_router(self):
        self._assert_unknown_returns_not_found_envelope("/api/v1/games/not-real")

    def test_unknown_under_classifications_router(self):
        self._assert_unknown_returns_not_found_envelope(
            "/api/v1/classifications/not-real"
        )

    def test_unknown_under_docs_path(self):
        self._assert_unknown_returns_not_found_envelope("/api/v1/docs/not-real")

    def test_root_still_works(self):
        c = Client()
        r = c.get("/api/v1/")
        self.assertEqual(r.status_code, 200)

    def test_openapi_still_works(self):
        c = Client()
        r = c.get("/api/v1/openapi.json")
        self.assertEqual(r.status_code, 200)


class ProductionSettingsHttpTests(SimpleTestCase):
    """
    HTTP-level behaviour when docs are disabled (production config).
    """

    def _production_api(self):
        from classifications.api import router as classifications_router
        from games.api import router as games_router
        from ninja import NinjaAPI

        from api.errors import register_handlers
        from api.system import router as system_router

        api = NinjaAPI(
            title="MyGameDNA API",
            version="1.0.0",
            openapi_url="/openapi.json",
            docs_url=None,
            urls_namespace=None,
        )
        register_handlers(api)
        api.add_router("", system_router)
        api.add_router("/games/", games_router)
        api.add_router("/classifications/", classifications_router)
        return api

    def test_production_docs_unreachable(self):
        from ninja.testing import TestClient

        api = self._production_api()
        client = TestClient(api)
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        with self.assertRaisesRegex(Exception, "Cannot resolve"):
            client.get("/docs")

    def test_production_openapi_configured(self):
        api = self._production_api()
        self.assertEqual(api.openapi_url, "/openapi.json")
        self.assertIsNone(api.docs_url)


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
        content_type = r.get("Content-Type", "")
        self.assertIn("text/html", content_type)
