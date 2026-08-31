"""
Rankings API router — SBGC-81.

Router ownership boundary for the public ranking read.  The HTTP layer stays
thin: it validates the request, delegates to the rankings service, and maps the
typed result into the response schema.  It owns none of the score derivation,
dominance, ordering, or pagination.
"""

from __future__ import annotations

from api.errors import STANDARD_ERROR_RESPONSES
from api.schemas import ApiErrorResponse
from ninja import Query, Router, Schema

from games.schemas.rankings import RankingsQuerySchema
from games.services.rankings import RankingGame, RankingQuery, get_rankings

router = Router(tags=["Rankings"])

# Module-level singleton so Ninja's Query default is not a function call in an
# argument default (ruff B008); Ninja types Query as Annotated for checkers.
_rankings_query = Query(...)  # pyright: ignore[reportCallIssue]


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
    query: RankingsQuerySchema = _rankings_query,
):
    ranking_query = RankingQuery(
        profile=query.profile,
        dimension=query.dimension,
        direction=query.direction,
        dominant=query.dominant,
        page=query.page,
        page_size=query.page_size,
    )
    result = get_rankings(ranking_query)
    return RankingResponse(
        count=result.count,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        results=[_ranking_item(game) for game in result.results],
    )
