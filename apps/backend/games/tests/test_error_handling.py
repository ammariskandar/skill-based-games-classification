"""
Error envelope standardization — SBGC-100.

Verifies the uniform error envelope across the public API: 4xx/5xx
responses always carry exactly ``error.code`` / ``error.message`` /
``error.details``, internal tracebacks are suppressed, the canonical codes
(GAME_NOT_FOUND, VALIDATION_ERROR, INTERNAL_SERVER_ERROR) surface through
the registered handlers, and the registry covers every code the handlers
can emit.
"""

from __future__ import annotations

import json

from api.errors import (
    authentication_error_handler,
    authorization_error_handler,
    http404_handler,
    http_error_handler,
    unexpected_exception_handler,
    validation_error_handler,
)
from django.http import Http404, HttpRequest
from django.test import TestCase, override_settings
from ninja.errors import AuthenticationError, AuthorizationError, HttpError

from games.errors import ERROR_REGISTRY, ErrorCategory, ErrorCode


def _error(response) -> dict:
    # Handlers return a plain HttpResponse; the test client also exposes
    # content, so parse it uniformly.
    return json.loads(response.content)["error"]


class ErrorEnvelopeTests(TestCase):
    """Uniform envelope across real endpoints and handlers."""

    def test_game_not_found_envelope(self):
        response = self.client.get("/api/v1/games/does-not-exist")
        self.assertEqual(response.status_code, 404)
        error = _error(response)
        self.assertEqual(error["code"], ErrorCode.GAME_NOT_FOUND.value)
        self.assertIsInstance(error["message"], str)
        self.assertEqual(error["details"], [])

    def test_validation_error_envelope(self):
        response = self.client.get("/api/v1/games/?page=0")
        self.assertEqual(response.status_code, 422)
        error = _error(response)
        self.assertEqual(error["code"], ErrorCode.VALIDATION_ERROR.value)
        self.assertIsInstance(error["details"], list)
        self.assertTrue(error["details"])
        detail = error["details"][0]
        for key in ("location", "message", "type"):
            self.assertIn(key, detail)

    def test_500_sanitized_envelope_suppresses_traceback(self):
        # Production semantics: DEBUG=False, unhandled exception → generic
        # message with no traceback or exception text leaked to the client.
        request = HttpRequest()
        with override_settings(DEBUG=False):
            response = unexpected_exception_handler(
                request, RuntimeError("secret internal detail")
            )
        self.assertEqual(response.status_code, 500)
        body = _error(response)
        self.assertEqual(body["code"], ErrorCode.INTERNAL_SERVER_ERROR.value)
        self.assertNotIn("secret internal detail", response.content.decode())
        self.assertNotIn("Traceback", response.content.decode())

    def test_envelope_structure_uniformity(self):
        request = HttpRequest()
        cases = [
            (self.client.get("/api/v1/games/does-not-exist"), 404),
            (self.client.get("/api/v1/games/?page=0"), 422),
            (authentication_error_handler(request, AuthenticationError()), 401),
            (authorization_error_handler(request, AuthorizationError()), 403),
            (http404_handler(request, Http404()), 404),
            (http_error_handler(request, HttpError(503, "down")), 503),
            (
                unexpected_exception_handler(request, RuntimeError("boom")),
                500,
            ),
        ]
        for response, expected_status in cases:
            with self.subTest(status=expected_status):
                self.assertEqual(response.status_code, expected_status)
                error = _error(response)
                self.assertEqual(set(error.keys()), {"code", "message", "details"})
                self.assertIsInstance(error["details"], list)


class ErrorRegistryTests(TestCase):
    """The registry catalogues every canonical code with valid metadata."""

    def test_registry_covers_every_error_code_member(self):
        self.assertEqual(set(ERROR_REGISTRY.keys()), set(ErrorCode))

    def test_registry_metadata_is_complete(self):
        for code, metadata in ERROR_REGISTRY.items():
            with self.subTest(code=code):
                self.assertEqual(metadata.code, code)
                self.assertIsInstance(metadata.http_status, int)
                self.assertIsInstance(metadata.category, ErrorCategory)
                self.assertTrue(metadata.description)
                self.assertIsInstance(metadata.sample_details, (list, dict))

    def test_known_codes_have_expected_statuses(self):
        self.assertEqual(ERROR_REGISTRY[ErrorCode.GAME_NOT_FOUND].http_status, 404)
        self.assertEqual(ERROR_REGISTRY[ErrorCode.VALIDATION_ERROR].http_status, 422)
        self.assertEqual(
            ERROR_REGISTRY[ErrorCode.INTERNAL_SERVER_ERROR].http_status, 500
        )

    def test_validation_error_handler_uses_registry_code(self):
        request = HttpRequest()
        from ninja.errors import ValidationError as NinjaValidationError

        response = validation_error_handler(
            request,
            NinjaValidationError(
                [
                    {
                        "loc": ["query", "page"],
                        "msg": "Input should be greater than or equal to 1",
                        "type": "greater_than_equal",
                    }
                ]
            ),
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(_error(response)["code"], ErrorCode.VALIDATION_ERROR.value)
