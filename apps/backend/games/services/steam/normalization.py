"""
Steam metadata normalization — SBGC-188.

Pure functions that convert raw Steam Store payload values into the canonical
plain-text/date forms persisted on ``Game``.  No network, no Django ORM.

These are the single owners of:

- description normalization (short/store description → safe plain text);
- developer normalization (list of developer names → comma-joined string);
- release-date normalization (Steam ``release_date`` object → ``date``).
"""

from __future__ import annotations

import html
from datetime import date, datetime

# Steam's store API returns ``release_date.date`` as "DD Mon, YYYY" in English
# month abbreviations (e.g. "18 Apr, 2011").  ``%d %b`` is deterministic under
# Python's default "C" locale.  The client does not set a language override.
_STEAM_RELEASE_DATE_FORMAT = "%d %b, %Y"


def normalize_steam_description(value: object) -> str | None:
    """Normalize a Steam short/store description to safe plain text.

    - ``None`` / non-string → ``None`` (absent/unusable).
    - HTML entities are decoded (``&quot;`` → ``"``) so the public description
      renders correctly under the frontend's own escaping; no HTML is injected.
    - Surrounding whitespace is stripped; blank → ``None``.
    - Legitimate Unicode is preserved.
    """
    if not isinstance(value, str):
        return None
    unescaped = html.unescape(value)
    stripped = unescaped.strip()
    return stripped if stripped else None


def normalize_steam_developer(value: object) -> str | None:
    """Normalize a Steam developers list to a comma-joined string.

    - ``None`` / non-list → ``None``.
    - entries are trimmed and empty entries are ignored;
    - upstream order is preserved;
    - exact duplicates are removed (dedup);
    - no alphabetical reordering, no publisher/developer synthesis.
    """
    if not isinstance(value, (list, tuple)):
        return None

    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        items.append(stripped)

    return ", ".join(items) if items else None


def normalize_steam_release_date(value: object) -> date | None:
    """Normalize a Steam ``release_date`` object to a ``date``.

    Steam shape: ``{"coming_soon": bool, "date": "18 Apr, 2011"}``.

    - missing/non-dict → ``None``;
    - ``coming_soon`` truthy → ``None`` (no fabricated date);
    - valid "DD Mon, YYYY" → ``date``;
    - blank/malformed/unrecognized → ``None`` (safe absence).
    """
    if not isinstance(value, dict):
        return None
    if value.get("coming_soon"):
        return None

    raw_date = value.get("date")
    if not isinstance(raw_date, str):
        return None
    stripped = raw_date.strip()
    if not stripped:
        return None

    try:
        return datetime.strptime(stripped, _STEAM_RELEASE_DATE_FORMAT).date()
    except ValueError:
        return None


__all__ = [
    "normalize_steam_description",
    "normalize_steam_developer",
    "normalize_steam_release_date",
]
