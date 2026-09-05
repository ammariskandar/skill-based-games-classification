"""
Email canonicalisation for duplicate detection — SBGC-218.

Google ignores dots in the local part of Gmail addresses and treats
``gmail.com`` / ``googlemail.com`` as the same domain, so ``johnsmith@gmail.com``,
``john.smith@gmail.com``, and ``j.o.h.n.s.m.i.t.h@gmail.com`` all reach the same
mailbox.  Registration-time "email already registered" checks compare this
canonical key instead of the raw address so functionally identical Gmail
addresses cannot be double-registered.

The rule is deliberately scoped to ``gmail.com`` / ``googlemail.com`` only —
dots are significant on every other domain and are left untouched.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Q

# Google delivers both domains to the same mailbox and ignores dots in the
# local part for both.
GMAIL_ALIAS_DOMAINS = frozenset({"gmail.com", "googlemail.com"})
GMAIL_CANONICAL_DOMAIN = "gmail.com"


def normalize_email(email: str) -> str:
    """Return the canonical duplicate-detection key for *email*.

    Trims surrounding whitespace, lower-cases, strips dots from the local part
    when the address is a Gmail alias (and normalises the alias domain to
    ``gmail.com``).  Non-Gmail addresses are only trimmed and lower-cased.
    """
    cleaned = (email or "").strip().lower()
    if "@" not in cleaned:
        return cleaned
    local, domain = cleaned.rsplit("@", 1)
    if domain in GMAIL_ALIAS_DOMAINS:
        local = local.replace(".", "")
        domain = GMAIL_CANONICAL_DOMAIN
    return f"{local}@{domain}"


def email_is_registered(email: str) -> bool:
    """Return whether any account owns an email equivalent to *email*.

    Exact (case-insensitive) lookup first, then — only for Gmail aliases — a
    dot-insensitive scan of stored Gmail/Googlemail addresses.  The sentinel
    ``@gmail.com`` canonical domain makes the non-Gmail case a single indexed
    query.
    """
    canonical = normalize_email(email)
    if not canonical:
        return False
    if User.objects.filter(email__iexact=canonical).exists():
        return True

    # Non-Gmail canonical keys are unchanged from the raw address, so the
    # exact lookup above already decided the result.
    if not canonical.endswith(f"@{GMAIL_CANONICAL_DOMAIN}"):
        return False

    gmail_users = User.objects.filter(
        Q(email__iendswith="@gmail.com") | Q(email__iendswith="@googlemail.com")
    )
    return any(
        normalize_email(stored) == canonical
        for stored in gmail_users.values_list("email", flat=True)
    )


def resolve_active_user_by_email(email: str) -> User | None:
    """Return the active user whose stored email is equivalent to *email*.

    Mirrors :func:`email_is_registered` but resolves the actual account so the
    recovery endpoints (SBGC-219) can dispatch account-specific mail (username
    reminders, password-reset links).  Only ``is_active`` accounts are eligible
    for recovery.
    """
    canonical = normalize_email(email)
    if not canonical:
        return None

    user = User.objects.filter(email__iexact=canonical, is_active=True).first()
    if user is not None:
        return user

    # Non-Gmail canonical keys are unchanged from the raw address, so the exact
    # lookup above already decided the result.
    if not canonical.endswith(f"@{GMAIL_CANONICAL_DOMAIN}"):
        return None

    gmail_users = User.objects.filter(
        Q(email__iendswith="@gmail.com") | Q(email__iendswith="@googlemail.com"),
        is_active=True,
    )
    for stored in gmail_users.only("id", "email"):
        if normalize_email(stored.email) == canonical:
            return stored
    return None
