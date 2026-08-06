"""
Deterministic development seed data — SBGC-50.

Sample Games, classifications, and a seed editor for local development.
Seeded records use stable identities (Steam: source_type+external_id,
Manual: slug).  Idempotent — safe to re-run.
"""

from __future__ import annotations

import dataclasses

from classifications.services.editorial import (
    ScoreDistribution,
    set_editorial_classification,
)
from django.contrib.auth.models import User

from games.models import ContentType, Game, ListingStatus, SourceType

# ---------------------------------------------------------------------------
# Seed editor
# ---------------------------------------------------------------------------

_SEED_USERNAME = "development-editor"
_SEED_EMAIL = "development-editor@example.invalid"


def get_or_create_seed_editor() -> User:
    """Return the deterministic seed editor, creating or updating as needed.

    The editor is a plain user with an unusable password — not staff,
    not superuser.  Re-running restores the canonical email.
    """
    user, _created = User.objects.update_or_create(
        username=_SEED_USERNAME,
        defaults={
            "email": _SEED_EMAIL,
            "is_staff": False,
            "is_superuser": False,
        },
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user


# ---------------------------------------------------------------------------
# Seed Game definitions
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SeedGame:
    slug: str
    name: str
    source_type: str
    external_id: str | None
    content_type: str
    listing_status: str
    manual_description: str = ""
    manual_image_url: str = ""
    manual_website_url: str = ""
    classify: bool = False
    # Classification scores (challenge, reward)
    challenge: tuple[int, int, int] | None = None
    reward: tuple[int, int, int] | None = None
    notes: str = ""


SEED_GAMES: list[SeedGame] = [
    # -- Steam games ----------------------------------------------------------
    SeedGame(
        slug="portal-2",
        name="Portal 2",
        source_type=SourceType.STEAM,
        external_id="620",
        content_type=ContentType.GAME,
        listing_status=ListingStatus.PUBLISHED,
        classify=True,
        challenge=(50, 20, 30),
        reward=(10, 30, 60),
        notes="Classic puzzle-platformer.",
    ),
    SeedGame(
        slug="hades",
        name="Hades",
        source_type=SourceType.STEAM,
        external_id="1145360",
        content_type=ContentType.GAME,
        listing_status=ListingStatus.PUBLISHED,
        classify=True,
        challenge=(60, 25, 15),
        reward=(20, 50, 30),
        notes="Roguelike action with rich narrative.",
    ),
    SeedGame(
        slug="half-life-2-demo",
        name="Half-Life 2 Demo",
        source_type=SourceType.STEAM,
        external_id="220",
        content_type=ContentType.DEMO,
        listing_status=ListingStatus.PUBLISHED,
    ),
    SeedGame(
        slug="sample-soundtrack",
        name="Sample Soundtrack",
        source_type=SourceType.STEAM,
        external_id="323190",
        content_type=ContentType.SOUNDTRACK,
        listing_status=ListingStatus.PUBLISHED,
    ),
    # -- Manual games ---------------------------------------------------------
    SeedGame(
        slug="chess",
        name="Chess",
        source_type=SourceType.MANUAL,
        external_id=None,
        content_type=ContentType.GAME,
        listing_status=ListingStatus.PUBLISHED,
        manual_description="The classic board game.",
        manual_website_url="https://example.invalid/chess",
        classify=True,
        challenge=(30, 50, 20),
        reward=(10, 10, 80),
        notes="Abstract strategy.  High Mystiko (opening knowledge).",
    ),
    SeedGame(
        slug="go",
        name="Go",
        source_type=SourceType.MANUAL,
        external_id=None,
        content_type=ContentType.GAME,
        listing_status=ListingStatus.PUBLISHED,
        manual_description="The ancient game of surrounding territory.",
        classify=True,
        challenge=(20, 70, 10),
        reward=(5, 80, 15),
        notes="Deep strategy.  Reward dominated by Mystiko (discovery).",
    ),
    SeedGame(
        slug="sample-productivity-tool",
        name="Sample Productivity Tool",
        source_type=SourceType.MANUAL,
        external_id=None,
        content_type=ContentType.SOFTWARE,
        listing_status=ListingStatus.PUBLISHED,
        manual_description="A non-game application example.",
        manual_website_url="https://example.invalid/tool",
    ),
    SeedGame(
        slug="unresolved-sample",
        name="Unresolved Sample",
        source_type=SourceType.MANUAL,
        external_id=None,
        content_type=ContentType.UNKNOWN,
        listing_status=ListingStatus.DRAFT,
    ),
    SeedGame(
        slug="tied-challenge-sample",
        name="Tied Challenge Sample",
        source_type=SourceType.MANUAL,
        external_id=None,
        content_type=ContentType.GAME,
        listing_status=ListingStatus.PUBLISHED,
        classify=True,
        challenge=(50, 50, 0),
        reward=(25, 25, 50),
        notes="Challenge Micro and Mystiko tie at 50.",
    ),
]


# ---------------------------------------------------------------------------
# Seed entry point
# ---------------------------------------------------------------------------


def seed_development_data() -> dict:
    """Create or reconcile deterministic development records.

    Returns a summary dict with counts of created/updated records.
    Never contacts Steam or any external service.

    Must be called inside ``transaction.atomic()``.
    """
    stats = {
        "games_created": 0,
        "games_updated": 0,
        "classifications_created": 0,
        "classifications_updated": 0,
    }

    editor = get_or_create_seed_editor()

    for sg in SEED_GAMES:
        stats = _seed_one_game(sg, editor, stats)

    return stats


def _seed_one_game(sg: SeedGame, editor: User, stats: dict) -> dict:
    """Create or update a single seeded Game and optional classification."""

    if sg.source_type == SourceType.STEAM:
        existing = Game.objects.filter(
            source_type=sg.source_type, external_id=sg.external_id
        ).first()
    else:
        existing = Game.objects.filter(slug=sg.slug).first()
        if existing is not None and existing.source_type != SourceType.MANUAL:
            from django.core.management import CommandError

            raise CommandError(
                f"Slug '{sg.slug}' is occupied by a {existing.source_type} record "
                f"— cannot seed a manual record with the same slug."
            )

    if existing is not None:
        created = False
        game = existing
    else:
        created = True
        game = Game(
            source_type=sg.source_type,
            external_id=sg.external_id,
        )

    # Apply canonical fields.
    game.name = sg.name
    game.slug = sg.slug
    game.content_type = sg.content_type
    game.listing_status = sg.listing_status
    game.manual_description = sg.manual_description
    game.manual_image_url = sg.manual_image_url
    game.manual_website_url = sg.manual_website_url
    game.save()

    if created:
        stats["games_created"] += 1
    else:
        stats["games_updated"] += 1

    # Optional editorial classification.
    if sg.classify and sg.challenge and sg.reward:
        _was_new = (
            not hasattr(game, "editorial_classification")
            or game.editorial_classification is None
        )
        set_editorial_classification(
            game=game,
            updated_by=editor,
            challenge=ScoreDistribution(*sg.challenge),
            reward=ScoreDistribution(*sg.reward),
            notes=sg.notes,
        )
        if _was_new:
            stats["classifications_created"] += 1
        else:
            stats["classifications_updated"] += 1

    return stats
