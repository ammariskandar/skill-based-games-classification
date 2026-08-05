"""
Steam HTTP client — SBGC-42 / SBGC-168.

Synchronous, injectable client for the Steam Web API.  Uses Requests
with urllib3 Retry for bounded idempotent retries.

SBGC-168 changes:
- Origins from games.services.steam.constants (immutable code constants).
- Response processing: status classified first, error body bounded-drained,
  successful body streamed once with single join.
- Media-type regex: accepts application/json, application/*+json,
  with optional parameters; rejects text/json and malformed types.
- Retry: explicit backoff_max and retry_after_max from sleep cap.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from games.services.steam.constants import STEAM_WEB_API_ORIGIN
from games.services.steam.errors import (
    SteamAuthenticationError,
    SteamConfigurationError,
    SteamConnectionError,
    SteamInvalidResponseError,
    SteamNotFoundError,
    SteamRateLimitedError,
    SteamRedirectError,
    SteamResponseTooLargeError,
    SteamTimeoutError,
    SteamUpstreamError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Accept: application/json or application/<subtype>+json with optional params.
# Rejects: text/json, application/jsonx, application/+json, missing subtype.
_JSON_MEDIA_RE = re.compile(
    r"^application/(?:[a-zA-Z0-9][a-zA-Z0-9.+-]*\+)?json(?:\s*;.*)?$"
)

# Status codes that trigger a retry.
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

# Status codes that must never be retried.
_NON_RETRYABLE = frozenset({401, 403})

# Allowed HTTP methods for retry.
_RETRY_METHODS = frozenset({"GET", "HEAD"})


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

_TRAVERSAL_RE = re.compile(r"^(?:%2[eE]|\.)(?:%2[eE]|\.)(?:/|%2[fF]|$)", re.IGNORECASE)


def _validate_path(path: str) -> str:
    """Validate a relative Steam API path.  Returns the path unchanged."""
    if not isinstance(path, str):
        raise SteamConfigurationError("API path must be a string.")
    if path.startswith("//"):
        raise SteamConfigurationError(
            "API path must be relative, not protocol-relative."
        )
    if not path.startswith("/"):
        raise SteamConfigurationError("API path must start with '/'.")
    if path == "/":
        raise SteamConfigurationError("API path must not be root-only.")
    if "://" in path:
        raise SteamConfigurationError("API path must be relative, not an absolute URL.")
    if "\\" in path:
        raise SteamConfigurationError("API path must not contain backslashes.")
    if "?" in path:
        raise SteamConfigurationError(
            "API path must not contain a query string — use the 'params' argument."
        )
    if "#" in path:
        raise SteamConfigurationError("API path must not contain a fragment.")
    if "@" in path:
        raise SteamConfigurationError("API path must not contain credentials.")

    segments = path.lstrip("/").split("/")
    for seg in segments:
        if seg in (".", ".."):
            raise SteamConfigurationError(
                "API path must not contain dot-segment traversal."
            )
        if _TRAVERSAL_RE.match(seg):
            raise SteamConfigurationError(
                "API path must not contain encoded dot-segment traversal."
            )

    return path


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SteamClient:
    """
    Synchronous Steam Web API client.

    Constructor accepts an immutable ``SteamClientConfig`` and an optional
    pre-configured ``requests.Session``.  When no session is injected the
    client creates its own with retry and timeout configuration.
    """

    def __init__(
        self,
        config,  # SteamClientConfig (lazy import to avoid circular)
        *,
        session: requests.Session | None = None,
    ) -> None:
        from games.services.steam.config import SteamClientConfig

        if not isinstance(config, SteamClientConfig):
            raise TypeError("config must be a SteamClientConfig instance.")

        self._config = config
        self._owned_session = session is None
        self._session = session or self._build_session(config)

    # -- session factory -------------------------------------------------------

    @staticmethod
    def _build_session(config) -> requests.Session:
        """Create a configured Requests Session with retry adapter."""
        cap = config.retry_sleep_max_seconds
        retry = Retry(
            total=config.max_retries,
            connect=config.max_retries,
            read=config.max_retries,
            redirect=0,
            status=config.max_retries,
            status_forcelist=list(_RETRY_STATUSES),
            allowed_methods=_RETRY_METHODS,
            backoff_factor=config.retry_backoff,
            backoff_max=cap,
            retry_after_max=cap,
            raise_on_redirect=False,
            raise_on_status=False,
            respect_retry_after_header=True,
            other=0,
        )

        adapter = HTTPAdapter(max_retries=retry)
        session = requests.Session()
        session.mount("https://", adapter)
        session.headers.update(
            {
                "User-Agent": "MyGameDNA/1.0 (+https://mygamedna.com)",
                "Accept": "application/json",
            }
        )
        return session

    # -- context manager -------------------------------------------------------

    def close(self) -> None:
        """Close the underlying session if it is owned by this client."""
        if self._owned_session and self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self) -> SteamClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # -- request ---------------------------------------------------------------

    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        requires_api_key: bool = False,
    ) -> dict[str, object]:
        """Perform a GET request and return the decoded JSON object."""
        _validate_path(path)

        api_key = self._config.api_key
        if api_key is not None:
            api_key = api_key.strip()
            if not api_key:
                api_key = None

        if requires_api_key and not api_key:
            raise SteamConfigurationError(
                "STEAM_WEB_API_KEY is required for this request."
            )

        url = f"{STEAM_WEB_API_ORIGIN}{path}"

        headers: dict[str, str] = {}
        if api_key:
            headers["x-webapi-key"] = api_key

        params_dict = dict(params) if params else {}
        timeout = (self._config.connect_timeout, self._config.read_timeout)

        try:
            response = self._session.get(
                url,
                params=params_dict,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
        except requests.exceptions.Timeout as exc:
            raise SteamTimeoutError("Steam request timed out.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise SteamConnectionError("Could not connect to Steam.") from exc
        except requests.exceptions.RequestException as exc:
            raise SteamConnectionError("Steam request failed.") from exc

        try:
            return self._process_response(response)
        finally:
            try:
                response.close()
            except Exception:
                pass

    # -- response processing ---------------------------------------------------

    def _process_response(self, response: requests.Response) -> dict[str, object]:
        """Classify and decode a Steam response."""
        status = response.status_code

        # -- Redirect (3xx) ----------------------------------------------------
        if 300 <= status < 400:
            _drain_and_close(response)
            raise SteamRedirectError(
                "Steam returned an unexpected redirect.", status=status
            )

        # -- Error status — classify first, then bounded-drain body ------------
        if status >= 400:
            error_exc = self._classify_error_status(status, response)
            _drain_and_close(response)
            raise error_exc

        # -- Success (2xx) — bounded body read, then validate ------------------
        body = _read_body_bounded(response, self._config.max_response_bytes)

        if not body:
            raise SteamInvalidResponseError("Steam response body was empty.")

        content_type = response.headers.get("Content-Type", "")
        if not _JSON_MEDIA_RE.match(content_type):
            raise SteamInvalidResponseError(
                f"Unexpected Content-Type: {content_type!r}."
            )

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SteamInvalidResponseError(
                "Steam response contained invalid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise SteamInvalidResponseError(
                f"Steam JSON response must be an object, got {type(data).__name__}."
            )

        return data

    def _classify_error_status(
        self, status: int, response: requests.Response
    ) -> Exception:
        """Return the appropriate exception for a non-2xx status."""
        if status == 401 or status == 403:
            return SteamAuthenticationError(
                "Steam API authentication failed.", status=status
            )
        if status == 404:
            return SteamNotFoundError("Steam resource not found.", status=status)
        if status == 429:
            ra = _parse_retry_after(response)
            return SteamRateLimitedError(
                "Steam rate limit exceeded.", status=status, retry_after=ra
            )
        if status >= 500:
            return SteamUpstreamError(
                f"Steam upstream error (HTTP {status}).", status=status
            )
        if status >= 400:
            return SteamUpstreamError(
                f"Steam client error (HTTP {status}).", status=status
            )
        return SteamUpstreamError(f"Steam error (HTTP {status}).", status=status)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_body_bounded(response: requests.Response, max_bytes: int) -> bytes:
    """Stream response body into a single joined bytes object, bounded."""
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise SteamResponseTooLargeError(
                    f"Response Content-Length ({content_length}) "
                    f"exceeds limit ({max_bytes} bytes)."
                )
        except ValueError:
            pass

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=8192):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise SteamResponseTooLargeError(
                f"Response body exceeds limit ({max_bytes} bytes)."
            )
        chunks.append(chunk)

    return b"".join(chunks)


def _drain_and_close(response: requests.Response) -> None:
    """Bounded-drain the response body for connection hygiene, then close."""
    try:
        total = 0
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                total += len(chunk)
                if total > 1_048_576:  # 1 MiB drain limit for error bodies
                    break
    except Exception:
        pass
    finally:
        try:
            response.close()
        except Exception:
            pass


def _parse_retry_after(response: requests.Response) -> int | None:
    """Parse Retry-After header into a bounded integer, or None."""
    value = response.headers.get("Retry-After", "").strip()
    if not value:
        return None
    try:
        seconds = int(value)
    except ValueError:
        return None
    if seconds < 0:
        return None
    return min(seconds, 3600)


__all__ = ["SteamClient"]
