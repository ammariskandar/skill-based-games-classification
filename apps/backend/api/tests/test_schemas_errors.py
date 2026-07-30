"""
Schema and error-handling tests — SBGC-38.

Validates request validation, error envelope serialisation, and exception
handler behaviour.

Handler-level tests create a fresh NinjaAPI instance with registered error
handlers so they can dynamically add test routes without tripping over
the frozen-router protection on the production api instance.
"""

from django.http import Http404
from django.test import SimpleTestCase
from ninja import NinjaAPI
from ninja.errors import (
    AuthenticationError,
    AuthorizationError,
    HttpError,
)
from ninja.testing import TestClient
from pydantic import ValidationError as PydanticValidationError

from api.errors import ApiException, register_handlers
from api.schemas import (
    ApiErrorDetail,
    ApiErrorResponse,
    ApiRequestSchema,
    ApiRootResponse,
)

# ============================================================================
# Helpers
# ============================================================================


def _fresh_api() -> NinjaAPI:
    """Create a fresh NinjaAPI with registered error handlers for testing."""
    api = NinjaAPI()
    register_handlers(api)
    return api


# ============================================================================
# Schema unit tests
# ============================================================================


class ApiRequestSchemaTests(SimpleTestCase):
    """ApiRequestSchema extra-field rejection."""

    def test_rejects_unknown_fields(self):
        with self.assertRaises(PydanticValidationError):
            ApiRequestSchema(unknown_field="value")


class ApiRootResponseTests(SimpleTestCase):
    """ApiRootResponse validation."""

    def test_validates_required_fields(self):
        with self.assertRaises(PydanticValidationError):
            ApiRootResponse()
        with self.assertRaises(PydanticValidationError):
            ApiRootResponse(name="Test")

    def test_valid_instance(self):
        resp = ApiRootResponse(name="Test", version="1.0")
        self.assertEqual(resp.name, "Test")
        self.assertEqual(resp.version, "1.0")


class ApiErrorDetailTests(SimpleTestCase):
    """ApiErrorResponse default-details independence."""

    def test_details_default_independent(self):
        """Each default details list is a separate empty list."""
        e1 = ApiErrorResponse(error={"code": "TEST", "message": "m1", "details": []})
        e2 = ApiErrorResponse(error={"code": "TEST", "message": "m2", "details": []})
        e1.error.details.append(ApiErrorDetail(location=["a"], message="x", type="t"))
        self.assertEqual(len(e1.error.details), 1)
        self.assertEqual(len(e2.error.details), 0)


# ============================================================================
# Exception handler tests (fresh NinjaAPI per test)
# ============================================================================


class ValidationErrorHandlerTests(SimpleTestCase):
    """ValidationError → 422 VALIDATION_ERROR."""

    def test_validation_error_becomes_422(self):
        api = _fresh_api()

        class TestSchema(ApiRequestSchema):
            required_field: str

        @api.post("/test", response={200: dict})
        def test_op(request, body: TestSchema):
            return {"ok": True}

        client = TestClient(api)
        r = client.post(
            "/test",
            json={"extra": "unexpected"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 422)
        body = r.json()
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("details", body["error"])

    def test_validation_detail_fields(self):
        api = _fresh_api()

        class TestSchema(ApiRequestSchema):
            required_field: str

        @api.post("/test", response={200: dict})
        def test_op(request, body: TestSchema):
            return {"ok": True}

        client = TestClient(api)
        r = client.post("/test", json={}, content_type="application/json")
        body = r.json()
        details = body["error"]["details"]
        self.assertTrue(len(details) >= 1)
        for d in details:
            self.assertIn("location", d)
            self.assertIn("message", d)
            self.assertIn("type", d)
            self.assertNotIn("input", d)
            self.assertNotIn("ctx", d)
            self.assertNotIn("url", d)


class AuthenticationErrorHandlerTests(SimpleTestCase):
    def test_auth_error_becomes_401(self):
        api = _fresh_api()

        @api.get("/test")
        def test_op(request):
            raise AuthenticationError()

        client = TestClient(api)
        r = client.get("/test")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"]["code"], "AUTHENTICATION_ERROR")


class AuthorizationErrorHandlerTests(SimpleTestCase):
    def test_authz_error_becomes_403(self):
        api = _fresh_api()

        @api.get("/test")
        def test_op(request):
            raise AuthorizationError()

        client = TestClient(api)
        r = client.get("/test")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"]["code"], "AUTHORIZATION_ERROR")


class Http404HandlerTests(SimpleTestCase):
    def test_http404_becomes_404(self):
        api = _fresh_api()

        @api.get("/test")
        def test_op(request):
            raise Http404()

        client = TestClient(api)
        r = client.get("/test")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"]["code"], "NOT_FOUND")


class HttpErrorHandlerTests(SimpleTestCase):
    def test_http_error_503_maps(self):
        api = _fresh_api()

        @api.get("/test")
        def test_op(request):
            raise HttpError(503, "Service temporarily unavailable")

        client = TestClient(api)
        r = client.get("/test")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"]["code"], "SERVICE_UNAVAILABLE")

    def test_http_error_unknown_maps_to_http_error(self):
        api = _fresh_api()

        @api.get("/test")
        def test_op(request):
            raise HttpError(418, "I'm a teapot")

        client = TestClient(api)
        r = client.get("/test")
        self.assertEqual(r.json()["error"]["code"], "HTTP_ERROR")


class ApiExceptionTests(SimpleTestCase):
    def test_api_exception_preserves_code(self):
        api = _fresh_api()

        @api.get("/test")
        def test_op(request):
            raise ApiException(status_code=409, code="CONFLICT", message="dup")

        client = TestClient(api)
        r = client.get("/test")
        self.assertEqual(r.status_code, 409)
        body = r.json()
        self.assertEqual(body["error"]["code"], "CONFLICT")
        self.assertEqual(body["error"]["message"], "dup")


class UnexpectedExceptionHandlerTests(SimpleTestCase):
    def test_unexpected_exception_becomes_500(self):
        api = _fresh_api()

        @api.get("/test")
        def test_op(request):
            raise RuntimeError("secret details")

        client = TestClient(api)
        r = client.get("/test")
        self.assertEqual(r.status_code, 500)
        body = r.json()
        self.assertEqual(body["error"]["code"], "INTERNAL_SERVER_ERROR")
        self.assertNotIn("secret details", body["error"]["message"].lower())

    def test_unexpected_exception_is_logged(self):

        api = _fresh_api()

        @api.get("/test")
        def test_op(request):
            raise RuntimeError("ephemeral crash")

        client = TestClient(api)
        with self.assertLogs("api.errors", level="ERROR") as log_cm:
            client.get("/test")
        self.assertTrue(
            any("Unhandled API exception" in m for m in log_cm.output),
            "Expected 'Unhandled API exception' log message",
        )


# ============================================================================
# Router identity tests
# ============================================================================


class RouterIdentityTests(SimpleTestCase):
    def test_games_router_exists(self):
        from games.api import router

        self.assertIsNotNone(router)

    def test_classifications_router_exists(self):
        from classifications.api import router

        self.assertIsNotNone(router)

    def test_system_router_exists(self):
        from api.system import router

        self.assertIsNotNone(router)
