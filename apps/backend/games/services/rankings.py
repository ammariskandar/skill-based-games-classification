"""
Game rankings query service — SBGC-81.

Owns the deterministic public ranking read: profile (unified/challenge/reward),
dimension (micro/macro/mystiko), direction (desc/asc), dominant-category filter,
pagination, and deterministic tie-breaking.  Reads persisted published state only
— never contacts Steam, never probes images, never recalculates classification.

Unified is a presentation-only profile: its dimension score is
(challenge + reward) / 2.  For database-side sorting we annotate the doubled
integer (challenge + reward) and divide only when exposing the public score, so
ordering stays integer-exact and .5 results are preserved without Decimal.
"""

from __future__ import annotations

from dataclasses import dataclass

from classifications.services.published import (
    published_dominant_category,
    published_score,
)
from classifications.skills import SkillCategory
from django.db import models

from games.models import Game

_CATEGORIES = (SkillCategory.MICRO, SkillCategory.MACRO, SkillCategory.MYSTIKO)


class RankingProfile(models.TextChoices):
    """Ranking profile: the two editorial profiles plus a presentation Unified view."""

    UNIFIED = "unified", "Unified"
    CHALLENGE = "challenge", "Challenge"
    REWARD = "reward", "Reward"


class RankingDirection(models.TextChoices):
    """Sort direction for the selected score."""

    DESC = "desc", "Desc"
    ASC = "asc", "Asc"


@dataclass(frozen=True)
class RankingQuery:
    """Parsed ranking filter/sort/pagination inputs."""

    profile: str = RankingProfile.UNIFIED
    dimension: str = SkillCategory.MICRO
    direction: str = RankingDirection.DESC
    dominant: str | None = None
    page: int = 1
    page_size: int = 24


@dataclass(frozen=True)
class RankingGame:
    """One public ranking row."""

    slug: str
    name: str
    hero_url: str
    score: int | float


@dataclass(frozen=True)
class RankingPage:
    """Paginated ranking result."""

    count: int
    page: int
    page_size: int
    total_pages: int
    results: list[RankingGame]


def _validate_query(query: RankingQuery) -> None:
    profiles = set(RankingProfile.values)
    dimensions = set(SkillCategory.values)
    directions = set(RankingDirection.values)

    if query.profile not in profiles:
        raise ValueError(f"profile must be one of {profiles}, got {query.profile!r}.")
    if query.dimension not in dimensions:
        raise ValueError(
            f"dimension must be one of {dimensions}, got {query.dimension!r}."
        )
    if query.direction not in directions:
        raise ValueError(
            f"direction must be one of {directions}, got {query.direction!r}."
        )
    if query.dominant is not None and query.dominant not in dimensions:
        raise ValueError(
            f"dominant must be one of {dimensions} or None, got {query.dominant!r}."
        )


def _sort_score_expression(profile: str, dimension: str):
    """Database-side sort score for *profile*/*dimension*.

    Challenge/Reward use the single integer dimension.  Unified annotates the
    doubled ``challenge + reward`` integer so ordering is exact; the public score
    is halved only when mapping to a DTO.
    """
    if profile == RankingProfile.UNIFIED:
        return published_score("challenge", dimension) + published_score(
            "reward", dimension
        )
    return published_score(profile, dimension)


def _category_score_expressions(profile: str) -> dict[str, object]:
    """Category → score expression for *profile* (Unified sums Challenge + Reward)."""
    if profile == RankingProfile.UNIFIED:
        return {
            category: published_score("challenge", category)
            + published_score("reward", category)
            for category in _CATEGORIES
        }
    return {category: published_score(profile, category) for category in _CATEGORIES}


def _public_score(sort_score: int, profile: str) -> int | float:
    """Public score from the annotated sort score.

    Unified halves the doubled sum and keeps the exact .5 when the sum is odd;
    Challenge/Reward expose the integer dimension unchanged.
    """
    if profile == RankingProfile.UNIFIED:
        if sort_score % 2 == 0:
            return sort_score // 2
        return sort_score / 2
    return sort_score


def get_rankings(query: RankingQuery) -> RankingPage:
    """Return the paginated public ranking for *query*.

    Eligibility starts from ``publicly_listable()`` and additionally requires a
    current READY snapshot with the score data for the selected profile (both
    Challenge and Reward vectors for Unified).  Filtering and ordering happen
    database-side and before the page slice.
    """
    _validate_query(query)

    qs = (
        Game.objects.publicly_listable()
        .annotate(_score=_sort_score_expression(query.profile, query.dimension))
        .filter(_score__isnull=False)
    )

    # Dominant-category filter (before ordering/pagination).
    if query.dominant is not None:
        category_scores = _category_score_expressions(query.profile)
        qs = (
            qs.annotate(
                _cat_micro=category_scores[SkillCategory.MICRO],
                _cat_macro=category_scores[SkillCategory.MACRO],
                _cat_mystiko=category_scores[SkillCategory.MYSTIKO],
            )
            .annotate(_dominant=published_dominant_category())
            .filter(_dominant=query.dominant)
        )

    # Deterministic order: score (selected direction) → name ASC → id ASC.  Only
    # the score reverses for ascending; the name/id tie-breakers stay ascending.
    direction = "-" if query.direction == RankingDirection.DESC else ""
    qs = qs.order_by(f"{direction}_score", "name", "id")

    count = qs.count()
    total_pages = (count + query.page_size - 1) // query.page_size if count else 0

    offset = (query.page - 1) * query.page_size
    page_qs = qs[offset : offset + query.page_size]

    results = [
        RankingGame(
            slug=game.slug,
            name=game.name,
            hero_url=game.display_hero_url,
            score=_public_score(game._score, query.profile),
        )
        for game in page_qs
    ]

    return RankingPage(
        count=count,
        page=query.page,
        page_size=query.page_size,
        total_pages=total_pages,
        results=results,
    )
