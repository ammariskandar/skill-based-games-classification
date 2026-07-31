"""
Schema and error-handling tests — SBGC-38.

Validates request validation, error envelope serialisation, exception
handler behaviour, shared response declarations, explicit endpoint
response handling, and malformed-payload rejection — SBGC-167.

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
from ninja.responses import codes_4xx, codes_5xx
from ninja.testing import TestClient
from pydantic import ValidationError as PydanticValidationError

from api.errors import (
    STANDARD_ERROR_RESPONSES,
    ApiException,
    register_handlers,
)
from api.schemas import (
    ApiError,
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
    """ApiError default-details independence and serialisation."""

    def test_default_details_is_independent_list(self):
        e1 = ApiError(code="T1", message="m1")
        e2 = ApiError(code="T2", message="m2")
        e1.details.append(ApiErrorDetail(location=["a"], message="x", type="t"))
        self.assertEqual(len(e1.details), 1)
        self.assertEqual(len(e2.details), 0)

    def test_default_details_serializes_as_empty_array(self):
        resp = ApiErrorResponse(error=ApiError(code="T1", message="m1"))
        json_str = resp.model_dump_json()
        self.assertIn('"details":[]', json_str)

    def test_details_explicit_list(self):
        e1 = ApiErrorResponse(error={"code": "TEST", "message": "m1", "details": []})
        e2 = ApiErrorResponse(error={"code": "TEST", "message": "m2", "details": []})
        e1.error.details.append(ApiErrorDetail(location=["a"], message="x", type="t"))
        self.assertEqual(len(e1.error.details), 1)
        self.assertEqual(len(e2.error.details), 0)

    def test_generated_openapi_schema_details_is_array(self):
        schema = ApiErrorResponse.model_json_schema()
        error_props = schema["$defs"]["ApiError"]["properties"]
        details_schema = error_props["details"]
        self.assertEqual(details_schema["type"], "array")


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


# ============================================================================
# Shared declaration tests — SBGC-167
# ============================================================================


class StandardErrorResponsesTests(SimpleTestCase):
    """The shared STANDARD_ERROR_RESPONSES uses supported grouped response sets."""

    def test_uses_grouped_response_sets_not_integers(self):
        keys = list(STANDARD_ERROR_RESPONSES.keys())
        self.assertNotIn(4, keys)
        self.assertNotIn(5, keys)
        for k in keys:
            self.assertIsInstance(k, frozenset)

    def test_contains_4xx_and_5xx(self):
        keys = list(STANDARD_ERROR_RESPONSES.keys())
        self.assertIn(codes_4xx, keys)
        self.assertIn(codes_5xx, keys)

    def test_422_not_in_standard_4xx_group(self):
        """422 is not included in Django Ninja's codes_4xx — endpoints returning
        explicit 422 responses must declare it separately."""
        self.assertNotIn(422, codes_4xx)

    def test_maps_to_api_error_response(self):
        for schema in STANDARD_ERROR_RESPONSES.values():
            self.assertIs(schema, ApiErrorResponse)

    def test_spreadable_with_success_schema(self):
        combined = {200: ApiRootResponse, **STANDARD_ERROR_RESPONSES}
        self.assertIn(200, combined)
        self.assertIn(codes_4xx, combined)
        self.assertIn(codes_5xx, combined)


# ============================================================================
# Explicit endpoint response tests — SBGC-167
# ============================================================================


class ExplicitEndpointResponseTests(SimpleTestCase):
    """
    Explicit (status, body) endpoint returns work with grouped and
    explicit response declarations.

    Django Ninja's codes_4xx does not include 422 — endpoints that return
    explicit 422 responses must declare ``422: ApiErrorResponse`` in
    addition to ``STANDARD_ERROR_RESPONSES``.
    """

    def test_explicit_200_works_with_standard_responses(self):
        api = _fresh_api()

        @api.get("/ok", response={200: ApiRootResponse, **STANDARD_ERROR_RESPONSES})
        def test_op(request):
            return 200, {"name": "X", "version": "1"}

        client = TestClient(api)
        r = client.get("/ok")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"name": "X", "version": "1"})

    def test_explicit_422_with_explicit_declaration(self):
        """
        422 is not in codes_4xx.  When an endpoint returns explicit 422
        responses it must declare 422: ApiErrorResponse explicitly alongside
        STANDARD_ERROR_RESPONSES.  The explicit key does not collide with
        the grouped codes_4xx frozenset.
        """
        api = _fresh_api()
        error_body = ApiErrorResponse(
            error=ApiError(
                code="VALIDATION_ERROR",
                message="Invalid input.",
                details=[],
            )
        )

        @api.get(
            "/fail",
            response={
                200: dict,
                **STANDARD_ERROR_RESPONSES,
                422: ApiErrorResponse,
            },
        )
        def test_op(request):
            return 422, error_body

        client = TestClient(api)
        r = client.get("/fail")
        self.assertEqual(r.status_code, 422)
        body = r.json()
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")

    def test_explicit_422_without_declaration_falls_back(self):
        """
        When an endpoint returns 422 but only uses STANDARD_ERROR_RESPONSES
        (which does not include 422), Ninja cannot validate the response
        and produces a 500 via the unexpected-exception handler.
        """
        api = _fresh_api()
        error_body = ApiErrorResponse(
            error=ApiError(
                code="VALIDATION_ERROR",
                message="Invalid input.",
                details=[],
            )
        )

        @api.get("/fail", response={200: dict, **STANDARD_ERROR_RESPONSES})
        def test_op(request):
            return 422, error_body

        client = TestClient(api)
        r = client.get("/fail")
        # Without an explicit 422 declaration, Ninja fails response-schema
        # validation and the unexpected-exception handler returns 500.
        self.assertEqual(r.status_code, 500)
        body = r.json()
        self.assertIn("error", body)

    def test_explicit_404_matches_grouped_set(self):
        """404 is in codes_4xx — explicit 404 returns work through the group."""
        api = _fresh_api()
        error_body = ApiErrorResponse(
            error=ApiError(code="NOT_FOUND", message="Gone.", details=[])
        )

        @api.get("/missing", response={200: dict, **STANDARD_ERROR_RESPONSES})
        def test_op(request):
            return 404, error_body

        client = TestClient(api)
        r = client.get("/missing")
        self.assertEqual(r.status_code, 404)
        body = r.json()
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

    def test_explicit_500_matches_grouped_set(self):
        """500 is in codes_5xx — explicit 500 returns work through the group."""
        api = _fresh_api()
        error_body = ApiErrorResponse(
            error=ApiError(code="INTERNAL_SERVER_ERROR", message="Boom.", details=[])
        )

        @api.get("/crash", response={200: dict, **STANDARD_ERROR_RESPONSES})
        def test_op(request):
            return 500, error_body

        client = TestClient(api)
        r = client.get("/crash")
        self.assertEqual(r.status_code, 500)
        body = r.json()
        self.assertEqual(body["error"]["code"], "INTERNAL_SERVER_ERROR")

    def test_malformed_error_payload_is_rejected(self):
        """
        When an endpoint returns a body that does not satisfy the declared
        ApiErrorResponse schema, Ninja rejects it with response-schema
        validation.  The malformed body is never silently returned as a
        valid API error.

        The test suppresses the expected internal logging from the
        unexpected-exception handler.
        """
        api = _fresh_api()

        @api.get(
            "/bad",
            response={
                200: dict,
                **STANDARD_ERROR_RESPONSES,
                422: ApiErrorResponse,
            },
        )
        def test_op(request):
            # Missing the required "error" wrapper key.
            return 422, {"code": "OOPS", "message": "bad"}

        client = TestClient(api)
        with self.assertLogs("api.errors", level="ERROR"):
            r = client.get("/bad")
        self.assertEqual(r.status_code, 500)
        body = r.json()
        self.assertEqual(body["error"]["code"], "INTERNAL_SERVER_ERROR")

    def test_handler_response_is_not_double_wrapped(self):
        """
        Exception-handler responses (HttpResponse) bypass response-schema
        validation because they are returned directly by the handler.
        This test confirms existing handler behaviour is unchanged.
        """
        api = _fresh_api()

        @api.get("/httperror")
        def test_op(request):
            raise HttpError(503, "down")

        client = TestClient(api)
        r = client.get("/httperror")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"]["code"], "SERVICE_UNAVAILABLE")
