"""
Pre-registration email verification & anti-abuse engine — SBGC-218.

Keeps unverified accounts out of ``auth_user`` by routing registration
through an ephemeral, single-use challenge stored in Django's cache.  Also
owns the reCAPTCHA v3 score check and the 30-minute resend lockout.

Zero email enumeration: the caller always receives a generic
``challenge_id`` regardless of whether the address is already registered;
the distinction is only ever communicated in the email body.
"""

from __future__ import annotations

import uuid

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

CHALLENGE_TIMEOUT = 900  # 15 minutes
LOCKOUT_TIMEOUT = 1800  # 30 minutes
MAX_RESEND_ATTEMPTS = 3

CHALLENGE_KEY_PREFIX = "email_challenge:"
RESEND_IP_KEY_PREFIX = "resend_limit_ip:"
RESEND_EMAIL_KEY_PREFIX = "resend_limit_email:"

signer = TimestampSigner(salt="email-verification-salt")


def verify_recaptcha(token: str, remote_ip: str | None = None) -> bool:
    """Verify a reCAPTCHA v3 token, requiring a score >= 0.5.

    Bypasses in test/debug for the canonical test token, and when no
    ``RECAPTCHA_SECRET_KEY`` is configured (local development without a key).
    """
    if settings.DEBUG and token == "test-recaptcha-token":
        return True
    secret = getattr(settings, "RECAPTCHA_SECRET_KEY", "")
    if not secret:
        return True
    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data=payload,
            timeout=5.0,
        )
        data = res.json()
        return bool(data.get("success") and data.get("score", 0.0) >= 0.5)
    except Exception:
        return False


def is_signup_rate_limited(ip: str, email: str) -> bool:
    ip_key = f"{RESEND_IP_KEY_PREFIX}{ip}"
    email_key = f"{RESEND_EMAIL_KEY_PREFIX}{email.lower().strip()}"
    return (
        cache.get(ip_key, 0) >= MAX_RESEND_ATTEMPTS
        or cache.get(email_key, 0) >= MAX_RESEND_ATTEMPTS
    )


def increment_resend_attempt(ip: str, email: str) -> None:
    for key in (
        f"{RESEND_IP_KEY_PREFIX}{ip}",
        f"{RESEND_EMAIL_KEY_PREFIX}{email.lower().strip()}",
    ):
        value = cache.get(key, 0)
        if value == 0:
            cache.set(key, 1, timeout=LOCKOUT_TIMEOUT)
        else:
            cache.incr(key)


def _challenge_key(challenge_id: str) -> str:
    return f"{CHALLENGE_KEY_PREFIX}{challenge_id}"


def get_challenge(challenge_id: str) -> dict | None:
    """Return the cached challenge dict, or None when absent/expired."""
    return cache.get(_challenge_key(challenge_id))


def delete_challenge(challenge_id: str) -> None:
    """Remove a challenge (single-use guarantee after registration)."""
    cache.delete(_challenge_key(challenge_id))


def _send_verification_email(email: str, verification_url: str) -> None:
    send_mail(
        subject="Verify your email for MyGameDNA",
        message=(
            "Click the link below to verify your email address:\n\n"
            f"{verification_url}\n\nThis link expires in 15 minutes."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


def send_existing_account_email(email: str) -> None:
    """Email an already-registered address without revealing anything to the caller."""
    send_mail(
        subject="MyGameDNA account already exists",
        message=(
            "An account already exists for this email address. "
            "Please log in instead of signing up."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


def create_email_challenge(email: str, base_url: str = "http://localhost:4321") -> str:
    """Create a PENDING cache challenge and email the signed verification link."""
    normalized_email = email.strip().lower()
    challenge_id = str(uuid.uuid4())
    cache.set(
        _challenge_key(challenge_id),
        {"email": normalized_email, "status": "PENDING"},
        timeout=CHALLENGE_TIMEOUT,
    )
    token = signer.sign(f"{challenge_id}:{normalized_email}")
    verification_url = f"{base_url}/verify-email?token={token}"
    _send_verification_email(normalized_email, verification_url)
    return challenge_id


def confirm_email_challenge(token: str) -> bool:
    """Verify a signed token and transition its challenge to VERIFIED."""
    try:
        unsigned = signer.unsign(token, max_age=CHALLENGE_TIMEOUT)
        challenge_id, email = unsigned.split(":", 1)
    except (BadSignature, SignatureExpired, ValueError):
        return False

    data = cache.get(_challenge_key(challenge_id))
    if not data or data.get("email") != email:
        return False

    data["status"] = "VERIFIED"
    cache.set(_challenge_key(challenge_id), data, timeout=CHALLENGE_TIMEOUT)
    return True
