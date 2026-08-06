"""
Steam Store app-details adapter — SBGC-53.

Fetches and validates application details from the Steam Store API
for a single App ID.  Uses the existing ``SteamClient`` transport.
"""

from __future__ import annotations

from urllib.parse import urlparse

from games.services.steam.adapters import (
    SteamAdapterError,
    SteamMalformedPayloadError,
    SteamMissingRequiredFieldError,
)
from games.services.steam.dto import SteamAppDetails, SteamAppId
from games.services.steam.mapping import map_steam_product_type

# Store appdetails endpoint.
_APP_DETAILS_PATH = "/api/appdetails"


class SteamAppDetailsAdapter:
    """Fetches and validates Steam Store app details for one App ID."""

    def __init__(self, client):
        """*client* must be a ``SteamClient`` instance."""
        self._client = client

    def fetch(self, app_id: SteamAppId) -> SteamAppDetails:
        """Return validated ``SteamAppDetails`` for *app_id*.

        Raises:
            SteamMalformedPayloadError: Response structure is invalid.
            SteamMissingRequiredFieldError: Required field is absent/blank.
            SteamAdapterError: Generic adapter-level failure.
            (Transport exceptions from ``SteamClient`` propagate unchanged.)
        """
        raw = self._client.get_store_api_json(
            _APP_DETAILS_PATH,
            params={"appids": app_id.value},
        )
        return self._parse_response(app_id.value, raw)

    # -- response parsing -------------------------------------------------------

    def _parse_response(self, app_id: str, raw: dict[str, object]) -> SteamAppDetails:
        """Validate and extract ``SteamAppDetails`` from raw JSON."""
        # Root: must be a dict.
        if not isinstance(raw, dict):
            raise SteamMalformedPayloadError(
                f"Steam response must be a JSON object, got {type(raw).__name__}."
            )

        # Root: must contain the requested App ID as key.
        wrapped = raw.get(app_id)
        if wrapped is None:
            raise SteamMalformedPayloadError(
                f"Response missing wrapper key for App ID {app_id}."
            )
        if not isinstance(wrapped, dict):
            raise SteamMalformedPayloadError(
                f"Wrapper for App ID {app_id} must be a dict, "
                f"got {type(wrapped).__name__}."
            )

        # success: bool.
        success = wrapped.get("success")
        if not isinstance(success, bool):
            raise SteamMalformedPayloadError(
                f"'success' must be a bool, got {type(success).__name__}."
            )
        if not success:
            raise SteamAdapterError(
                f"Steam app {app_id} is unavailable (success=false).",
                code="STEAM_APP_UNAVAILABLE",
            )

        # data: dict (required when success=true).
        data = wrapped.get("data")
        if not isinstance(data, dict):
            raise SteamMalformedPayloadError(
                f"'data' must be a dict on success, got {type(data).__name__}."
            )

        # -- required fields -----------------------------------------------------

        name = _require_nonblank_str(data, "name", app_id)
        raw_type = _require_nonblank_str(data, "type", app_id)

        # -- optional fields -----------------------------------------------------

        short_description = _optional_str(data, "short_description")
        header_image_url = _validate_image_url(data.get("header_image"))
        website_url = _validate_website_url(data.get("website"))
        is_free = _optional_bool(data, "is_free")
        developers = _optional_str_list(data, "developers")
        publishers = _optional_str_list(data, "publishers")

        return SteamAppDetails(
            app_id=app_id,
            name=name,
            content_type=map_steam_product_type(raw_type),
            short_description=short_description,
            header_image_url=header_image_url,
            website_url=website_url,
            is_free=is_free,
            developers=developers,
            publishers=publishers,
        )


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------


def _require_nonblank_str(data: dict[str, object], key: str, app_id: str) -> str:
    """Extract a required non-blank string field."""
    value = data.get(key)
    if not isinstance(value, str):
        raise SteamMissingRequiredFieldError(
            f"'{key}' is required and must be a string (App ID {app_id})."
        )
    stripped = value.strip()
    if not stripped:
        raise SteamMissingRequiredFieldError(
            f"'{key}' must not be blank (App ID {app_id})."
        )
    return stripped


def _optional_str(data: dict[str, object], key: str) -> str | None:
    """Extract an optional string field.  Blank → None."""
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _optional_bool(data: dict[str, object], key: str) -> bool | None:
    """Extract an optional boolean field."""
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return None


def _optional_str_list(data: dict[str, object], key: str) -> tuple[str, ...] | None:
    """Extract an optional list of strings."""
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            s = item.strip()
            if s:
                items.append(s)
    return tuple(items) if items else None


def _validate_image_url(value: object) -> str | None:
    """Validate a header image URL.  Returns None for None/blank.

    Non-string types raise ``SteamMalformedPayloadError``.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise SteamMalformedPayloadError(
            f"header_image must be a string or null, got {type(value).__name__}."
        )
    v = value.strip()
    if not v:
        return None
    parsed = urlparse(v)
    if parsed.scheme != "https":
        return None
    if parsed.username or parsed.password:
        return None
    if not parsed.hostname:
        return None
    host = parsed.hostname
    if host.count(".") == 3:
        parts = host.split(".")
        if all(p.isdigit() for p in parts):
            return None
    return v


def _validate_website_url(value: object) -> str | None:
    """Validate an optional website URL.  Returns None for None/blank.

    Non-string types raise ``SteamMalformedPayloadError``.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise SteamMalformedPayloadError(
            f"website must be a string or null, got {type(value).__name__}."
        )
    v = value.strip()
    if not v:
        return None
    parsed = urlparse(v)
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.username or parsed.password:
        return None
    if not parsed.hostname:
        return None
    return v
