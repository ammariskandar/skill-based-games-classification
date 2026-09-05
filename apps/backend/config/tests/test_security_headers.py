"""
Modern security response headers & payload-boundary tests — SBGC-105.

Verifies that every response carries the modern security headers (nosniff,
Referrer-Policy, SAMEORIGIN framing, COOP) and does NOT emit the obsolete
X-XSS-Protection header; that HSTS is emitted under HTTPS when configured;
and that request bodies beyond DATA_UPLOAD_MAX_MEMORY_SIZE are rejected.
"""

from __future__ import annotations

from django.core.exceptions import RequestDataTooBig
from django.test import Client, RequestFactory, SimpleTestCase, override_settings


class SecurityHeadersTestCase(SimpleTestCase):
    def setUp(self) -> None:
        self.client = Client()

    def _health_response(self, **kwargs):
        # /health/ is a public 200 endpoint with no auth/DB requirements.
        return self.client.get("/health/", **kwargs)

    def test_response_contains_modern_security_headers(self) -> None:
        """Verify all responses include nosniff, referrer-policy, and frame options."""
        response = self._health_response()

        # Verify Content-Type-Options.
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

        # Verify Referrer Policy.
        self.assertEqual(
            response.headers.get("Referrer-Policy"),
            "strict-origin-when-cross-origin",
        )

        # Verify Frame Options allows same-origin framing (Admin popups).
        self.assertEqual(response.headers.get("X-Frame-Options"), "SAMEORIGIN")

        # Verify Cross-Origin-Opener-Policy.
        self.assertEqual(
            response.headers.get("Cross-Origin-Opener-Policy"),
            "same-origin-allow-popups",
        )

        # Verify obsolete X-XSS-Protection is NOT set.
        self.assertNotIn("X-XSS-Protection", response.headers)

    @override_settings(
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
    )
    def test_hsts_header_present_when_configured(self) -> None:
        """Verify HSTS headers are emitted when enabled under HTTPS."""
        response = self._health_response(secure=True)
        hsts = response.headers.get("Strict-Transport-Security")
        self.assertIsNotNone(hsts)
        assert hsts is not None
        self.assertIn("max-age=31536000", hsts)
        self.assertIn("includeSubDomains", hsts)
        self.assertIn("preload", hsts)

    @override_settings(SECURE_HSTS_SECONDS=0)
    def test_no_hsts_when_disabled(self) -> None:
        """HSTS must be absent when SECURE_HSTS_SECONDS is zero (dev/test)."""
        response = self._health_response(secure=True)
        self.assertNotIn("Strict-Transport-Security", response.headers)

    def test_payload_boundary_exceeded_raises_error(self) -> None:
        """Payload exceeding DATA_UPLOAD_MAX_MEMORY_SIZE must be rejected.

        Exercises Django's ``MultiPartParser`` guard directly: parsing
        ``request.POST`` for a multipart body whose non-file field data exceeds
        the 1 MiB in-memory ceiling raises ``RequestDataTooBig``.
        """
        from django.test.client import BOUNDARY, encode_multipart

        oversized = "X" * (1024 * 1024 + 500)  # > 1 MiB
        body = encode_multipart(
            BOUNDARY,
            {"username": "admin", "payload": oversized},
        )
        request = RequestFactory().post(
            "/api/v1/auth/login",
            data=body,
            content_type=f"multipart/form-data; boundary={BOUNDARY}",
        )
        with self.assertRaises(RequestDataTooBig):
            _ = request.POST
