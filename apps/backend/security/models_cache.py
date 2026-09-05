"""
VPN login challenge state machine — SBGC-106.

The adaptive 30-minute challenge, per-user/IP whitelist, and security-lockout
markers all live in Django's cache (Redis in production, LocMem in dev/test)
so multi-worker state never drifts process-locally.  The raw challenge data
contract and TTLs are owned here.
"""

from __future__ import annotations

import logging
import uuid

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone

from security.ip_engine import is_flagged_ip

logger = logging.getLogger("django.security")

CHALLENGE_TIMEOUT = 3600  # 1 hour cache TTL
CHALLENGE_READ_ONLY_AFTER = 1800  # 30 minutes of PENDING before Read-Only

CHALLENGE_KEY_PREFIX = "admin_vpn_challenge:"
WHITELIST_KEY_PREFIX = "admin_vpn_whitelist:"
LOCKED_USER_KEY_PREFIX = "sec_locked_user:"

WHITELIST_TTL = 30 * 24 * 3600  # 30 days

# Statuses: PENDING | APPROVED | REJECTED | READ_ONLY
PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
READ_ONLY = "READ_ONLY"

review_signer = TimestampSigner(salt="admin-login-review")


def _challenge_key(challenge_id: str) -> str:
    return f"{CHALLENGE_KEY_PREFIX}{challenge_id}"


def get_challenge(challenge_id: str | None) -> dict | None:
    """Return the cached challenge dict, or None when absent/expired."""
    if not challenge_id:
        return None
    return cache.get(_challenge_key(challenge_id))


def update_challenge_status(challenge_id: str, status: str) -> bool:
    """Transition a challenge to *status* in place."""
    data = get_challenge(challenge_id)
    if not data:
        return False
    data["status"] = status
    cache.set(_challenge_key(challenge_id), data, timeout=CHALLENGE_TIMEOUT)
    return True


def create_vpn_challenge(user: User, ip_address: str, user_agent: str = "") -> str:
    """Create a PENDING challenge for a flagged login and return its id."""
    challenge_id = str(uuid.uuid4())
    now = timezone.now()
    created_at = now.timestamp()
    cache.set(
        _challenge_key(challenge_id),
        {
            "challenge_id": challenge_id,
            "user_id": user.pk,
            "username": user.username,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "status": PENDING,
            "created_at": created_at,
            "read_only_at": created_at + CHALLENGE_READ_ONLY_AFTER,
            "expires_at": created_at + CHALLENGE_TIMEOUT,
        },
        timeout=CHALLENGE_TIMEOUT,
    )
    return challenge_id


def is_read_only_due(challenge: dict) -> bool:
    """True when a PENDING challenge's 30-minute review window has elapsed."""
    read_only_at = challenge.get("read_only_at")
    if read_only_at is None:
        return False
    return timezone.now().timestamp() >= float(read_only_at)


def is_ip_whitelisted(user_id: int, ip_address: str) -> bool:
    return cache.get(f"{WHITELIST_KEY_PREFIX}{user_id}:{ip_address}") is not None


def whitelist_user_ip(user_id: int, ip_address: str) -> None:
    cache.set(
        f"{WHITELIST_KEY_PREFIX}{user_id}:{ip_address}",
        True,
        timeout=WHITELIST_TTL,
    )


def should_challenge_login(user: User, ip_address: str) -> bool:
    """Decide whether a staff login from *ip_address* must enter the gate."""
    if not ip_address:
        return False
    if is_ip_whitelisted(user.pk, ip_address):
        return False
    return is_flagged_ip(ip_address)


# -- review-link signing -----------------------------------------------------


def sign_review_token(challenge_id: str) -> str:
    return review_signer.sign(challenge_id)


def verify_review_token(token: str) -> str | None:
    try:
        return review_signer.unsign(token, max_age=CHALLENGE_TIMEOUT)
    except (BadSignature, SignatureExpired):
        return None


# -- security lockout --------------------------------------------------------


def is_user_security_locked(user_id: int) -> bool:
    return cache.get(f"{LOCKED_USER_KEY_PREFIX}{user_id}") is not None


def set_user_security_locked(user_id: int, reason: str) -> None:
    cache.set(
        f"{LOCKED_USER_KEY_PREFIX}{user_id}",
        {"reason": reason, "locked_at": timezone.now().isoformat()},
        timeout=None,
    )


def clear_user_security_locked(user_id: int) -> None:
    cache.delete(f"{LOCKED_USER_KEY_PREFIX}{user_id}")


def terminate_user_sessions(user_id: int) -> None:
    """Delete every live session row authenticated as *user_id*."""
    now = timezone.now()
    user_key = str(user_id)
    for session in Session.objects.filter(expire_date__gte=now):
        try:
            session_data = session.get_decoded()
        except Exception:  # noqa: BLE001 — corrupt rows must not block revocation
            session.delete()
            continue
        if session_data.get("_auth_user_id") == user_key:
            session.delete()


def execute_security_lockout(user: User, reason: str) -> None:
    """Freeze a compromised account and terminate its active sessions."""
    user.is_active = False
    user.save(update_fields=["is_active"])
    set_user_security_locked(user.pk, reason)
    terminate_user_sessions(user.pk)
    logger.warning("Security lockout applied to user %s: %s", user.pk, reason)
