"""
Rankings query request validation — SBGC-99.

Explicit Pydantic schema for ``GET /api/v1/rankings/`` query parameters:
bounded pagination and strict profile/dimension/direction/dominant enums.
Defaults mirror the historical endpoint behaviour (SBGC-81) so every
previously-valid query keeps its identical response.
"""

from __future__ import annotations

from typing import Annotated, Literal

from ninja import Field, Schema


class RankingsQuerySchema(Schema):
    """Validated query parameters for the public rankings."""

    page: Annotated[int, Field(default=1, ge=1)]
    page_size: Annotated[int, Field(default=24, ge=1, le=100)]
    profile: Literal["unified", "challenge", "reward"] = "unified"
    dimension: Literal["micro", "mystiko", "macro"] = "micro"
    direction: Literal["desc", "asc"] = "desc"
    dominant: Literal["micro", "mystiko", "macro"] | None = None
