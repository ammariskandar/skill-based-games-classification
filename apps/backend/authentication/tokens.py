"""
Pre-registration email verification & anti-abuse engine — SBGC-218 / SBGC-219.

SBGC-218 keeps unverified accounts out of ``auth_user`` by routing registration
through an ephemeral, single-use challenge stored in Django's cache.  Also owns
the reCAPTCHA v3 score check and the 30-minute resend lockout.

SBGC-219 adds the one-chance password-reset machinery: a signed 15-minute token
that is exchanged (once) for an ephemeral cache ``session_nonce``, plus the
post-reset session revocation and security-alert email.  Zero email enumeration:
the recovery endpoints always return the same generic body — the existence of an
account is only ever communicated inside the email body.
"""

from __future__ import annotations

import uuid

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone

CHALLENGE_TIMEOUT = 900  # 15 minutes
LOCKOUT_TIMEOUT = 1800  # 30 minutes
MAX_RESEND_ATTEMPTS = 3

CHALLENGE_KEY_PREFIX = "email_challenge:"
RESEND_IP_KEY_PREFIX = "resend_limit_ip:"
RESEND_EMAIL_KEY_PREFIX = "resend_limit_email:"

# ── SBGC-219 one-chance password-reset keys ────────────────────────────────
RESET_TOKEN_TIMEOUT = 900  # 15 minutes
RESET_TOKEN_KEY_PREFIX = "pw_reset_token:"
RESET_NONCE_KEY_PREFIX = "reset_nonce:"

signer = TimestampSigner(salt="email-verification-salt")
reset_signer = TimestampSigner(salt="password-reset-salt")


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


# ── SBGC-219 one-chance password reset ──────────────────────────────────────


def create_password_reset_token(user: User) -> str:
    """Create a PENDING reset token and return its signed form for emailing.

    The cache entry (``pw_reset_token:<id>``) is the authoritative state; the
    signed string merely names the entry.  A token that is never claimed simply
    expires after :data:`RESET_TOKEN_TIMEOUT`.
    """
    token_id = str(uuid.uuid4())
    cache.set(
        f"{RESET_TOKEN_KEY_PREFIX}{token_id}",
        {"user_id": user.pk, "status": "PENDING"},
        timeout=RESET_TOKEN_TIMEOUT,
    )
    return reset_signer.sign(f"{token_id}:{user.pk}")


def claim_password_reset_token(signed_token: str) -> str | None:
    """Exchange a signed reset token for a single-use session nonce.

    Transitions the underlying token PENDING → CLAIMED so the same signed
    string can never be redeemed twice (reloads/back-navigation reject it),
    then caches a fresh ``session_nonce`` bound to the token.  Returns ``None``
    when the token is invalid, expired, or already claimed.
    """
    try:
        unsigned = reset_signer.unsign(signed_token, max_age=RESET_TOKEN_TIMEOUT)
        token_id, user_id_str = unsigned.split(":", 1)
        user_id = int(user_id_str)
    except (BadSignature, SignatureExpired, ValueError):
        return None

    key = f"{RESET_TOKEN_KEY_PREFIX}{token_id}"
    data = cache.get(key)
    if not data or data.get("user_id") != user_id or data.get("status") != "PENDING":
        return None

    data["status"] = "CLAIMED"
    cache.set(key, data, timeout=RESET_TOKEN_TIMEOUT)

    session_nonce = str(uuid.uuid4())
    cache.set(
        f"{RESET_NONCE_KEY_PREFIX}{session_nonce}",
        {"token_id": token_id, "user_id": user_id},
        timeout=RESET_TOKEN_TIMEOUT,
    )
    return session_nonce


def get_reset_session(session_nonce: str) -> dict | None:
    """Return the cached session-nonce record, or None when absent/expired."""
    return cache.get(f"{RESET_NONCE_KEY_PREFIX}{session_nonce}")


def burn_reset_session_nonce(session_nonce: str) -> None:
    """Delete a session nonce and its parent token (one-chance invalidation)."""
    data = cache.get(f"{RESET_NONCE_KEY_PREFIX}{session_nonce}")
    if not data:
        return
    token_id = data.get("token_id")
    cache.delete(f"{RESET_NONCE_KEY_PREFIX}{session_nonce}")
    if token_id:
        cache.delete(f"{RESET_TOKEN_KEY_PREFIX}{token_id}")


def revoke_all_user_sessions(user_id: int) -> None:
    """Delete every live Django session row authenticated as *user_id*.

    Used after a password change so stolen/forgotten sessions are kicked out
    immediately.  A corrupted session row is deleted rather than allowed to
    block the revocation sweep.
    """
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


def send_username_recovery_email(user: User) -> None:
    """Email the username to the account owner (never revealed to the caller)."""
    send_mail(
        subject="Your MyGameDNA Username",
        message=f"Your username is: {user.username}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_password_reset_email(
    user: User, token: str, base_url: str = "http://localhost:4321"
) -> None:
    """Email the signed one-chance reset link (expires in 15 minutes)."""
    reset_url = f"{base_url}/reset-password?token={token}"
    send_mail(
        subject="Reset your MyGameDNA password",
        message=(
            "We received a request to reset the password for your "
            "MyGameDNA account.\n\n"
            f"Click the link below to reset it:\n{reset_url}\n\n"
            "This link expires in 15 minutes. If you did not request this, "
            "you can safely ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_password_changed_notification(
    user: User, base_url: str = "http://localhost:4321"
) -> None:
    """Alert the account owner after a password change (post-reset)."""
    reset_url = f"{base_url}/reset"
    send_mail(
        subject="Security Alert: Your MyGameDNA password has been changed",
        message=(
            f"Hello {user.username},\n\n"
            "This is a confirmation that the password for your MyGameDNA "
            "account was recently changed.\n\n"
            "If you initiated this change, you can safely ignore this email.\n\n"
            "IF YOU DID NOT MAKE THIS CHANGE, YOUR ACCOUNT MAY BE COMPROMISED.\n"
            "Please visit the following link immediately to secure and reset "
            f"your account:\n{reset_url}\n\n"
            "The MyGameDNA Team"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
