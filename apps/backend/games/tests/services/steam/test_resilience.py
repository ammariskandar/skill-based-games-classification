"""
Steam transport resilience tests — SBGC-102.

Locks the existing SBGC-42/53/168 hardening of the synchronous Steam
client against upstream faults:

- transport exceptions (timeout / connection) convert to typed domain
  exceptions with stable machine codes;
- 429 / 5xx statuses classify to typed rate-limit / upstream errors;
- malformed payloads fail safe as ``SteamInvalidResponseError``;
- the mounted urllib3 Retry policy retries 5xx/429 for GET/HEAD only, is
  bounded by ``max_retries``, and gives up cleanly;
- the API boundary maps these exceptions onto the canonical ``ErrorCode``
  registry (429 ``RATE_LIMITED``, 503 ``SERVICE_UNAVAILABLE``).

Never makes real network requests — injected fake sessions/responses.
"""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock

import requests
from django.test import SimpleTestCase
from urllib3 import Retry
from urllib3.exceptions import MaxRetryError
from urllib3.response import HTTPResponse

from games.api import _map_steam_service_error
from games.errors import ErrorCode
from games.services.steam import (
    SteamClient,
    SteamClientConfig,
    SteamConnectionError,
    SteamError,
    SteamInvalidResponseError,
    SteamRateLimitedError,
    SteamTimeoutError,
    SteamUpstreamError,
)

# ============================================================================
# Helpers (mirror test_steam.py conventions)
# ============================================================================


def _make_config(**overrides) -> SteamClientConfig:
    kwargs = {
        "api_key": None,
        "connect_timeout": 3.05,
        "read_timeout": 10.0,
        "max_retries": 2,
        "retry_backoff": 0.25,
        "max_response_bytes": 2_097_152,
        **overrides,
    }
    return SteamClientConfig(**kwargs)


