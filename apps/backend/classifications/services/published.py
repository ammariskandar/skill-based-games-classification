"""
Published current-snapshot read helpers — SBGC-81.

Read-only query building blocks for the published current
``ClassificationSnapshot`` (``is_current=True`` and ``status=READY``).  Owns the
canonical score read so the catalogue (SBGC-76/79) and rankings (SBGC-81) share
one implementation instead of each reconstructing JSON-index subqueries.

Reads persisted state only — never contacts Steam and never recalculates
classification.
"""

from __future__ import annotations

from django.db.models import (
    Case,
    CharField,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast

from classifications.calculations.results import READY
from classifications.models import ClassificationSnapshot
from classifications.skills import SkillCategory

# Canonical array order ``[micro, macro, mystiko]`` (PROFILE_DISPLAY_ORDER).
# Index lookup is pinned here rather than inferred from display order.
SKILL_INDEX: dict[str, int] = {
    "micro": 0,
    "macro": 1,
    "mystiko": 2,
}

# Profile → JSON field on ClassificationSnapshot.
PROFILE_FIELD: dict[str, str] = {
    "challenge": "unified_integer_challenge",
    "reward": "unified_integer_reward",
}


def published_score(profile: str, category: str) -> Subquery:
    """Subquery for one published READY unified integer score.

    Extracts a single array element from the current READY snapshot's
    ``unified_integer_{profile}`` JSON list (canonical order
    ``[micro, macro, mystiko]``) and casts it to an integer.  Returns ``NULL``
    when no current READY snapshot exists or the vector element is missing.

    The cast is load-bearing rather than cosmetic.  The vector lives in a
    ``JSONField``, so ``->`` yields ``jsonb`` (on SQLite, an untyped JSON value),
    and Unified rankings *add two of these expressions together* — PostgreSQL
    has no ``jsonb + jsonb`` operator, so a bare ``->`` extraction raises
    ``ProgrammingError`` and 500s the endpoint.  ``->>`` returns text and the
    explicit cast turns it into a real integer, which also makes ordering and
    ``_cat_*`` dominance comparisons numeric on every backend.
    """
    field = PROFILE_FIELD[profile]
    index = SKILL_INDEX[category]
    return Subquery(
        ClassificationSnapshot.objects.filter(
            game=OuterRef("pk"),
            is_current=True,
            status=READY,
        )
        .order_by()
        .annotate(_value=Cast(KeyTextTransform(str(index), field), IntegerField()))
        .values("_value")[:1],
        output_field=IntegerField(),
    )


def published_snapshot_exists() -> Exists:
    """Exists subquery: does the Game have a current READY snapshot?"""
    return Exists(
        ClassificationSnapshot.objects.filter(
            game=OuterRef("pk"),
            is_current=True,
            status=READY,
        )
    )


def published_dominant_category() -> Case:
    """Strict-dominance Case/When over the ``_cat_micro``/``_cat_macro``/
    ``_cat_mystiko`` annotations (produced by ``published_score``).

    A category is dominant iff its score is strictly greater than both other
    categories; any top-score tie (or a missing score, which annotates NULL)
    yields ``None``.  Callers must annotate the ``_cat_*`` aliases first.
    """
    return Case(
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
    )
