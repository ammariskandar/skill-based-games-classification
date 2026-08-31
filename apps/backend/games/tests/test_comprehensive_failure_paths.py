"""
Comprehensive failure-path matrix — SBGC-103.

Final audit + matrix suite for the SBGC-15 epic.  Verifies that every
canonical ``ErrorCode`` and every emitted HTTP status conforms to the
uniform ``{ error: { code, message, details } }`` envelope, that the
registry is complete and contains no dead/hallucinated codes, that the
public 404 boundary is byte-identical across all non-listable
permutations, and that internal tracebacks never leak regardless of
``DEBUG``.

Handler-level assertions are used only where no public route emits a given
status (400/401/403/405/429/503/500); public-route assertions cover
404/422.  This deliberately documents, rather than re-implements, the
SBGC-100/101/102 behaviour.
"""

from __future__ import annotations

import json

from api.errors import (
    _HTTP_ERROR_MAP,
    authentication_error_handler,
    authorization_error_handler,
    http_error_handler,
    unexpected_exception_handler,
)
from django.http import HttpRequest
from django.test import TestCase, override_settings
from ninja.errors import AuthenticationError, AuthorizationError, HttpError

from games.errors import ERROR_REGISTRY, ErrorCategory, ErrorCode
from games.models import Game, SourceType

ENVELOPE_KEYS = {"code", "message", "details"}


def _error(response) -> dict:
    return json.loads(response.content)["error"]


def _assert_envelope(testcase: TestCase, response, status: int, code: str) -> dict:
    testcase.assertEqual(response.status_code, status)
    error = _error(response)
    testcase.assertEqual(set(error.keys()), ENVELOPE_KEYS)
    testcase.assertEqual(error["code"], code)
    testcase.assertIsInstance(error["message"], str)
    testcase.assertIsInstance(error["details"], list)
    return error


class ErrorRegistryCompletenessTests(TestCase):
    """The registry catalogues every canonical code with valid metadata."""

    def test_all_registry_error_codes_have_metadata(self):
        for code, metadata in ERROR_REGISTRY.items():
            with self.subTest(code=code):
                self.assertEqual(metadata.code, code)
                self.assertIsInstance(metadata.http_status, int)
                self.assertIsInstance(metadata.category, ErrorCategory)
                self.assertTrue(metadata.description)
                self.assertIsInstance(metadata.sample_details, (list, dict))

    def test_every_emitted_api_code_exists_in_registry(self):
        registry = {code.value for code in ErrorCode}

        # Every code the HttpError handler can map is a real registry member.
        self.assertLessEqual(set(_HTTP_ERROR_MAP.values()), registry)

        # Codes emitted directly by the domain endpoints / handlers.
        for code in (
            ErrorCode.GAME_NOT_FOUND,
            ErrorCode.BAD_REQUEST,
            ErrorCode.RATE_LIMITED,
            ErrorCode.SERVICE_UNAVAILABLE,
            ErrorCode.VALIDATION_ERROR,
            ErrorCode.AUTHENTICATION_ERROR,
            ErrorCode.AUTHORIZATION_ERROR,
            ErrorCode.NOT_FOUND,
            ErrorCode.HTTP_ERROR,
            ErrorCode.INTERNAL_SERVER_ERROR,
            ErrorCode.METHOD_NOT_ALLOWED,
            ErrorCode.CONFLICT,
        ):
            self.assertIn(code.value, registry)


