"""
Editorial role vocabulary and fixed base weights — SBGC-63.

These are the canonical role definitions and constants.  No scoring or
weighted arithmetic lives here — only identity and the fixed product
weights used for future statistical provenance.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models


class EditorialRole(models.TextChoices):
    SUPERUSER = "superuser", "Superuser"
    MODERATOR = "moderator", "Moderator"
    COMMUNITY_LEADER = "community_leader", "Community Leader"
    COMMUNITY = "community", "Community"


# Fixed product constants — not user-editable values.
BASE_WEIGHTS: dict[str, Decimal] = {
    EditorialRole.SUPERUSER: Decimal("1.00"),
    EditorialRole.MODERATOR: Decimal("0.95"),
    EditorialRole.COMMUNITY_LEADER: Decimal("0.65"),
    EditorialRole.COMMUNITY: Decimal("0.20"),
}


__all__ = ["BASE_WEIGHTS", "EditorialRole"]
