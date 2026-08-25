"""
Game catalogue query service — SBGC-76 / SBGC-79.

Owns the deterministic public catalogue read: canonical public eligibility,
search, source/classification/dominant filters, primary sorting, the
cover-last outer partition, pagination, and a bounded current-snapshot
prefetch so the route never does per-Game classification lookups.  Reads
persisted state only — never contacts Steam, never probes images, never
recalculates classification.

SBGC-79 additions:
* ``sort``  — primary order (name A–Z/Z–A, recently added, or a
  Challenge/Reward Micro/Mystiko/Macro score).
* ``profile`` — the explicit Challenge/Reward profile for score sorting and
  the dominant-category filter.
* ``dominant`` — dominant-category filter against the published current READY
  snapshot (strictly-highest wins; top-score ties have no dominant category).
* ``coverless_last`` — an outer partition (before pagination) that puts Games
  without an effective Capsule after Games with one, independent of the chosen
  primary sort.

Score ordering always reads the published current ``ClassificationSnapshot``
(``is_current=True`` and ``status=READY``) ``unified_integer_*`` arrays — the
canonical order is ``[micro, macro, mystiko]`` (see
``classifications.calculations.constants.PROFILE_DISPLAY_ORDER``).  It never
uses the editorial submission tables.
"""

from __future__ import annotations

from dataclasses import dataclass

from classifications.calculations.results import READY
from classifications.models import ClassificationSnapshot
from classifications.services.published import (
    published_score,
    published_snapshot_exists,
)
from classifications.skills import EditorialProfile, SkillCategory
from django.db import models
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    F,
    Prefetch,
    Q,
    Value,
    When,
)

from games.models import Game, SourceType


class CatalogueSort(models.TextChoices):
    """Primary catalogue sort identifiers."""

    NAME_ASC = "name_asc", "Name (A–Z)"
    NAME_DESC = "name_desc", "Name (Z–A)"
    RECENT = "recent", "Recently added"
    MICRO = "micro", "Micro"
    MYSTIKO = "mystiko", "Mystiko"
    MACRO = "macro", "Macro"


@dataclass(frozen=True)
class CatalogueQuery:
    """Parsed catalogue filter/sort/pagination inputs."""

    q: str | None = None
    source: SourceType | None = None
    classified: bool | None = None
    sort: str = CatalogueSort.NAME_ASC
    profile: str = EditorialProfile.CHALLENGE
    dominant: str | None = None
    coverless_last: bool = True
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


def _validate_query(query: CatalogueQuery) -> None:
    if query.sort not in CatalogueSort.values:
        raise ValueError(
            f"sort must be one of {set(CatalogueSort.values)}, got {query.sort!r}."
        )
    if query.profile not in EditorialProfile.values:
        raise ValueError(
            f"profile must be one of {set(EditorialProfile.values)}, "
            f"got {query.profile!r}."
        )
    if query.dominant is not None and query.dominant not in SkillCategory.values:
        raise ValueError(
            f"dominant must be one of {set(SkillCategory.values)} or None, "
            f"got {query.dominant!r}."
        )


def _has_capsule_expression() -> Case:
    """Boolean annotation: does the Game have an effective Capsule URL?

    Mirrors ``Game.display_capsule_url`` (SBGC-190): Steam uses the manual
    Capsule override when present, else the Library Capsule; Manual uses only
    the manual Capsule.  A general/header image is not a Capsule.
    """
    steam = Case(
        When(
            Q(manual_capsule_url="") & Q(library_capsule_url=""),
            then=Value(False),
        ),
        default=Value(True),
        output_field=BooleanField(),
    )
    manual = Case(
        When(Q(manual_capsule_url=""), then=Value(False)),
        default=Value(True),
        output_field=BooleanField(),
    )
    return Case(
        When(source_type=SourceType.STEAM, then=steam),
        When(source_type=SourceType.MANUAL, then=manual),
        default=Value(False),
        output_field=BooleanField(),
    )


def get_game_catalogue(query: CatalogueQuery) -> CataloguePage:
    """Return the paginated public catalogue for *query*.

    Filters are AND-composed on top of ``publicly_listable()``; ordering is
    deterministic; classification availability and score sorting are driven by
    the current published snapshot (status READY), never the editorial
    submission table.  The cover-last partition is applied before the
    count/page slice so it is globally correct across pages.
    """
    _validate_query(query)

    qs = Game.objects.publicly_listable()

    if query.q:
        qs = qs.filter(name__icontains=query.q)

    if query.source is SourceType.STEAM:
        qs = qs.steam()
    elif query.source is SourceType.MANUAL:
        qs = qs.manual()

    if query.classified is not None:
        has_ready = published_snapshot_exists()
        qs = qs.filter(has_ready) if query.classified else qs.exclude(has_ready)

    # Dominant-category filter (published current READY snapshot).  Strictly
    # highest score wins; top-score ties (or missing scores) yield no dominant
    # category and therefore match no filter.
    if query.dominant is not None:
        qs = (
            qs.annotate(
                _cat_micro=published_score(query.profile, SkillCategory.MICRO),
                _cat_macro=published_score(query.profile, SkillCategory.MACRO),
                _cat_mystiko=published_score(query.profile, SkillCategory.MYSTIKO),
            )
            .annotate(
                _dominant=Case(
                    When(
                        condition=Q(_cat_micro__gt=F("_cat_macro"))
                        & Q(_cat_micro__gt=F("_cat_mystiko")),
                        then=Value(SkillCategory.MICRO),
                    ),
                    When(
                        condition=Q(_cat_macro__gt=F("_cat_micro"))
                        & Q(_cat_macro__gt=F("_cat_mystiko")),
                        then=Value(SkillCategory.MACRO),
                    ),
                    When(
                        condition=Q(_cat_mystiko__gt=F("_cat_micro"))
                        & Q(_cat_mystiko__gt=F("_cat_macro")),
                        then=Value(SkillCategory.MYSTIKO),
                    ),
                    default=Value(None),
                    output_field=CharField(),
                ),
            )
            .filter(_dominant=query.dominant)
        )

    # Primary sort (with the skill-score annotation when a skill sort is chosen).
    if query.sort in (
        CatalogueSort.MICRO,
        CatalogueSort.MYSTIKO,
        CatalogueSort.MACRO,
    ):
        qs = qs.annotate(_score=published_score(query.profile, query.sort))
        primary_order = [F("_score").desc(nulls_last=True), "name", "id"]
    elif query.sort == CatalogueSort.NAME_DESC:
        primary_order = ["-name", "id"]
    elif query.sort == CatalogueSort.RECENT:
        primary_order = ["-created_at", "name", "id"]
    else:  # name_asc
        primary_order = ["name", "id"]

    # Cover-last outer partition, before pagination (SBGC-79 cross-page).
    qs = qs.annotate(_has_capsule=_has_capsule_expression())
    if query.coverless_last:
        qs = qs.order_by(F("_has_capsule").desc(nulls_last=True), *primary_order)
    else:
        qs = qs.order_by(*primary_order)

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
