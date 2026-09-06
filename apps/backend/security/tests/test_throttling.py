"""
Public API rate-limiting & circuit-breaker tests — SBGC-107.

Exercises the atomic two-bucket limiter, strict IP trust resolution, dynamic
Retry-After, syntax-bypass counter isolation, per-IP strike escalation, the
global username-check circuit breaker, and concurrent increment resilience.
"""

from __future__ import annotations

import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from security.throttling import (
    CB_COUNT_PREFIX,
    CB_OPEN_KEY,
    CB_THRESHOLD,
    CB_WINDOW_SECONDS,
    check_rate_limit_atomic,
    hash_identifier,
    increment_atomic_bucket,
    is_username_circuit_open,
    record_accepted_username_query,
    resolve_client_ip,
)


class _ThreadSafeCache:
    """Minimal thread-safe fake backend for the concurrency resilience test."""

    def __init__(self) -> None:
        self._data: dict[str, int] = {}
        self._lock = threading.Lock()

    def add(self, key: str, value: int, timeout: int | None = None) -> bool:
        with self._lock:
            if key in self._data:
                return False
            self._data[key] = value
            return True

    def incr(self, key: str, delta: int = 1) -> int:
        with self._lock:
            if key not in self._data:
                raise ValueError("missing key")
            self._data[key] += delta
            return self._data[key]

    def get(self, key: str, default: int = 0) -> int:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: int, timeout: int | None = None) -> None:
        with self._lock:
            self._data[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


class IPResolutionTests(SimpleTestCase):
    def test_trusted_proxies_ip_resolution(self):
        factory = RequestFactory()
        trusted = factory.get(
            "/", HTTP_X_CLIENT_REAL_IP="203.0.113.19", REMOTE_ADDR="127.0.0.1"
        )
        self.assertEqual(resolve_client_ip(trusted), "203.0.113.19")

        untrusted = factory.get(
            "/", HTTP_X_CLIENT_REAL_IP="203.0.113.19", REMOTE_ADDR="198.51.100.22"
        )
        self.assertEqual(resolve_client_ip(untrusted), "198.51.100.22")


class RetryAfterTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_retry_after_dynamic_range(self):
        scope = "retry_after_range_test"
        limited = False
        retry_after = 0
        for _ in range(11):
            limited, retry_after = check_rate_limit_atomic(
                scope, limit=10, window_seconds=60
            )
        self.assertTrue(limited)
        self.assertGreaterEqual(retry_after, 1)
        self.assertLessEqual(retry_after, 60)


class ConcurrentIncrementTests(SimpleTestCase):
    def test_concurrent_increment_resilience(self):
        fake = _ThreadSafeCache()
        with mock.patch("security.throttling.cache", fake):
            key = "concurrent:increment"
            workers = 8
            iterations = 1000
            with ThreadPoolExecutor(max_workers=workers) as executor:
                list(
                    executor.map(
                        lambda _: increment_atomic_bucket(key, 60),
                        range(iterations),
                    )
                )
        self.assertEqual(fake.get(key), iterations)


@override_settings(API_RATE_LIMITING_ENABLED=True)
class CheckUsernameThrottlingTests(TestCase):
    def setUp(self):
        cache.clear()

    def _check(self, username: str = "freeuser"):
        return self.client.get(f"/api/v1/auth/check-username?username={username}")

    def test_syntax_errors_bypass_counters(self):
        for _ in range(50):
            self.assertEqual(self._check("ab").status_code, 422)

        bucket = math.floor(time.time() / 60)
        ip_hash = hash_identifier("127.0.0.1")
        self.assertIsNone(cache.get(f"throttle:ip:{ip_hash}:check_user:{bucket}"))
        self.assertIsNone(cache.get(f"{CB_COUNT_PREFIX}{bucket}"))
        self.assertFalse(is_username_circuit_open()[0])

    def test_rejected_requests_do_not_increment_breaker(self):
        statuses = [self._check().status_code for _ in range(50)]
        self.assertEqual(statuses[:30], [200] * 30)
        self.assertTrue(all(status == 429 for status in statuses[30:]))

        bucket = math.floor(time.time() / 60)
        self.assertEqual(cache.get(f"{CB_COUNT_PREFIX}{bucket}", 0), 30)

    def test_per_ip_rate_limit_and_strike_escalation(self):
        for _ in range(30):
            self.assertEqual(self._check().status_code, 200)

        # First violation → 429 with a dynamic Retry-After.
        response = self._check()
        self.assertEqual(response.status_code, 429)
        retry_after = int(response["Retry-After"])
        self.assertTrue(1 <= retry_after <= 60)

        # Second violation.
        self.assertEqual(self._check().status_code, 429)

        # Third violation escalates to a 30-minute lockout.
        response = self._check()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(int(response["Retry-After"]), 1800)

    def test_circuit_breaker_trips_and_recovers(self):
        for _ in range(CB_THRESHOLD):
            tripped, _ = record_accepted_username_query()
            self.assertFalse(tripped)

        tripped, wait = record_accepted_username_query()
        self.assertTrue(tripped)
        self.assertEqual(wait, CB_WINDOW_SECONDS)

        response = self._check()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "CIRCUIT_BREAKER_OPEN")
        self.assertEqual(response["X-Circuit-Breaker"], "OPEN")

        # Simulate the 60s TTL elapsing → breaker closes.
        cache.delete(CB_OPEN_KEY)
        self.assertFalse(is_username_circuit_open()[0])
