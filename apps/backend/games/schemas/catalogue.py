"""
Catalogue query request validation — SBGC-99.

Explicit Pydantic schema for ``GET /api/v1/games/`` query parameters:
bounded pagination, strict enum/boolean parsing, and search-query
sanitization (control-character stripping, whitespace trimming, empty →
``None``) before the catalogue service runs.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from ninja import Field, Schema
from pydantic import field_validator

CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x1f\x7f]")


class GameCatalogueQuerySchema(Schema):
    """Validated query parameters for the public game catalogue."""

    page: Annotated[int, Field(default=1, ge=1)]
    page_size: Annotated[int, Field(default=24, ge=1, le=100)]
    q: Annotated[str | None, Field(default=None, max_length=100)] = None
    source: Literal["steam", "manual"] | None = None
    classified: bool | None = None
    profile: Literal["challenge", "reward"] = "challenge"
    sort: Literal["name_asc", "name_desc", "recent", "micro", "mystiko", "macro"] = (
        "name_asc"
    )
    dominant: Literal["micro", "mystiko", "macro"] | None = None
    coverless_last: bool = True

    @field_validator("q", mode="before")
    @classmethod
    def sanitize_search_query(cls, value: object) -> str | None:
        """Strip control characters and whitespace; empty → ``None``.

        Runs before length validation so the ``max_length=100`` bound applies
        to the *cleaned* query, and so whitespace-only queries become
        ``None`` (downstream skips search filtering entirely).
        """
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Search query must be a string")
        cleaned = CONTROL_CHAR_REGEX.sub("", value).strip()
        return cleaned if cleaned else None
