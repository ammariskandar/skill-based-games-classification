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

from django.db.models import Exists, IntegerField, OuterRef, Subquery

from classifications.calculations.results import READY
from classifications.models import ClassificationSnapshot

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
    ``[micro, macro, mystiko]``).  Returns ``NULL`` when no current READY
    snapshot exists or the vector element is missing.
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
        .values(f"{field}__{index}")[:1],
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
