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
from games.services.steam.cdn import validate_steam_image_url
from games.services.steam.dto import SteamAppDetails, SteamAppId
from games.services.steam.mapping import map_steam_product_type
from games.services.steam.normalization import (
    normalize_steam_description,
    normalize_steam_developer,
    normalize_steam_release_date,
)
from games.types import ContentType

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

        # -- content type --------------------------------------------------------

        # The Steam ``type`` field is optional: absent/null/blank/non-string
        # payloads fail safe to UNKNOWN instead of crashing the import/refresh
        # pipeline (SBGC-95).  A genuine nonblank string is classified
        # deterministically by the canonical mapping (unrecognized values also
        # resolve to UNKNOWN, which is never publicly listable).
        raw_type = _optional_type(data)

        # -- optional fields -----------------------------------------------------

        description = normalize_steam_description(data.get("short_description"))
        developer = normalize_steam_developer(data.get("developers"))
        release_date = normalize_steam_release_date(data.get("release_date"))
        header_image_url = validate_steam_image_url(data.get("header_image"))
        website_url = _validate_website_url(data.get("website"))
        is_free = _optional_bool(data, "is_free")
        publishers = _optional_str_list(data, "publishers")

        return SteamAppDetails(
            app_id=app_id,
            name=name,
            content_type=(
                map_steam_product_type(raw_type)
                if raw_type is not None
                else ContentType.UNKNOWN
            ),
            description=description,
            developer=developer,
            release_date=release_date,
            header_image_url=header_image_url,
            website_url=website_url,
            is_free=is_free,
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


def _optional_type(data: dict[str, object]) -> str | None:
    """Extract the optional Steam ``type`` field.

    Returns ``None`` for absent/null/blank/non-string values so the caller
    fails safe to ``ContentType.UNKNOWN`` — an ambiguous payload must never
    crash the import/refresh pipeline (SBGC-95).  A genuine nonblank string
    is returned as-is for ``map_steam_product_type``.
    """
    value = data.get("type")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


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
