"""
Brute-force login rate limiting — SBGC-217.

Dual-key bucket throttling via Django's cache framework: five failed login
attempts per 60 seconds per client IP **and** per normalized username.  The
two buckets are independent so an attacker cannot bypass an IP limit by
spraying many usernames, nor a username limit by rotating source IPs.
"""

from django.core.cache import cache
from django.http import HttpRequest

FAILED_LOGIN_LIMIT = 5
FAILED_LOGIN_TIMEOUT_SECONDS = 60


def get_client_ip(request: HttpRequest) -> str:
    """Return the originating client IP, honouring a single-proxy XFF header."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


def _ip_key(ip: str) -> str:
    return f"auth_fail_ip:{ip}"


def _user_key(username: str) -> str:
    return f"auth_fail_user:{username.strip().lower()}"


def is_login_rate_limited(request: HttpRequest, username: str) -> bool:
    """True when either the IP or the username bucket has hit the limit."""
    ip = get_client_ip(request)
    ip_attempts = cache.get(_ip_key(ip), 0)
    user_attempts = cache.get(_user_key(username), 0)
    return ip_attempts >= FAILED_LOGIN_LIMIT or user_attempts >= FAILED_LOGIN_LIMIT


def record_failed_login(request: HttpRequest, username: str) -> None:
    """Increment both failure buckets, seeding a 60s TTL on first hit."""
    ip = get_client_ip(request)
    for key in (_ip_key(ip), _user_key(username)):
        value = cache.get(key, 0)
        if value == 0:
            cache.set(key, 1, timeout=FAILED_LOGIN_TIMEOUT_SECONDS)
        else:
            cache.incr(key)


def clear_failed_login(request: HttpRequest, username: str) -> None:
    """Reset both buckets after a successful authentication."""
    ip = get_client_ip(request)
    cache.delete(_ip_key(ip))
    cache.delete(_user_key(username))
