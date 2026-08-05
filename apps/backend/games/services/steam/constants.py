"""
Immutable Steam service constants — SBGC-168.

Trusted API and store origins are code constants, not configurable
via dataclass fields, Django settings, or environment variables.
"""

STEAM_WEB_API_ORIGIN = "https://api.steampowered.com"
STEAM_STORE_API_ORIGIN = "https://store.steampowered.com"

__all__ = ["STEAM_WEB_API_ORIGIN", "STEAM_STORE_API_ORIGIN"]
