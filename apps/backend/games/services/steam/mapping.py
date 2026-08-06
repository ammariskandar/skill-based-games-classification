"""
Steam product-type mapping — SBGC-53.

Pure function mapping raw Steam type strings to canonical ContentType
values.  No database access, no network access, no Django ORM import.
"""

from __future__ import annotations

from games.types import ContentType


def map_steam_product_type(raw_type: object) -> str:
    """Map a raw Steam product type string to a canonical content type.

    Returns a string matching ``ContentType`` values (``game``, ``dlc``,
    ``demo``, ``software``, ``soundtrack``, ``unknown``).

    Unknown/non-string types raise ``ValueError`` (malformed payload).
    Unrecognized nonblank strings map to ``ContentType.UNKNOWN``.
    """
    if not isinstance(raw_type, str):
        raise ValueError(
            f"Steam product type must be a string, got {type(raw_type).__name__}."
        )

    key = raw_type.strip().lower()

    if not key:
        raise ValueError("Steam product type must not be blank.")

    _MAP: dict[str, str] = {
        "game": ContentType.GAME,
        "dlc": ContentType.DLC,
        "demo": ContentType.DEMO,
        "software": ContentType.SOFTWARE,
        "music": ContentType.SOUNDTRACK,
        "soundtrack": ContentType.SOUNDTRACK,
    }

    return _MAP.get(key, ContentType.UNKNOWN)
