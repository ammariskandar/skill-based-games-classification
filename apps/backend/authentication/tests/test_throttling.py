"""
Rate-limiter unit tests — SBGC-217.

Isolated coverage of the dual-key throttle helpers using Django's cache
framework.  No HTTP layer — requests are built with RequestFactory.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase

from authentication.throttling import (
    FAILED_LOGIN_LIMIT,
    clear_failed_login,
    get_client_ip,
    is_login_rate_limited,
    record_failed_login,
)


def _request(*, remote_addr="127.0.0.1", x_forwarded_for=None):
    request = RequestFactory().get("/")
    request.META["REMOTE_ADDR"] = remote_addr
    if x_forwarded_for is not None:
        request.META["HTTP_X_FORWARDED_FOR"] = x_forwarded_for
    return request


class ClientIpTests(SimpleTestCase):
    def test_prefers_x_forwarded_for_first_ip(self):
        request = _request(
            remote_addr="127.0.0.1", x_forwarded_for="203.0.113.9, 10.0.0.1"
        )
        self.assertEqual(get_client_ip(request), "203.0.113.9")

    def test_falls_back_to_remote_addr(self):
        request = _request(remote_addr="198.51.100.7")
        self.assertEqual(get_client_ip(request), "198.51.100.7")


class RateLimitTests(SimpleTestCase):
    def tearDown(self):
        cache.clear()

    def test_not_rate_limited_initially(self):
        self.assertFalse(is_login_rate_limited(_request(), "someuser"))

    def test_ip_bucket_triggers_after_limit(self):
        request = _request(remote_addr="203.0.113.1")
        for i in range(FAILED_LOGIN_LIMIT):
            record_failed_login(request, f"user-{i}")
        self.assertTrue(is_login_rate_limited(request, "another-user"))

    def test_username_bucket_triggers_after_limit(self):
        for i in range(FAILED_LOGIN_LIMIT):
            request = _request(remote_addr=f"10.0.0.{i + 1}")
            record_failed_login(request, "target-user")
        self.assertTrue(
            is_login_rate_limited(_request(remote_addr="10.0.0.99"), "target-user")
        )

    def test_clear_failed_login_resets_both_buckets(self):
        request = _request(remote_addr="203.0.113.2")
        for _ in range(FAILED_LOGIN_LIMIT):
            record_failed_login(request, "target-user")

        self.assertTrue(is_login_rate_limited(request, "target-user"))
        clear_failed_login(request, "target-user")
        self.assertFalse(is_login_rate_limited(request, "target-user"))

    def test_username_normalization(self):
        request = _request(remote_addr="203.0.113.3")
        for _ in range(FAILED_LOGIN_LIMIT):
            record_failed_login(request, "TargetUser")
        self.assertTrue(is_login_rate_limited(request, "targetuser"))
