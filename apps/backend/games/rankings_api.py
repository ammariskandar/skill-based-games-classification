"""
Rankings API router — SBGC-81.

Router ownership boundary for the public ranking read.  The HTTP layer stays
thin: it validates the request, delegates to the rankings service, and maps the
typed result into the response schema.  It owns none of the score derivation,
dominance, ordering, or pagination.
"""

from __future__ import annotations

from typing import Literal

from api.errors import STANDARD_ERROR_RESPONSES
from api.schemas import ApiErrorResponse
from ninja import Query, Router, Schema

from games.services.rankings import RankingGame, RankingQuery, get_rankings

router = Router(tags=["Rankings"])


class RankingItem(Schema):
    """One public ranking row: identity, effective Hero, and the score."""

    slug: str
    name: str
    hero_url: str
    score: int | float


class RankingResponse(Schema):
    """Paginated public ranking."""

    count: int
    page: int
    page_size: int
    total_pages: int
    results: list[RankingItem]


def _ranking_item(game: RankingGame) -> RankingItem:
    return RankingItem(
        slug=game.slug,
        name=game.name,
        hero_url=game.hero_url,
        score=game.score,
    )


@router.get(
    "",
    response={
        200: RankingResponse,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="game_rankings",
    summary="List games by ranking score",
    description=(
        "Return a deterministic paginated ranking of publicly-listed base Games. "
        "Supports the Unified/Challenge/Reward profile, a Micro/Macro/Mystiko "
        "dimension, ascending/descending direction, an optional dominant-category "
        "filter, and pagination.  Unified scores are (Challenge + Reward) / 2 and "
        "may end in .5.  Reads persisted state only — never contacts Steam and "
        "never recalculates classification."
    ),
    url_name="game-rankings",
)
def game_rankings(
    request,
    profile: Literal["unified", "challenge", "reward"] = "unified",
    dimension: Literal["micro", "mystiko", "macro"] = "micro",
    direction: Literal["desc", "asc"] = "desc",
    dominant: Literal["micro", "mystiko", "macro"] | None = None,
    page: int = Query(default=1, ge=1),  # pyright: ignore[reportCallIssue]
    page_size: int = Query(default=24, ge=1, le=100),  # pyright: ignore[reportCallIssue]
):
    query = RankingQuery(
        profile=profile,
        dimension=dimension,
        direction=direction,
        dominant=dominant,
        page=page,
        page_size=page_size,
    )
    result = get_rankings(query)
    return RankingResponse(
        count=result.count,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        results=[_ranking_item(game) for game in result.results],
    )
