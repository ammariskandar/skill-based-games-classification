"""
Steam HTTP client — SBGC-42.

Synchronous, injectable client for the Steam Web API.  Uses Requests
with urllib3 Retry for bounded idempotent retries.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

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

# Media types accepted as JSON responses.
_JSON_MEDIA_PATTERN = re.compile(
    r"^application/(?:[a-z]+\+)?json(?:\s*;.*)?$", re.IGNORECASE
)

# Status codes that trigger a retry.
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

# Status codes that must never be retried.
_NON_RETRYABLE = frozenset({401, 403})

# Maximum allowed timeouts.
_MAX_CONNECT_TIMEOUT = 30.0
_MAX_READ_TIMEOUT = 60.0


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

# Paths that are equivalent to dot-segment traversal.
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

    # Dot-segment and encoded dot-segment traversal.
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
        retry = Retry(
            total=config.max_retries,
            connect=config.max_retries,
            read=config.max_retries,
            redirect=0,  # redirects are never followed
            status=config.max_retries,
            status_forcelist=list(_RETRY_STATUSES),
            allowed_methods={"GET", "HEAD"},
            backoff_factor=config.retry_backoff,
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
        """
        Perform a GET request and return the decoded JSON object.

        Args:
            path: Relative API path starting with ``/``.
            params: Optional query parameters.
            requires_api_key: If True, the API key must be configured.

        Returns:
            Decoded JSON object (``dict``).

        Raises:
            SteamConfigurationError: Invalid path or missing API key.
            SteamRequestError / subclasses: Network or timeout failure.
            SteamResponseError / subclasses: Non-2xx response or invalid body.
            SteamResponseTooLargeError: Response exceeds max_response_bytes.
        """
        _validate_path(path)

        # -- API key -----------------------------------------------------------
        api_key = self._config.api_key
        if api_key is not None:
            api_key = api_key.strip()
            if not api_key:
                api_key = None

        if requires_api_key and not api_key:
            raise SteamConfigurationError(
                "STEAM_WEB_API_KEY is required for this request."
            )

        # -- URL ---------------------------------------------------------------
        url = f"{self._config.api_origin}{path}"

        # -- Headers -----------------------------------------------------------
        headers: dict[str, str] = {}
        if api_key:
            headers["x-webapi-key"] = api_key

        # -- Params ------------------------------------------------------------
        params_dict = dict(params) if params else {}

        # -- Timeout -----------------------------------------------------------
        timeout = (self._config.connect_timeout, self._config.read_timeout)

        # -- Perform request ---------------------------------------------------
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

        # -- Process response --------------------------------------------------
        try:
            return self._process_response(response)
        finally:
            response.close()

    # -- response processing ---------------------------------------------------

    def _process_response(self, response: requests.Response) -> dict[str, object]:
        """Classify and decode a Steam response."""
        status = response.status_code

        # -- Redirect ----------------------------------------------------------
        if 300 <= status < 400:
            raise SteamRedirectError(
                "Steam returned an unexpected redirect.",
                status=status,
            )

        # -- Bounded body read -------------------------------------------------
        content_type = response.headers.get("Content-Type", "")

        max_bytes = self._config.max_response_bytes
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    raise SteamResponseTooLargeError(
                        f"Response Content-Length ({content_length}) "
                        f"exceeds limit ({max_bytes} bytes)."
                    )
            except ValueError:
                pass  # malformed Content-Length — enforce during read

        body = b""
        chunks: list[bytes] = []
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                chunks.append(chunk)
                body = b"".join(chunks)
                if len(body) > max_bytes:
                    raise SteamResponseTooLargeError(
                        f"Response body exceeds limit ({max_bytes} bytes)."
                    )

        # -- Error status -------------------------------------------------------
        if status == 401 or status == 403:
            raise SteamAuthenticationError(
                "Steam API authentication failed.", status=status
            )
        if status == 404:
            raise SteamNotFoundError("Steam resource not found.", status=status)
        if status == 429:
            ra = _parse_retry_after(response)
            raise SteamRateLimitedError(
                "Steam rate limit exceeded.", status=status, retry_after=ra
            )
        if status >= 500:
            raise SteamUpstreamError(
                f"Steam upstream error (HTTP {status}).", status=status
            )
        if status >= 400:
            raise SteamUpstreamError(
                f"Steam client error (HTTP {status}).", status=status
            )

        # -- Success body validation -------------------------------------------
        if not body:
            raise SteamInvalidResponseError("Steam response body was empty.")

        if not _JSON_MEDIA_PATTERN.match(content_type):
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    # Bound to a reasonable maximum.
    return min(seconds, 3600)


__all__ = ["SteamClient"]