def _fake_response(
    status=200,
    body=None,
    content_type="application/json",
    headers=None,
):
    """Build a MagicMock requests.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.headers.setdefault("Content-Type", content_type)
    if body is not None:
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        resp.iter_content = MagicMock(
            side_effect=lambda chunk_size=None: [raw] if raw else []
        )
    else:
        resp.iter_content = MagicMock(return_value=iter([]))
    resp.close = MagicMock()
    return resp


# ============================================================================
# Transport-failure conversion
# ============================================================================


class TransportFailureTests(SimpleTestCase):
    """Network-level failures convert to typed, code-carrying exceptions."""

    def setUp(self):
        self.session = MagicMock()
        self.steam_client = SteamClient(_make_config(), session=self.session)

    def test_timeout_raises_typed_error(self):
        self.session.get.side_effect = requests.exceptions.Timeout("read timed out")
        with self.assertRaises(SteamTimeoutError) as cm:
            self.steam_client.get_json("/test/")
        self.assertEqual(cm.exception.code, "STEAM_TIMEOUT_ERROR")

    def test_connection_error_raises_typed_error(self):
        self.session.get.side_effect = requests.exceptions.ConnectionError("refused")
        with self.assertRaises(SteamConnectionError) as cm:
            self.steam_client.get_json("/test/")
        self.assertEqual(cm.exception.code, "STEAM_CONNECTION_ERROR")

    def test_generic_request_exception_raises_typed_error(self):
        self.session.get.side_effect = requests.exceptions.RequestException("boom")
        with self.assertRaises(SteamConnectionError) as cm:
            self.steam_client.get_json("/test/")
        self.assertEqual(cm.exception.code, "STEAM_CONNECTION_ERROR")

    def test_transport_failures_stay_in_steam_error_hierarchy(self):
        # Every transport failure stays inside the SteamError hierarchy so the
        # API boundary maps it onto the canonical registry (503).
        self.session.get.side_effect = requests.exceptions.Timeout("t")
        with self.assertRaises(SteamError):
            self.steam_client.get_json("/test/")

    def test_429_raises_rate_limited_error(self):
        resp = _fake_response(status=429)
        resp.headers["Retry-After"] = "30"
        self.session.get.return_value = resp
        with self.assertRaises(SteamRateLimitedError) as cm:
            self.steam_client.get_json("/test/")
        self.assertEqual(cm.exception.code, "STEAM_RATE_LIMITED")
        self.assertEqual(cm.exception.retry_after, 30)

    def test_503_raises_upstream_error(self):
        self.session.get.return_value = _fake_response(status=503)
        with self.assertRaises(SteamUpstreamError) as cm:
            self.steam_client.get_json("/test/")
        self.assertEqual(cm.exception.code, "STEAM_UPSTREAM_ERROR")


# ============================================================================
# Corrupted-payload fail-safes
# ============================================================================


class MalformedPayloadTests(SimpleTestCase):
    """Malformed upstream payloads fail safe without unhandled exceptions."""

    def setUp(self):
        self.session = MagicMock()
        self.steam_client = SteamClient(_make_config(), session=self.session)

    def test_html_body_fails_safe(self):
        resp = _fake_response(
            body=b"<html>upstream crash</html>", content_type="text/html"
        )
        self.session.get.return_value = resp
        with self.assertRaises(SteamInvalidResponseError) as cm:
            self.steam_client.get_json("/test/")
        self.assertEqual(cm.exception.code, "STEAM_INVALID_RESPONSE")
        self.assertNotIn("upstream crash", str(cm.exception).lower())

    def test_malformed_json_fails_safe(self):
        resp = _fake_response(body=b"{not json", content_type="application/json")
        self.session.get.return_value = resp
        with self.assertRaises(SteamInvalidResponseError) as cm:
            self.steam_client.get_json("/test/")
        self.assertEqual(cm.exception.code, "STEAM_INVALID_RESPONSE")


# ============================================================================
# Retry policy contract
# ============================================================================


class RetryContractTests(SimpleTestCase):
    """The mounted urllib3 Retry policy bounds 5xx/429 recovery."""

    def _client_retry(self) -> Retry:
        client = SteamClient(_make_config())  # owns a real built session
        self.addCleanup(client.close)
        adapter = client._session.get_adapter(  # pyright: ignore[reportOptionalMemberAccess]
            "https://"
        )
        return adapter.max_retries  # pyright: ignore[reportAttributeAccessIssue]

    def test_retry_statuses_and_methods(self):
        retry = self._client_retry()
        self.assertEqual(set(retry.status_forcelist), {429, 500, 502, 503, 504})
        self.assertEqual(retry.allowed_methods, {"GET", "HEAD"})

    def test_503_is_retryable_for_get(self):
        retry = self._client_retry()
        self.assertTrue(
            retry.is_retry(method="GET", status_code=503, has_retry_after=True)
        )

    def test_two_consecutive_503s_retry_then_give_up(self):
        # max_retries=2 → two back-to-back 503s are retried; a third 503
        # exhausts the budget (MaxRetryError) rather than looping forever, so a
        # request that succeeds on the next attempt recovers cleanly.
        retry = self._client_retry()
        resp = HTTPResponse(
            body=io.BytesIO(b""), headers={}, status=503, preload_content=False
        )
        url = "https://store.steampowered.com/appdetails"
        r1 = retry.increment(method="GET", url=url, response=resp)
        r2 = r1.increment(method="GET", url=url, response=resp)
        self.assertEqual(r2.total, 0)
        with self.assertRaises(MaxRetryError):
            r2.increment(method="GET", url=url, response=resp)


# ============================================================================
# API-boundary mapping onto the canonical ErrorCode registry
# ============================================================================


class ApiMappingTests(SimpleTestCase):
    """Transport/domain exceptions map to canonical ErrorCode values."""

    def _mapped(self, exc):
        mapped = _map_steam_service_error(exc)
        return mapped.status_code, mapped.code

    def test_timeout_maps_to_503_service_unavailable(self):
        self.assertEqual(
            self._mapped(SteamTimeoutError("read timed out")),
            (503, ErrorCode.SERVICE_UNAVAILABLE.value),
        )

    def test_connection_error_maps_to_503_service_unavailable(self):
        self.assertEqual(
            self._mapped(SteamConnectionError("refused")),
            (503, ErrorCode.SERVICE_UNAVAILABLE.value),
        )

    def test_invalid_response_maps_to_503_service_unavailable(self):
        self.assertEqual(
            self._mapped(SteamInvalidResponseError("bad payload")),
            (503, ErrorCode.SERVICE_UNAVAILABLE.value),
        )

    def test_upstream_error_maps_to_503_service_unavailable(self):
        self.assertEqual(
            self._mapped(SteamUpstreamError("upstream 502", status=502)),
            (503, ErrorCode.SERVICE_UNAVAILABLE.value),
        )

    def test_rate_limited_maps_to_429_rate_limited(self):
        self.assertEqual(
            self._mapped(SteamRateLimitedError("rate limited")),
            (429, ErrorCode.RATE_LIMITED.value),
        )