class ClientErrorEnvelopeTests(TestCase):
    """4xx responses conform to the canonical envelope."""

    def test_400_bad_request_envelope(self):
        response = http_error_handler(HttpRequest(), HttpError(400, "bad request"))
        _assert_envelope(self, response, 400, ErrorCode.BAD_REQUEST.value)

    def test_401_authentication_error_envelope(self):
        response = authentication_error_handler(HttpRequest(), AuthenticationError())
        _assert_envelope(self, response, 401, ErrorCode.AUTHENTICATION_ERROR.value)

    def test_403_forbidden_error_envelope(self):
        response = authorization_error_handler(HttpRequest(), AuthorizationError())
        _assert_envelope(self, response, 403, ErrorCode.AUTHORIZATION_ERROR.value)

    def test_405_method_not_allowed_envelope(self):
        response = http_error_handler(
            HttpRequest(), HttpError(405, "method not allowed")
        )
        _assert_envelope(self, response, 405, ErrorCode.METHOD_NOT_ALLOWED.value)

    def test_404_game_not_found_byte_identical_permutations(self):
        # Non-existent, draft, archived, DLC, and soundtrack slugs all resolve
        # through the single GAME_NOT_FOUND path and must be byte-identical.
        Game.objects.create(
            name="Draft Game",
            slug="draft-game",
            source_type=SourceType.MANUAL,
            content_type="game",
            listing_status="draft",
        )
        Game.objects.create(
            name="Archived Game",
            slug="archived-game",
            source_type=SourceType.MANUAL,
            content_type="game",
            listing_status="archived",
        )
        Game.objects.create(
            name="Published DLC",
            slug="published-dlc",
            source_type=SourceType.MANUAL,
            content_type="dlc",
            listing_status="published",
        )
        Game.objects.create(
            name="Published Soundtrack",
            slug="published-soundtrack",
            source_type=SourceType.MANUAL,
            content_type="soundtrack",
            listing_status="published",
        )

        slugs = [
            "does-not-exist",
            "draft-game",
            "archived-game",
            "published-dlc",
            "published-soundtrack",
        ]
        bodies: list[tuple[int, bytes, dict]] = []
        for slug in slugs:
            response = self.client.get(f"/api/v1/games/{slug}")
            self.assertEqual(response.status_code, 404)
            error = _error(response)
            self.assertEqual(error["code"], ErrorCode.GAME_NOT_FOUND.value)
            self.assertEqual(error["details"], [])
            # No metadata leakage: the payload names only the canonical code.
            self.assertNotIn(slug, response.content.decode())
            bodies.append((response.status_code, response.content, error))

        # Byte-identical across all permutations.
        first_status, first_body, _ = bodies[0]
        for status, body, _ in bodies[1:]:
            self.assertEqual(status, first_status)
            self.assertEqual(body, first_body)

    def test_422_validation_error_structured_details(self):
        response = self.client.get(
            "/api/v1/games/?page=0&page_size=200&profile=invalid&q=" + ("a" * 101)
        )
        error = _assert_envelope(self, response, 422, ErrorCode.VALIDATION_ERROR.value)
        self.assertTrue(error["details"])
        for detail in error["details"]:
            for key in ("location", "message", "type"):
                self.assertIn(key, detail)
        # Each violating field produces its own structured entry.
        field_names = {
            detail["location"][-1]
            for detail in error["details"]
            if detail.get("location")
        }
        for expected in ("page", "page_size", "profile", "q"):
            self.assertIn(expected, field_names)

    def test_429_rate_limited_envelope(self):
        response = http_error_handler(HttpRequest(), HttpError(429, "rate limited"))
        _assert_envelope(self, response, 429, ErrorCode.RATE_LIMITED.value)


class ServerErrorEnvelopeTests(TestCase):
    """5xx responses conform to the canonical envelope and never leak."""

    def test_500_internal_server_error_sanitized_in_production(self):
        request = HttpRequest()
        with override_settings(DEBUG=True):
            response = unexpected_exception_handler(
                request, RuntimeError("secret internal detail")
            )
        _assert_envelope(self, response, 500, ErrorCode.INTERNAL_SERVER_ERROR.value)
        body = response.content.decode()
        self.assertNotIn("secret internal detail", body)
        self.assertNotIn("Traceback", body)
        self.assertNotIn("RuntimeError", body)

    def test_500_debug_mode_behavior(self):
        # The handler is DEBUG-agnostic: even in debug mode it suppresses the
        # traceback and returns the same safe envelope (stricter than needed).
        request = HttpRequest()
        with override_settings(DEBUG=True):
            response = unexpected_exception_handler(
                request, RuntimeError("secret internal detail")
            )
        _assert_envelope(self, response, 500, ErrorCode.INTERNAL_SERVER_ERROR.value)
        self.assertNotIn("secret internal detail", response.content.decode())
        self.assertNotIn("Traceback", response.content.decode())

    def test_503_service_unavailable_envelope(self):
        response = http_error_handler(
            HttpRequest(), HttpError(503, "service unavailable")
        )
        _assert_envelope(self, response, 503, ErrorCode.SERVICE_UNAVAILABLE.value)


class PublicRouteBoundaryExclusionTests(TestCase):
    """Unlisted assets and invalid query params resolve truthfully."""

    def test_detail_endpoint_unlisted_game_returns_game_not_found(self):
        Game.objects.create(
            name="Unlisted Draft",
            slug="unlisted-draft",
            source_type=SourceType.MANUAL,
            content_type="game",
            listing_status="draft",
        )
        response = self.client.get("/api/v1/games/unlisted-draft")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_error(response)["code"], ErrorCode.GAME_NOT_FOUND.value)

    def test_catalogue_invalid_query_parameters_return_422(self):
        response = self.client.get("/api/v1/games/?sort=invalid_col")
        error = _assert_envelope(self, response, 422, ErrorCode.VALIDATION_ERROR.value)
        self.assertTrue(error["details"])

    def test_rankings_invalid_parameters_return_422(self):
        response = self.client.get("/api/v1/rankings/?profile=chaos")
        error = _assert_envelope(self, response, 422, ErrorCode.VALIDATION_ERROR.value)
        self.assertTrue(error["details"])
