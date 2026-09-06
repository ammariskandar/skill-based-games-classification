"""
Multi-tier atomic rate limiting & circuit breakers — SBGC-107.

Owns the concurrency-safe primitives for the public API throttle layer:

- SHA-256 key hashing so raw PII never appears in cache keys.
- An atomic two-bucket sliding-window counter (``add``/``incr`` scalar
  integers — no read-modify-write list serialization).
- Strict client-IP resolution honouring the trusted reverse-proxy contract.
- An idempotent global circuit-breaker state machine for the username
  availability check.
- Per-IP abuse-strike escalation into a 30-minute lockout.

The engine is backend-agnostic: production uses PostgreSQL ``DatabaseCache``
for cross-worker atomicity; tests use ``LocMemCache``.
"""

from __future__ import annotations

import hashlib
import math
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from games.errors import ErrorCode

# -- circuit breaker ---------------------------------------------------------

CB_OPEN_KEY = "cb:check_username:open"
CB_THRESHOLD = 500
CB_WINDOW_SECONDS = 60
CB_COUNT_PREFIX = "cb:check_username:count:"

# -- abuse-strike escalation -------------------------------------------------

STRIKE_LIMIT = 3
STRIKE_WINDOW_SECONDS = 900  # 15 minutes
LOCKOUT_SECONDS = 1800  # 30 minutes


def hash_identifier(value: str) -> str:
    """Return a truncated SHA-256 hash so raw PII never leaks into cache keys."""
    normalized = value.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def increment_atomic_bucket(key: str, window_seconds: int) -> int:
    """Atomically increment a scalar cache counter, seeding its TTL on first use."""
    timeout = window_seconds * 2 + 15
    added = cache.add(key, 1, timeout=timeout)
    if not added:
        try:
            return cache.incr(key, 1)
        except ValueError:
            # The key expired between ``add`` and ``incr`` — reseed it.
            cache.set(key, 1, timeout=timeout)
            return 1
    return 1


def check_rate_limit_atomic(
    scope_key: str, limit: int, window_seconds: int = 60
) -> tuple[bool, int]:
    """Two-bucket weighted sliding-window limiter.

    Returns ``(is_limited, retry_after)`` where ``retry_after`` is the dynamic
    remaining window seconds (1 <= retry_after <= window_seconds).
    """
    now = time.time()
    current_bucket = math.floor(now / window_seconds)
    previous_bucket = current_bucket - 1

    curr_key = f"throttle:{scope_key}:{current_bucket}"
    prev_key = f"throttle:{scope_key}:{previous_bucket}"

    current_count = increment_atomic_bucket(curr_key, window_seconds)
    prev_count = cache.get(prev_key, 0)

    time_into_current = now % window_seconds
    prev_weight = max(0.0, (window_seconds - time_into_current) / window_seconds)
    estimated_requests = (prev_count * prev_weight) + current_count

    if estimated_requests > limit:
        retry_after = max(1, int(window_seconds - time_into_current))
        return True, retry_after

    return False, 0


def resolve_client_ip(request: HttpRequest) -> str:
    """Resolve the client IP strictly per the trusted reverse-proxy contract.

    ``X-Client-Real-IP`` is honoured only when ``REMOTE_ADDR`` is an explicit
    address in ``TRUSTED_INTERNAL_PROXIES``; untrusted callers always fall back
    to ``REMOTE_ADDR`` so a spoofed forwarding header cannot bypass limits.
    """
    remote_addr = request.META.get("REMOTE_ADDR", "127.0.0.1").strip()
    trusted_proxies = getattr(
        settings, "TRUSTED_INTERNAL_PROXIES", ["127.0.0.1", "::1"]
    )

    if remote_addr in trusted_proxies:
        client_real_ip = request.META.get("HTTP_X_CLIENT_REAL_IP")
        if client_real_ip:
            return client_real_ip.strip()

    return remote_addr


def build_throttle_response(
    status: int,
    code: ErrorCode,
    message: str,
    retry_after: int,
    extra_headers: dict[str, str] | None = None,
) -> JsonResponse:
    """Build a standard error-envelope response with a dynamic Retry-After."""
    response = JsonResponse(
        {"error": {"code": code.value, "message": message, "details": []}},
        status=status,
    )
    response["Retry-After"] = str(retry_after)
    for key, value in (extra_headers or {}).items():
        response[key] = value
    return response


def enforce_ip_rate_limit(
    request: HttpRequest,
    scope: str,
    limit: int,
    window_seconds: int = 60,
    message: str = "Rate limit exceeded.",
) -> JsonResponse | None:
    """Return a 429 response when a per-IP limit is exceeded, else None."""
    client_ip = resolve_client_ip(request)
    scope_key = f"ip:{hash_identifier(client_ip)}:{scope}"
    limited, retry_after = check_rate_limit_atomic(scope_key, limit, window_seconds)
    if not limited:
        return None
    return build_throttle_response(429, ErrorCode.RATE_LIMITED, message, retry_after)


# -- circuit breaker state machine -------------------------------------------


def is_username_circuit_open() -> tuple[bool, int]:
    """Return ``(is_open, retry_after)`` for the username-check breaker."""
    opened_at = cache.get(CB_OPEN_KEY)
    if opened_at is None:
        return False, 0
    remaining = max(1, int(CB_WINDOW_SECONDS - (time.time() - float(opened_at))))
    return True, remaining


def record_accepted_username_query() -> tuple[bool, int]:
    """Atomically count one accepted username check and trip the breaker.

    Returns ``(tripped, retry_after)``.  The ``CLOSED -> OPEN`` transition is
    idempotent: ``cache.add`` only writes the open marker if it is not already
    present, so concurrent workers cannot re-open an already-open breaker.
    """
    now = time.time()
    bucket = math.floor(now / CB_WINDOW_SECONDS)
    key = f"{CB_COUNT_PREFIX}{bucket}"
    count = increment_atomic_bucket(key, CB_WINDOW_SECONDS)
    if count > CB_THRESHOLD:
        cache.add(CB_OPEN_KEY, now, timeout=CB_WINDOW_SECONDS)
        return True, CB_WINDOW_SECONDS
    return False, 0


# -- per-IP abuse strikes ----------------------------------------------------


def _strike_key(client_ip: str, scope: str) -> str:
    return f"strikes:{scope}:{hash_identifier(client_ip)}"


def _lockout_key(client_ip: str, scope: str) -> str:
    return f"lockout:{scope}:{hash_identifier(client_ip)}"


def is_ip_locked_out(client_ip: str, scope: str) -> bool:
    return cache.get(_lockout_key(client_ip, scope)) is not None


def record_ip_abuse_strike(client_ip: str, scope: str = "check_username") -> bool:
    """Record a rate-limit strike; return True when it escalates to lockout."""
    strike_key = _strike_key(client_ip, scope)
    lockout_key = _lockout_key(client_ip, scope)

    count = increment_atomic_bucket(strike_key, STRIKE_WINDOW_SECONDS)
    if count >= STRIKE_LIMIT:
        cache.set(lockout_key, time.time(), timeout=LOCKOUT_SECONDS)
        cache.delete(strike_key)
        return True
    return False
