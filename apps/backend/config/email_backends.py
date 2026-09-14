"""
Email backends — SBGC-239.

Two backends, wired together by production settings:

- ``ZeptoMailApiEmailBackend`` delivers through ZeptoMail's HTTPS API.  SMTP is
  not an option on hosts that block outbound 25/465/587 (Render free web
  services) and ZeptoMail supports only 465/587, so port 443 is the sole
  transport that works there.
- ``FailoverEmailBackend`` tries the primary backend and, if it raises, retries
  the same messages through the secondary.  The production pairing is Resend
  SMTP (primary) → ZeptoMail HTTPS (secondary).

Neither backend is active unless production settings select it; test and
development keep Django's standard behaviour.  No secret is ever logged.
"""

from __future__ import annotations

import logging
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

ZEPTOMAIL_DEFAULT_API_URL = "https://api.zeptomail.com/v1.1/email"
ZEPTOMAIL_DEFAULT_TIMEOUT_SECONDS = 10
ZEPTOMAIL_DEFAULT_FROM_NAME = "MyGameDNA"


class EmailDeliveryError(Exception):
    """A provider rejected the message or could not be reached."""


class ZeptoMailApiEmailBackend(BaseEmailBackend):
    """Send mail through ZeptoMail's HTTPS API.

    ZeptoMail authenticates with a per-Agent "Send API key" passed as a
    ``Zoho-enczapikey`` authorization header.  The provider's error body is
    surfaced (truncated) because it names the failing field — e.g. an unverified
    sender domain — and contains no credential.
    """

    def __init__(
        self,
        fail_silently: bool = False,
        *,
        send_token: str | None = None,
        api_url: str | None = None,
        from_name: str | None = None,
        timeout: float | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(fail_silently=fail_silently)
        self.send_token = (
            send_token or getattr(settings, "ZEPTOMAIL_SEND_TOKEN", "") or ""
        ).strip()
        self.api_url = api_url or getattr(
            settings, "ZEPTOMAIL_API_URL", ZEPTOMAIL_DEFAULT_API_URL
        )
        self.from_name = from_name or getattr(
            settings, "ZEPTOMAIL_FROM_NAME", ZEPTOMAIL_DEFAULT_FROM_NAME
        )
        self.timeout = float(
            timeout
            if timeout is not None
            else getattr(
                settings, "ZEPTOMAIL_TIMEOUT_SECONDS", ZEPTOMAIL_DEFAULT_TIMEOUT_SECONDS
            )
        )

    def send_messages(self, email_messages) -> int:
        if not email_messages:
            return 0
        if not self.send_token:
            raise ImproperlyConfigured(
                "ZEPTOMAIL_SEND_TOKEN must be set to use ZeptoMailApiEmailBackend."
            )

        sent = 0
        for message in email_messages:
            try:
                self._send(message)
            except Exception:
                if not self.fail_silently:
                    raise
                logger.warning(
                    "ZeptoMail delivery failed; message dropped.", exc_info=True
                )
                continue
            sent += 1
        return sent

    def _send(self, message) -> None:
        payload = self._payload(message)
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Zoho-enczapikey {self.send_token}",
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise EmailDeliveryError(
                f"ZeptoMail request failed: {type(exc).__name__}"
            ) from exc

        if response.status_code >= 400:
            raise EmailDeliveryError(
                f"ZeptoMail rejected the message ({response.status_code}): "
                f"{response.text[:300]}"
            )

    def _payload(self, message) -> dict:
        from_name, from_address = parseaddr(
            message.from_email or settings.DEFAULT_FROM_EMAIL
        )
        payload: dict = {
            "from": {"address": from_address, "name": from_name or self.from_name},
            "to": [
                {"email_address": {"address": address, "name": ""}}
                for address in message.to
            ],
            "subject": message.subject,
        }
        if message.cc:
            payload["cc"] = [
                {"email_address": {"address": address, "name": ""}}
                for address in message.cc
            ]
        if message.bcc:
            payload["bcc"] = [
                {"email_address": {"address": address, "name": ""}}
                for address in message.bcc
            ]

        # Django >= 4.2 exposes alternatives as EmailAlternative(content, mimetype)
        # namedtuples rather than MIME parts.
        html_body = next(
            (
                alternative.content
                for alternative in getattr(message, "alternatives", [])
                if alternative.mimetype == "text/html"
            ),
            None,
        )
        if html_body:
            payload["htmlbody"] = html_body
            payload["textbody"] = message.body
        else:
            payload["textbody"] = message.body
        return payload


class FailoverEmailBackend(BaseEmailBackend):
    """Try the primary backend, then the secondary if the primary raises.

    Failover triggers on any exception.  A message the primary accepted but whose
    response was lost can therefore be delivered twice; for transactional
    verification and reset mail that trade favours availability.  The primary is
    built with ``fail_silently=False`` so its failure is always observable, and
    ``fail_silently`` is honoured on the secondary — which is the last resort.
    """

    def __init__(self, fail_silently: bool = False, **kwargs: object) -> None:
        super().__init__(fail_silently=fail_silently)
        self.primary_backend = str(
            getattr(settings, "EMAIL_FAILOVER_PRIMARY_BACKEND", "")
        )
        self.secondary_backend = str(
            getattr(settings, "EMAIL_FAILOVER_SECONDARY_BACKEND", "")
        )
        if not self.primary_backend or not self.secondary_backend:
            raise ImproperlyConfigured(
                "EMAIL_FAILOVER_PRIMARY_BACKEND and EMAIL_FAILOVER_SECONDARY_BACKEND "
                "must both be set when FailoverEmailBackend is used."
            )
        self._primary = get_connection(
            backend=self.primary_backend, fail_silently=False
        )
        self._secondary = get_connection(
            backend=self.secondary_backend, fail_silently=False
        )

    def send_messages(self, email_messages) -> int:
        if not email_messages:
            return 0

        try:
            return self._primary.send_messages(email_messages)
        except Exception:
            logger.error(
                "Primary email backend %s failed; failing over to %s.",
                self.primary_backend,
                self.secondary_backend,
                exc_info=True,
            )

        try:
            return self._secondary.send_messages(email_messages)
        except Exception:
            if not self.fail_silently:
                raise
            logger.exception("Secondary email backend failed; message dropped.")
            return 0


__all__ = [
    "EmailDeliveryError",
    "FailoverEmailBackend",
    "ZeptoMailApiEmailBackend",
]
