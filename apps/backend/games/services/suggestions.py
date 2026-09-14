"""
Game suggestion intake — SBGC-240.

User-submitted game suggestions are emailed directly to the operator's
suggestion inbox through Django's configured mail backend (Resend SMTP in
production, per SBGC-239).  Nothing is persisted: the endpoint is a stateless
notification path.

Owns the domain rules the HTTP layer must not carry:

* Storefront-URL validation (an optional absolute ``https://`` URL; the
  ``http:``, ``javascript:``, ``data:``, ``ftp:``, and protocol-relative forms
  are rejected).
* The plain-text message body assembly.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import send_mail


class SuggestionValidationError(ValueError):
    """A game-suggestion payload violates a domain rule."""


def validate_storefront_url(value: str) -> str:
    """Trim and validate an optional storefront URL.

    An empty value is allowed.  A non-empty value must be an absolute
    ``https://`` URL; ``http:``, ``javascript:``, ``data:``, ``ftp:``, and
    protocol-relative (``//host``) forms all fail because they either use a
    different scheme or resolve to no scheme at all.
    """
    url = (value or "").strip()
    if not url:
        return ""

    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise SuggestionValidationError("Storefront URL must be a valid https:// URL.")
    return url


def build_suggestion_email_body(
    *,
    username: str,
    email: str,
    name: str,
    storefront_url: str,
    remarks: str,
) -> str:
    """Assemble the operator-facing plain-text suggestion notice."""
    return (
        "Game Suggestion Received\n"
        "\n"
        f"Submitted By: {username} ({email})\n"
        f"Name: {name}\n"
        f"Storefront URL: {storefront_url or 'None'}\n"
        f"Remarks: {remarks or 'None'}\n"
    )


def send_game_suggestion(
    *,
    username: str,
    email: str,
    name: str,
    storefront_url: str,
    remarks: str,
) -> None:
    """Email a validated suggestion to the configured operator inbox.

    ``fail_silently`` is left False on purpose: a dropped suggestion must
    surface as an error rather than disappearing quietly.
    """
    send_mail(
        subject=f"Game Suggestion Received: {name}",
        message=build_suggestion_email_body(
            username=username,
            email=email,
            name=name,
            storefront_url=storefront_url,
            remarks=remarks,
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.SUGGESTION_RECIPIENT_EMAIL],
        fail_silently=False,
    )


__all__ = [
    "SuggestionValidationError",
    "build_suggestion_email_body",
    "send_game_suggestion",
    "validate_storefront_url",
]
