"""
Canonical Game domain types — SBGC-53.

ORM-free vocabulary shared by Django models, Steam adapters, query
helpers, seed data, and tests.  No Django ORM import, no network,
no database.
"""

from __future__ import annotations

from enum import StrEnum


class ContentType(StrEnum):
    """Normalized application content classification.

    Six canonical values.  Default is GAME.
    """

    GAME = "game"
    DLC = "dlc"
    DEMO = "demo"
    SOFTWARE = "software"
    SOUNDTRACK = "soundtrack"
    UNKNOWN = "unknown"


# Django model choices derived from the canonical enum.
CONTENT_TYPE_CHOICES = [
    (ContentType.GAME, "Game"),
    (ContentType.DLC, "Downloadable content"),
    (ContentType.DEMO, "Demo"),
    (ContentType.SOFTWARE, "Software"),
    (ContentType.SOUNDTRACK, "Soundtrack"),
    (ContentType.UNKNOWN, "Unknown"),
]
