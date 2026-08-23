"""
Game catalogue query service — SBGC-76.

Owns the deterministic public catalogue read: canonical public eligibility,
search, source/classification filters, ordering, pagination, and a bounded
current-snapshot prefetch so the route never does per-Game classification
lookups.  Reads persisted state only — never contacts Steam, never probes
images, never recalculates classification.
"""

from __future__ import annotations

from dataclasses import dataclass

from classifications.calculations.results import READY
from classifications.models import ClassificationSnapshot
from django.db.models import Exists, OuterRef, Prefetch

from games.models import Game, SourceType


@dataclass(frozen=True)
class CatalogueQuery:
    """Parsed catalogue filter/pagination inputs."""

    q: str | None = None
    source: SourceType | None = None
    classified: bool | None = None
    page: int = 1
    page_size: int = 24


@dataclass(frozen=True)
class CatalogueClassification:
    """Narrow public classification summary (SBGC-76)."""

    status: str
    challenge: list[int] | None = None
    reward: list[int] | None = None
    confidence_level: float | None = None
    confidence_label: str | None = None
    is_stale: bool = False


@dataclass(frozen=True)
class CatalogueGame:
    """One public catalogue item with effective artwork and classification."""

    slug: str
    name: str
    source: str
    image_url: str
    library_capsule_url: str | None
    classification: CatalogueClassification | None


@dataclass(frozen=True)
class CataloguePage:
    """Paginated catalogue result."""

    count: int
    page: int
    page_size: int
    total_pages: int
    games: list[CatalogueGame]


def get_game_catalogue(query: CatalogueQuery) -> CataloguePage:
    """Return the paginated public catalogue for *query*.

    Filters are AND-composed on top of ``publicly_listable()``; ordering is
    deterministic (`name ASC, id ASC`); classification availability is driven
    by the current published snapshot (status READY), never the editorial
    submission table.
    """
    qs = Game.objects.publicly_listable()

    if query.q:
        qs = qs.filter(name__icontains=query.q)

    if query.source is SourceType.STEAM:
        qs = qs.steam()
    elif query.source is SourceType.MANUAL:
        qs = qs.manual()

    if query.classified is not None:
        has_ready = Exists(
            ClassificationSnapshot.objects.filter(
                game=OuterRef("pk"),
                is_current=True,
                status=READY,
            )
        )
        qs = qs.filter(has_ready) if query.classified else qs.exclude(has_ready)

    qs = qs.order_by("name", "id")

    count = qs.count()
    total_pages = (count + query.page_size - 1) // query.page_size if count else 0

    offset = (query.page - 1) * query.page_size
    page_qs = qs[offset : offset + query.page_size].prefetch_related(
        Prefetch(
            "classification_snapshots",
            queryset=ClassificationSnapshot.objects.filter(is_current=True),
            to_attr="current_snapshot",
        )
    )

    games = [_to_catalogue_game(game) for game in page_qs]

    return CataloguePage(
        count=count,
        page=query.page,
        page_size=query.page_size,
        total_pages=total_pages,
        games=games,
    )


def _to_catalogue_game(game: Game) -> CatalogueGame:
    current = getattr(game, "current_snapshot", None) or []
    snapshot = current[0] if current else None
    return CatalogueGame(
        slug=game.slug,
        name=game.name,
        source=game.source_type,
        image_url=game.display_image_url,
        library_capsule_url=game.display_capsule_url or None,
        classification=_to_catalogue_classification(snapshot),
    )


def _to_catalogue_classification(snapshot) -> CatalogueClassification | None:
    if snapshot is None or snapshot.status != READY:
        return None
    return CatalogueClassification(
        status=snapshot.status,
        challenge=snapshot.unified_integer_challenge,
        reward=snapshot.unified_integer_reward,
        confidence_level=(
            float(snapshot.confidence_final)
            if snapshot.confidence_final is not None
            else None
        ),
        confidence_label=snapshot.confidence_label or None,
        is_stale=snapshot.is_stale,
    )
