"""
Steam service package — SBGC-42 / SBGC-168.

Provides a synchronous HTTP client for the Steam Web API with
validated configuration, bounded retries, and isolated testing support.
"""

from games.services.steam.cdn import validate_steam_cdn_url
from games.services.steam.client import SteamClient
from games.services.steam.config import SteamClientConfig
from games.services.steam.constants import STEAM_STORE_API_ORIGIN, STEAM_WEB_API_ORIGIN
from games.services.steam.errors import (
    SteamAuthenticationError,
    SteamConfigurationError,
    SteamConnectionError,
    SteamError,
    SteamInvalidResponseError,
    SteamNotFoundError,
    SteamRateLimitedError,
    SteamRedirectError,
    SteamRequestError,
    SteamResponseError,
    SteamResponseTooLargeError,
    SteamTimeoutError,
    SteamUpstreamError,
)

__all__ = [
    "SteamClient",
    "SteamClientConfig",
    "STEAM_WEB_API_ORIGIN",
    "STEAM_STORE_API_ORIGIN",
    "validate_steam_cdn_url",
    # Errors
    "SteamError",
    "SteamConfigurationError",
    "SteamRequestError",
    "SteamConnectionError",
    "SteamTimeoutError",
    "SteamRedirectError",
    "SteamResponseError",
    "SteamAuthenticationError",
    "SteamRateLimitedError",
    "SteamNotFoundError",
    "SteamUpstreamError",
    "SteamInvalidResponseError",
    "SteamResponseTooLargeError",
]
