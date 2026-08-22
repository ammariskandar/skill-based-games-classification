"""
Steam Library asset URL construction — SBGC-184.

Pure helpers that build the official Steam Library Hero and Library Capsule
CDN URLs from a validated App ID.  These assets are not present in the
standard Store ``appdetails`` response; Steam serves them as deterministic
official CDN files.

Django remains the authority for Steam metadata, so these URLs are
constructed here — never in Astro — and persisted as source-managed fields on
``Game``.  Astro renders whatever the public Game DTO exposes.
"""

from __future__ import annotations

# Canonical Steam CDN base for library artwork.  This host serves the official
# assets and sends ``Access-Control-Allow-Origin: *`` (required for the
# browser-side WebSR pixel read on the Library Capsule).
_LIBRARY_CDN_BASE = "https://cdn.cloudflare.steamstatic.com/steam/apps"


def build_library_hero_url(app_id: str) -> str:
    """Return the official Steam Library Hero URL for *app_id*.

    The Library Hero is the wide atmospheric background asset.  It is never
    WebSR-upscaled — it is displayed softened/dimmed as the background layer.
    """
    return f"{_LIBRARY_CDN_BASE}/{app_id}/library_hero.jpg"


def build_library_capsule_url(app_id: str) -> str:
    """Return the official Steam Library Capsule (portrait) URL for *app_id*.

    The Library Capsule is the portrait key-art / box-art foreground element.
    It is the only Steam asset eligible for browser-side WebSR enhancement.
    """
    return f"{_LIBRARY_CDN_BASE}/{app_id}/library_600x900.jpg"


def build_steam_library_asset_urls(app_id: str) -> tuple[str, str]:
    """Return ``(hero_url, capsule_url)`` for *app_id*."""
    return (
        build_library_hero_url(app_id),
        build_library_capsule_url(app_id),
    )


__all__ = [
    "build_library_hero_url",
    "build_library_capsule_url",
    "build_steam_library_asset_urls",
]
