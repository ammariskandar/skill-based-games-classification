"""
Steam product-type mapping — SBGC-53.

Pure function mapping raw Steam type strings to normalized application
content types.  No database access, no network access.
"""

from __future__ import annotations


def map_steam_product_type(raw_type: object) -> str:
    """Map a raw Steam product type string to a normalized content type.

    Returns one of: ``game``, ``dlc``, ``demo``, ``software``,
    ``soundtrack``, ``unknown``.

    Unknown/non-string types raise ``ValueError`` (malformed payload).
    Unrecognized nonblank strings map to ``unknown``.
    """
    if not isinstance(raw_type, str):
        raise ValueError(
            f"Steam product type must be a string, got {type(raw_type).__name__}."
        )

    key = raw_type.strip().lower()

    if not key:
        raise ValueError("Steam product type must not be blank.")

    _MAP: dict[str, str] = {
        "game": "game",
        "dlc": "dlc",
        "demo": "demo",
        "software": "software",
        "music": "soundtrack",
        "soundtrack": "soundtrack",
    }

    return _MAP.get(key, "unknown")
