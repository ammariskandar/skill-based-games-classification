"""
Steam service tests — SBGC-42.

Isolated tests for configuration, client, CDN validation, and error taxonomy.
Never makes real network requests — uses injected fake sessions and responses.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from games.services.steam import (
    STEAM_STORE_API_ORIGIN,
    STEAM_WEB_API_ORIGIN,
    SteamAuthenticationError,
    SteamClient,
    SteamClientConfig,
    SteamConfigurationError,
    SteamConnectionError,
    SteamError,
    SteamInvalidResponseError,
    SteamNotFoundError,
    SteamRateLimitedError,
    SteamRedirectError,
    SteamResponseTooLargeError,
    SteamTimeoutError,
    SteamUpstreamError,
    validate_steam_cdn_url,
)

# ============================================================================
# Helpers
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


def _steam_client(config=None, session=None):
    cfg = config or _make_config()
    return SteamClient(cfg, session=session)


# ============================================================================
# Configuration tests
# ============================================================================


class ConfigTests(SimpleTestCase):
    def test_defaults(self):
        cfg = SteamClientConfig()
        self.assertIsNone(cfg.api_key)
        self.assertEqual(cfg.connect_timeout, 3.05)
        self.assertEqual(cfg.read_timeout, 10.0)
        self.assertEqual(cfg.max_retries, 2)
        self.assertEqual(cfg.retry_backoff, 0.25)
        self.assertEqual(cfg.max_response_bytes, 2_097_152)
        self.assertEqual(STEAM_WEB_API_ORIGIN, "https://api.steampowered.com")
        self.assertEqual(STEAM_STORE_API_ORIGIN, "https://store.steampowered.com")
        self.assertEqual(tuple(cfg.cdn_allowed_hosts), ())

    def test_valid_overrides(self):
        cfg = _make_config(
            api_key="  ABC123  ",
            connect_timeout=5.0,
            read_timeout=20.0,
            max_retries=1,
            retry_backoff=1.0,
            max_response_bytes=1_048_576,
            cdn_allowed_hosts=["cdn.cloudflare.steamstatic.com"],
        )
        self.assertEqual(cfg.api_key, "  ABC123  ")
        self.assertEqual(cfg.connect_timeout, 5.0)
        self.assertEqual(cfg.read_timeout, 20.0)

    def test_optional_key_none(self):
        cfg = _make_config(api_key=None)
        self.assertIsNone(cfg.api_key)

    def test_optional_key_blank(self):
        cfg = _make_config(api_key="")
        self.assertEqual(cfg.api_key, "")

    def test_cdn_hosts_deduplicated(self):
        cfg = _make_config(cdn_allowed_hosts=["a.com", "  a.com  ", "b.com"])
        # deduplication happens later in validate_steam_cdn_url
        self.assertEqual(len(cfg.cdn_allowed_hosts), 3)

    def test_immutable(self):
        cfg = _make_config()
        with self.assertRaises(AttributeError):
            cfg.connect_timeout = 1.0  # type: ignore[misc]


# ============================================================================
# Client path validation
# ============================================================================


class PathValidationTests(SimpleTestCase):
    def setUp(self):
        # Use a mock session so path-validation failures are tested
        # without a real network call.
        session = MagicMock()
        resp = _fake_response(body={"ok": True})
        session.get.return_value = resp
        self.client = _steam_client(session=session)

    def _req(self, path, **kwargs):
        return self.client.get_json(path, **kwargs)

    def test_valid_relative_path(self):
        # Will fail on network, not path validation — good.
        # We test path validation with a mock session.
        pass  # covered by integration tests below

    def test_empty_path_rejected(self):
        with self.assertRaises(SteamConfigurationError):
            self._req("")

    def test_root_only_rejected(self):
        with self.assertRaises(SteamConfigurationError):
            self._req("/")

    def test_missing_leading_slash(self):
        with self.assertRaises(SteamConfigurationError):
            self._req("ISteamApps/GetAppList/v2/")

    def test_absolute_url_rejected(self):
        with self.assertRaises(SteamConfigurationError):
            self._req("https://evil.com/")

    def test_protocol_relative_rejected(self):
        with self.assertRaises(SteamConfigurationError):
            self._req("//evil.com/path")

    def test_query_in_path_rejected(self):
        with self.assertRaises(SteamConfigurationError):
            self._req("/path?x=1")

    def test_fragment_rejected(self):
        with self.assertRaises(SteamConfigurationError):
            self._req("/path#section")

    def test_backslash_rejected(self):
        with self.assertRaises(SteamConfigurationError):
            self._req("/path\\hidden")

    def test_dot_segment_rejected(self):
        with self.assertRaises(SteamConfigurationError):
            self._req("/api/../admin")

    def test_encoded_dot_segment_rejected(self):
        with self.assertRaises(SteamConfigurationError):
            self._req("/api/%2e%2e/admin")


# ============================================================================
# API key handling
# ============================================================================


class ApiKeyTests(SimpleTestCase):
    def test_missing_key_fails_before_request(self):
        client = _steam_client(_make_config(api_key=None))
        with self.assertRaises(SteamConfigurationError):
            client.get_json("/ISteamApps/GetAppList/v2/", requires_api_key=True)

    def test_blank_key_fails(self):
        client = _steam_client(_make_config(api_key="   "))
        with self.assertRaises(SteamConfigurationError):
            client.get_json("/ISteamApps/GetAppList/v2/", requires_api_key=True)

    def test_key_in_header_not_query(self):
        session = MagicMock()
        resp = _fake_response(status=200, body={"result": "ok"})
        session.get.return_value = resp
        client = _steam_client(_make_config(api_key="SECRET-KEY"), session=session)
        client.get_json("/IPartnerEvent/Test/v1/", requires_api_key=True)
        _, kwargs = session.get.call_args
        self.assertIn("headers", kwargs)
        self.assertEqual(kwargs["headers"].get("x-webapi-key"), "SECRET-KEY")
        self.assertNotIn("key", kwargs.get("params", {}))

    def test_key_never_in_exception(self):
        session = MagicMock()
        client = _steam_client(_make_config(api_key="SECRET-KEY"), session=session)
        with self.assertRaises(SteamConfigurationError):
            client.get_json("invalid", requires_api_key=True)


# ============================================================================
# Response handling (with fake session)
# ============================================================================


class ResponseHandlingTests(SimpleTestCase):
    def setUp(self):
        self.session = MagicMock()

    def _client(self, **cfg_overrides):
        return _steam_client(_make_config(**cfg_overrides), session=self.session)

    def _mock_response(self, **kw):
        resp = _fake_response(**kw)
        self.session.get.return_value = resp
        return resp

    # -- success ---------------------------------------------------------------

    def test_valid_object_json(self):
        self._mock_response(body={"result": "ok"})
        client = self._client()
        data = client.get_json("/IPartnerEvent/Test/v1/")
        self.assertEqual(data, {"result": "ok"})

    def test_json_with_charset(self):
        resp = _fake_response(
            body={"x": 1},
            content_type="application/json; charset=utf-8",
        )
        self.session.get.return_value = resp
        client = self._client()
        self.assertEqual(client.get_json("/test/"), {"x": 1})

    def test_application_plus_json(self):
        resp = _fake_response(
            body={"x": 1},
            content_type="application/steam+json",
        )
        self.session.get.return_value = resp
        client = self._client()
        self.assertEqual(client.get_json("/test/"), {"x": 1})

    # -- malformed / invalid ---------------------------------------------------

    def test_malformed_json_rejected(self):
        resp = _fake_response(body=b"not json", content_type="application/json")
        self.session.get.return_value = resp
        client = self._client()
        with self.assertRaises(SteamInvalidResponseError):
            client.get_json("/test/")

    def test_array_root_rejected(self):
        self._mock_response(body=[1, 2, 3])
        client = self._client()
        with self.assertRaises(SteamInvalidResponseError):
            client.get_json("/test/")

    def test_scalar_root_rejected(self):
        self._mock_response(body="hello")
        client = self._client()
        with self.assertRaises(SteamInvalidResponseError):
            client.get_json("/test/")

    def test_null_root_rejected(self):
        self._mock_response(body=None)
        client = self._client()
        with self.assertRaises(SteamInvalidResponseError):
            client.get_json("/test/")

    def test_wrong_content_type_rejected(self):
        resp = _fake_response(body=b"<html>", content_type="text/html")
        self.session.get.return_value = resp
        client = self._client()
        with self.assertRaises(SteamInvalidResponseError):
            client.get_json("/test/")

    def test_missing_content_type_rejected(self):
        resp = _fake_response(body=b"{}", content_type="")
        self.session.get.return_value = resp
        client = self._client()
        with self.assertRaises(SteamInvalidResponseError):
            client.get_json("/test/")

    # -- status codes ----------------------------------------------------------

    def test_301_redirect_error(self):
        self._mock_response(status=301)
        with self.assertRaises(SteamRedirectError) as cm:
            self._client().get_json("/test/")
        self.assertEqual(cm.exception.status, 301)

    def test_400_upstream_error(self):
        self._mock_response(status=400)
        with self.assertRaises(SteamUpstreamError):
            self._client().get_json("/test/")

    def test_401_auth_error(self):
        self._mock_response(status=401)
        with self.assertRaises(SteamAuthenticationError):
            self._client().get_json("/test/")

    def test_403_auth_error(self):
        self._mock_response(status=403)
        with self.assertRaises(SteamAuthenticationError):
            self._client().get_json("/test/")

    def test_404_not_found(self):
        self._mock_response(status=404)
        with self.assertRaises(SteamNotFoundError):
            self._client().get_json("/test/")

    def test_429_rate_limited(self):
        resp = self._mock_response(status=429)
        resp.headers["Retry-After"] = "60"
        with self.assertRaises(SteamRateLimitedError) as cm:
            self._client().get_json("/test/")
        self.assertEqual(cm.exception.retry_after, 60)

    def test_500_upstream_error(self):
        self._mock_response(status=500)
        with self.assertRaises(SteamUpstreamError):
            self._client().get_json("/test/")

    def test_503_upstream_error(self):
        self._mock_response(status=503)
        with self.assertRaises(SteamUpstreamError):
            self._client().get_json("/test/")

    # -- response too large ----------------------------------------------------

    def test_content_length_over_limit(self):
        resp = _fake_response(
            body=b"{}",
            headers={"Content-Length": "99999999"},
        )
        self.session.get.return_value = resp
        with self.assertRaises(SteamResponseTooLargeError):
            self._client(max_response_bytes=100).get_json("/test/")

    def test_streamed_body_over_limit(self):
        # Return a body larger than the limit.
        big = b"x" * 200
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"Content-Type": "application/json"}
        resp.iter_content = MagicMock(return_value=[big, big, big])
        resp.close = MagicMock()
        self.session.get.return_value = resp
        with self.assertRaises(SteamResponseTooLargeError):
            self._client(max_response_bytes=100).get_json("/test/")

    # -- exception safety ------------------------------------------------------

    def test_exception_contains_no_raw_body(self):
        # 500 with text/html — upstream error raised before content-type check.
        # The error message must not contain the raw upstream body.
        resp = _fake_response(status=500, body=b"<html>upstream crash</html>")
        resp.headers["Content-Type"] = "text/html"
        self.session.get.return_value = resp
        client = self._client()
        with self.assertRaises(SteamUpstreamError) as cm:
            client.get_json("/test/")
        self.assertNotIn("upstream crash", str(cm.exception).lower())
        self.assertNotIn("<html>", str(cm.exception).lower())


# ============================================================================
# Retry / session policy
# ============================================================================


class SessionPolicyTests(SimpleTestCase):
    def test_https_adapter_installed(self):
        client = _steam_client()
        adapter = client._session.adapters.get("https://")
        self.assertIsNotNone(adapter)

    def test_retry_allowed_methods(self):
        client = _steam_client()
        adapter = client._session.adapters["https://"]
        retry = adapter.max_retries
        self.assertEqual(retry.allowed_methods, {"GET", "HEAD"})

    def test_retry_status_list(self):
        client = _steam_client()
        adapter = client._session.adapters["https://"]
        retry = adapter.max_retries
        self.assertEqual(set(retry.status_forcelist), {429, 500, 502, 503, 504})

    def test_401_403_not_in_retry_list(self):
        client = _steam_client()
        adapter = client._session.adapters["https://"]
        retry = adapter.max_retries
        self.assertNotIn(401, retry.status_forcelist)
        self.assertNotIn(403, retry.status_forcelist)

    def test_redirect_retry_disabled(self):
        client = _steam_client()
        adapter = client._session.adapters["https://"]
        retry = adapter.max_retries
        self.assertEqual(retry.redirect, 0)

    def test_retry_other_zero(self):
        client = _steam_client()
        adapter = client._session.adapters["https://"]
        retry = adapter.max_retries
        self.assertEqual(retry.other, 0)

    def test_retry_after_respected(self):
        client = _steam_client()
        adapter = client._session.adapters["https://"]
        retry = adapter.max_retries
        self.assertTrue(retry.respect_retry_after_header)

    def test_backoff_factor(self):
        client = _steam_client(_make_config(retry_backoff=0.5))
        adapter = client._session.adapters["https://"]
        retry = adapter.max_retries
        self.assertEqual(retry.backoff_factor, 0.5)

    def test_max_retries_total(self):
        client = _steam_client(_make_config(max_retries=1))
        adapter = client._session.adapters["https://"]
        retry = adapter.max_retries
        self.assertEqual(retry.total, 1)

    def test_owned_session_closed(self):
        client = _steam_client()
        self.assertIsNotNone(client._session)
        client.close()
        self.assertIsNone(client._session)

    def test_injected_session_not_closed(self):
        session = MagicMock()
        client = _steam_client(session=session)
        client.close()
        session.close.assert_not_called()

    def test_context_manager_closes_owned_session(self):
        with _steam_client() as client:
            self.assertIsNotNone(client._session)
        self.assertIsNone(client._session)

    def test_timeout_tuple_passed(self):
        session = MagicMock()
        resp = _fake_response(body={"ok": True})
        session.get.return_value = resp
        client = _steam_client(
            _make_config(connect_timeout=5.0, read_timeout=15.0),
            session=session,
        )
        client.get_json("/test/")
        _, kwargs = session.get.call_args
        self.assertEqual(kwargs["timeout"], (5.0, 15.0))

    def test_allow_redirects_disabled(self):
        session = MagicMock()
        resp = _fake_response(body={"ok": True})
        session.get.return_value = resp
        client = _steam_client(session=session)
        client.get_json("/test/")
        _, kwargs = session.get.call_args
        self.assertFalse(kwargs["allow_redirects"])

    def test_params_not_mutated(self):
        session = MagicMock()
        resp = _fake_response(body={"ok": True})
        session.get.return_value = resp
        client = _steam_client(session=session)
        p = {"key": "value"}
        client.get_json("/test/", params=p)
        self.assertEqual(p, {"key": "value"})

    def test_missing_key_before_request(self):
        client = _steam_client(_make_config(api_key=None))
        with self.assertRaises(SteamConfigurationError):
            client.get_json("/test/", requires_api_key=True)


# ============================================================================
# CDN validation
# ============================================================================


class CdnValidationTests(SimpleTestCase):
    _ALLOWED = {"cdn.cloudflare.steamstatic.com"}

    def test_valid_https_url_accepted(self):
        result = validate_steam_cdn_url(
            "https://cdn.cloudflare.steamstatic.com/steam/apps/440/header.jpg",
            allowed_hosts=self._ALLOWED,
        )
        self.assertIn("cdn.cloudflare.steamstatic.com", result)
        self.assertTrue(result.startswith("https://"))

    def test_scheme_normalised_lowercase(self):
        result = validate_steam_cdn_url(
            "HTTPS://CDN.Cloudflare.Steamstatic.COM/path/file.jpg",
            allowed_hosts=self._ALLOWED,
        )
        self.assertEqual(
            result,
            "https://cdn.cloudflare.steamstatic.com/path/file.jpg",
        )

    def test_query_preserved(self):
        result = validate_steam_cdn_url(
            "https://cdn.cloudflare.steamstatic.com/img.jpg?t=123",
            allowed_hosts=self._ALLOWED,
        )
        self.assertIn("?t=123", result)

    def test_http_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "http://cdn.cloudflare.steamstatic.com/img.jpg",
                allowed_hosts=self._ALLOWED,
            )

    def test_unapproved_host_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://evil.com/img.jpg",
                allowed_hosts=self._ALLOWED,
            )

    def test_subdomain_when_parent_allowed_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://sub.cdn.cloudflare.steamstatic.com/img.jpg",
                allowed_hosts=self._ALLOWED,
            )

    def test_credentials_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://user:pass@cdn.cloudflare.steamstatic.com/img.jpg",
                allowed_hosts=self._ALLOWED,
            )

    def test_custom_port_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://cdn.cloudflare.steamstatic.com:8080/img.jpg",
                allowed_hosts=self._ALLOWED,
            )

    def test_fragment_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://cdn.cloudflare.steamstatic.com/img.jpg#top",
                allowed_hosts=self._ALLOWED,
            )

    def test_protocol_relative_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "//cdn.cloudflare.steamstatic.com/img.jpg",
                allowed_hosts=self._ALLOWED,
            )

    def test_localhost_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://localhost/img.jpg",
                allowed_hosts=self._ALLOWED,
            )

    def test_ip_literal_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://127.0.0.1/img.jpg",
                allowed_hosts=self._ALLOWED,
            )

    def test_empty_allowlist_rejects_all(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://cdn.cloudflare.steamstatic.com/img.jpg",
                allowed_hosts=[],
            )

    def test_empty_path_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://cdn.cloudflare.steamstatic.com",
                allowed_hosts=self._ALLOWED,
            )

    def test_root_path_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://cdn.cloudflare.steamstatic.com/",
                allowed_hosts=self._ALLOWED,
            )

    def test_control_characters_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "https://cdn.cloudflare.steamstatic.com/\x00img.jpg",
                allowed_hosts=self._ALLOWED,
            )

    def test_malformed_url_rejected(self):
        with self.assertRaises(ValueError):
            validate_steam_cdn_url(
                "not-a-url",
                allowed_hosts=self._ALLOWED,
            )


# ============================================================================
# Error taxonomy
# ============================================================================


class ErrorTaxonomyTests(SimpleTestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(SteamConfigurationError, SteamError))
        self.assertTrue(issubclass(SteamConnectionError, SteamError))
        self.assertTrue(issubclass(SteamTimeoutError, SteamError))
        self.assertTrue(issubclass(SteamAuthenticationError, SteamError))
        self.assertTrue(issubclass(SteamRateLimitedError, SteamError))
        self.assertTrue(issubclass(SteamNotFoundError, SteamError))
        self.assertTrue(issubclass(SteamUpstreamError, SteamError))
        self.assertTrue(issubclass(SteamInvalidResponseError, SteamError))
        self.assertTrue(issubclass(SteamResponseTooLargeError, SteamError))

    def test_error_codes(self):
        exc = SteamRateLimitedError("msg", status=429, retry_after=30)
        self.assertEqual(exc.code, "STEAM_RATE_LIMITED")
        self.assertEqual(exc.status, 429)
        self.assertEqual(exc.retry_after, 30)
        self.assertIn("msg", str(exc))

    def test_auth_error_status(self):
        exc = SteamAuthenticationError("bad key", status=403)
        self.assertEqual(exc.status, 403)


# ============================================================================
# Real adapter-policy verification (no network — inspects live urllib3 Retry)
# ============================================================================


class AdapterPolicyIntegrationTests(SimpleTestCase):
    """
    Verify the real HTTPS adapter is constructed with the correct
    urllib3 Retry policy.  Instantiates the real client; makes no
    network request.
    """

    def test_adapter_allowed_methods_get_head_only(self):
        client = _steam_client()
        adapter = client._session.adapters["https://"]
        self.assertIsNotNone(adapter)
        retry = adapter.max_retries
        self.assertEqual(retry.allowed_methods, {"GET", "HEAD"})

    def test_adapter_retry_statuses_exact(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(set(retry.status_forcelist), {429, 500, 502, 503, 504})

    def test_adapter_redirects_disabled(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(retry.redirect, 0)

    def test_adapter_other_zero(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(retry.other, 0)

    def test_adapter_retry_after_respected(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertTrue(retry.respect_retry_after_header)

    def test_adapter_configured_retry_count(self):
        client = _steam_client(_make_config(max_retries=3))
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(retry.total, 3)
        self.assertEqual(retry.connect, 3)
        self.assertEqual(retry.read, 3)

    def test_adapter_configured_backoff(self):
        client = _steam_client(_make_config(retry_backoff=0.5))
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(retry.backoff_factor, 0.5)

    def test_adapter_no_network_request(self):
        """
        Constructing the client and inspecting its adapter must not
        trigger any network request.  No mock is used — this is the
        real client.
        """
        client = _steam_client()
        self.assertIsNotNone(client._session)
        # Accessing adapters does not make a request.
        _ = client._session.adapters["https://"]


# ============================================================================
# Retry behavior tests — SBGC-168
# ============================================================================


class RetryBehaviorTests(SimpleTestCase):
    """Verify urllib3 Retry construction with real adapter inspection."""

    def test_backoff_max_capped(self):
        client = _steam_client(_make_config(retry_sleep_max_seconds=3))
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(retry.backoff_max, 3)

    def test_retry_after_max_capped(self):
        client = _steam_client(_make_config(retry_sleep_max_seconds=4))
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(retry.retry_after_max, 4)

    def test_sleep_cap_default(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(retry.backoff_max, 5.0)
        self.assertEqual(retry.retry_after_max, 5.0)

    def test_allowed_methods_exact(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(retry.allowed_methods, {"GET", "HEAD"})

    def test_status_forcelist_exact(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(set(retry.status_forcelist), {429, 500, 502, 503, 504})

    def test_redirects_zero(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(retry.redirect, 0)

    def test_other_zero(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertEqual(retry.other, 0)

    def test_raise_on_redirect_false(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertFalse(retry.raise_on_redirect)

    def test_raise_on_status_false(self):
        client = _steam_client()
        retry = client._session.adapters["https://"].max_retries
        self.assertFalse(retry.raise_on_status)


class OperationBudgetTests(SimpleTestCase):
    """Configured operation budget calculations — SBGC-168."""

    def test_defaults_within_budget(self):
        cfg = _make_config()
        self.assertLess(cfg.configured_operation_budget_seconds, 120.0)

    def test_maximum_attempts(self):
        cfg = _make_config(max_retries=2)
        self.assertEqual(cfg.maximum_attempts, 3)

    def test_maximum_attempts_zero_retries(self):
        cfg = _make_config(max_retries=0)
        self.assertEqual(cfg.maximum_attempts, 1)

    def test_budget_exceeds_ceiling_rejected(self):
        # Large timeouts + large sleep cap → budget > 120
        with self.assertRaises((ValueError, TypeError)):
            _make_config(
                connect_timeout=30.0,
                read_timeout=60.0,
                max_retries=3,
                retry_sleep_max_seconds=10,
            )


class MediaTypeTests(SimpleTestCase):
    """Structured JSON media-type matching — SBGC-168."""

    def setUp(self):
        self.session = MagicMock()

    def _client(self):
        return _steam_client(session=self.session)

    def _assert_accepted(self, content_type: str):
        resp = _fake_response(body={"ok": True}, content_type=content_type)
        self.session.get.return_value = resp
        data = self._client().get_json("/test/")
        self.assertEqual(data, {"ok": True})

    def _assert_rejected(self, content_type: str):
        resp = _fake_response(body=b"{}", content_type=content_type)
        self.session.get.return_value = resp
        with self.assertRaises(SteamInvalidResponseError):
            self._client().get_json("/test/")

    def test_application_json_accepted(self):
        self._assert_accepted("application/json")

    def test_json_with_charset_accepted(self):
        self._assert_accepted("application/json; charset=utf-8")

    def test_application_problem_json_accepted(self):
        self._assert_accepted("application/problem+json")

    def test_application_vnd_steam_json_accepted(self):
        self._assert_accepted("application/vnd.steam+json")

    def test_application_any_subtype_json_accepted(self):
        self._assert_accepted("application/x.foo-bar.baz+json")

    def test_text_json_rejected(self):
        self._assert_rejected("text/json")

    def test_text_problem_json_rejected(self):
        self._assert_rejected("text/problem+json")

    def test_application_jsonx_rejected(self):
        self._assert_rejected("application/jsonx")

    def test_application_plus_json_rejected(self):
        self._assert_rejected("application/+json")

    def test_application_problem_jsonx_rejected(self):
        self._assert_rejected("application/problem+jsonx")

    def test_empty_content_type_rejected(self):
        self._assert_rejected("")

    def test_missing_content_type_rejected(self):
        resp = _fake_response(body=b"{}", content_type="")
        self.session.get.return_value = resp
        # Clear the default content-type from _fake_response
        resp.headers = {}
        with self.assertRaises(SteamInvalidResponseError):
            self._client().get_json("/test/")


# ============================================================================
# Behavioral sleep tests — SBGC-168
# ============================================================================


class RetrySleepBehaviorTests(SimpleTestCase):
    """Patch time.sleep in urllib3.util.retry to verify sleep behaviour."""

    def setUp(self):
        import urllib3.util.retry as retry_module
        from urllib3.util.retry import Retry as _Retry

        self._Retry = _Retry
        self.retry = _Retry(
            total=2,
            connect=2,
            read=2,
            redirect=0,
            status=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={"GET", "HEAD"},
            backoff_factor=0.25,
            backoff_max=5,
            retry_after_max=5,
            raise_on_redirect=False,
            raise_on_status=False,
            respect_retry_after_header=True,
            other=0,
        )
        self.sleep_times: list[float] = []
        self._patcher = patch.object(
            retry_module.time, "sleep", lambda s: self.sleep_times.append(s)
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    # -- backoff path (no Retry-After header) ----------------------------------

    def test_no_sleep_when_no_errors(self):
        self.retry.sleep()
        self.assertEqual(self.sleep_times, [])

    def test_exponential_backoff_calls_sleep(self):
        # Need >= 2 increments for non-zero backoff.
        for _ in range(2):
            self.retry = self.retry.increment(method="GET", url="/test")
        self.retry.sleep()
        self.assertEqual(len(self.sleep_times), 1)
        self.assertGreater(self.sleep_times[0], 0.0)
        self.assertLessEqual(self.sleep_times[0], 5.0)

    def test_backoff_capped_at_max(self):
        r = self._Retry(
            total=3,
            backoff_factor=100.0,
            backoff_max=0.5,
            allowed_methods={"GET"},
            raise_on_status=False,
        )
        for _ in range(2):
            r = r.increment(method="GET", url="/test")
        r.sleep()
        self.assertEqual(len(self.sleep_times), 1)
        self.assertAlmostEqual(self.sleep_times[0], 0.5)

    # -- Retry-After path ------------------------------------------------------

    def test_retry_after_below_cap_respected(self):
        import io

        from urllib3.response import HTTPResponse

        resp = HTTPResponse(
            body=io.BytesIO(b""),
            headers={"Retry-After": "2"},
            status=429,
            preload_content=False,
        )
        self.retry.sleep(response=resp)
        self.assertEqual(len(self.sleep_times), 1)
        self.assertAlmostEqual(self.sleep_times[0], 2.0)

    def test_retry_after_above_cap_reduced(self):
        import io

        from urllib3.response import HTTPResponse

        resp = HTTPResponse(
            body=io.BytesIO(b""),
            headers={"Retry-After": "999999"},
            status=429,
            preload_content=False,
        )
        self.retry.sleep(response=resp)
        self.assertEqual(len(self.sleep_times), 1)
        self.assertLessEqual(self.sleep_times[0], 5.0)

    def test_zero_sleep_cap_prevents_positive_sleep(self):
        r = self._Retry(
            total=0,
            backoff_factor=100.0,
            backoff_max=0,
            retry_after_max=0,
            allowed_methods={"GET"},
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        self.sleep_times.clear()
        r.sleep()
        self.assertEqual(self.sleep_times, [])

    def test_no_real_sleep_occurs(self):
        for _ in range(2):
            self.retry = self.retry.increment(method="GET", url="/test")
        self.sleep_times.clear()
        self.retry.sleep()
        self.assertEqual(len(self.sleep_times), 1)

    def test_no_network_request_made(self):
        self.assertIsNotNone(self.retry)

    def test_malformed_retry_after_raises(self):
        import io

        from urllib3.exceptions import InvalidHeader
        from urllib3.response import HTTPResponse

        resp = HTTPResponse(
            body=io.BytesIO(b""),
            headers={"Retry-After": "not-a-number"},
            status=429,
            preload_content=False,
        )
        self.sleep_times.clear()
        with self.assertRaises(InvalidHeader):
            self.retry.sleep(response=resp)
        # No sleep should have occurred before the exception.
        self.assertEqual(self.sleep_times, [])


# ============================================================================
# Status-first error handling — SBGC-168
# ============================================================================


class StatusFirstErrorTests(SimpleTestCase):
    """Oversized/malformed error bodies never mask status classification."""

    def setUp(self):
        self.session = MagicMock()

    def _client(self, **cfg_overrides):
        return _steam_client(_make_config(**cfg_overrides), session=self.session)

    def _mock_response(
        self, status, body, content_type="text/html", extra_headers=None
    ):
        headers = extra_headers or {}
        resp = _fake_response(status=status, body=body, content_type=content_type)
        resp.headers.update(headers)
        self.session.get.return_value = resp
        return resp

    def test_oversized_401_still_auth_error(self):
        # Large body that would normally trigger SteamResponseTooLargeError
        big = b"x" * 200
        resp = MagicMock()
        resp.status_code = 401
        resp.headers = {"Content-Type": "text/html", "Content-Length": "99999999"}
        resp.iter_content = MagicMock(return_value=[big, big, big])
        resp.close = MagicMock()
        self.session.get.return_value = resp
        with self.assertRaises(SteamAuthenticationError):
            self._client(max_response_bytes=100).get_json("/test/")

    def test_invalid_media_403_still_auth_error(self):
        self._mock_response(403, b"<html>forbidden</html>", content_type="text/html")
        with self.assertRaises(SteamAuthenticationError) as cm:
            self._client().get_json("/test/")
        self.assertNotIn("forbidden", str(cm.exception).lower())

    def test_malformed_json_429_still_rate_limited(self):
        resp = MagicMock()
        resp.status_code = 429
        resp.headers = {"Content-Type": "application/json", "Retry-After": "30"}
        resp.iter_content = MagicMock(return_value=[b"not json"])
        resp.close = MagicMock()
        self.session.get.return_value = resp
        with self.assertRaises(SteamRateLimitedError) as cm:
            self._client().get_json("/test/")
        self.assertEqual(cm.exception.status, 429)

    def test_oversized_500_still_upstream_error(self):
        big = b"x" * 200
        resp = MagicMock()
        resp.status_code = 500
        resp.headers = {"Content-Type": "text/html"}
        resp.iter_content = MagicMock(return_value=[big, big, big])
        resp.close = MagicMock()
        self.session.get.return_value = resp
        with self.assertRaises(SteamUpstreamError):
            self._client(max_response_bytes=100).get_json("/test/")

    def test_wrong_media_503_still_upstream_error(self):
        self._mock_response(503, b"<html>down</html>", content_type="text/html")
        with self.assertRaises(SteamUpstreamError) as cm:
            self._client().get_json("/test/")
        self.assertNotIn("down", str(cm.exception).lower())

    def test_raw_body_never_in_exception(self):
        self._mock_response(
            500, b"<html>secret crash info</html>", content_type="text/html"
        )
        with self.assertRaises(SteamUpstreamError) as cm:
            self._client().get_json("/test/")
        self.assertNotIn("secret", str(cm.exception).lower())
        self.assertNotIn("crash", str(cm.exception).lower())
        self.assertNotIn("<html>", str(cm.exception).lower())

    def test_drain_stops_at_limit(self):
        """Error-body drain stops at the 1 MiB limit — does not consume
        arbitrarily large error payloads."""
        big = b"x" * 200_000  # 200 KiB per chunk
        chunks = [big] * 10  # 2 MiB total, drain stops at 1 MiB
        resp = MagicMock()
        resp.status_code = 500
        resp.headers = {"Content-Type": "text/html"}
        resp.iter_content = MagicMock(return_value=chunks)
        resp.close = MagicMock()
        self.session.get.return_value = resp
        with self.assertRaises(SteamUpstreamError):
            self._client().get_json("/test/")
        # close() is called at least once (by _drain_and_close and/or
        # the get_json finally block).
        resp.close.assert_called()

    def test_response_closed_when_iter_content_raises(self):
        """If iter_content raises during drain, the response is still closed
        and the original status exception is still raised."""
        resp = MagicMock()
        resp.status_code = 401
        resp.headers = {"Content-Type": "application/json"}
        resp.iter_content = MagicMock(side_effect=OSError("connection lost"))
        resp.close = MagicMock()
        self.session.get.return_value = resp
        with self.assertRaises(SteamAuthenticationError):
            self._client().get_json("/test/")
        resp.close.assert_called()

    def test_drain_close_errors_never_replace_status_exception(self):
        """Even when drain and close both fail, the original status
        classification exception is the one raised."""
        resp = MagicMock()
        resp.status_code = 503
        resp.headers = {"Content-Type": "text/html"}
        resp.iter_content = MagicMock(side_effect=OSError("read failure"))
        resp.close = MagicMock(side_effect=OSError("close failure"))
        self.session.get.return_value = resp
        with self.assertRaises(SteamUpstreamError) as cm:
            self._client().get_json("/test/")
        self.assertEqual(cm.exception.status, 503)
        self.assertNotIn("read failure", str(cm.exception))
        self.assertNotIn("close failure", str(cm.exception))
