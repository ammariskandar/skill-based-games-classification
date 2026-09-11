"""
Similar-Games query validation — SBGC-227.

Bounded ``limit`` for ``GET /api/v1/games/{slug}/similar``.
"""

from __future__ import annotations

from typing import Annotated

from ninja import Field, Schema


class SimilarGamesQuerySchema(Schema):
    """Validated query parameters for the public similar-Games read."""

    limit: Annotated[int, Field(default=6, ge=1, le=24)]
