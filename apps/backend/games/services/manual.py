"""
Manual Game service — SBGC-59.

Single entry point for creating and editing canonical manual (non-Steam)
Games.  Manual identity is owned here:

    source_type = manual
    external_id = NULL

The service never contacts Steam and never mutates Steam-owned fields.
"""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils.text import slugify

from games.models import Game, ListingStatus, SourceType
from games.services.source_policy import can_manual_edit
from games.types import ContentType


class _Unset:
    """Sentinel for optional update fields where ``None`` means clear."""


_UNSET = _Unset()


class ManualGameError(Exception):
    """Domain error for invalid manual Game operations."""


def create_manual_game(
    *,
    name: str,
    slug: str | None = None,
    content_type: str = ContentType.GAME,
    listing_status: str = ListingStatus.DRAFT,
    release_date: date | None = None,
    developer: str = "",
    description: str = "",
    manual_image_url: str = "",
    manual_website_url: str = "",
) -> Game:
    """Create a canonical manual Game.

    The service forces ``source_type=manual`` and ``external_id=None``.
    Steam-owned fields (``steam_image_url`` / ``last_steam_refresh_at``)
    are never populated here.
    """
    if not isinstance(name, str):
        raise TypeError(f"name must be a string, got {type(name).__name__}.")
    if name.strip() == "":
        raise ValueError("name must not be blank.")

    resolved_slug = _resolve_slug(name, slug)

    game = Game(
        source_type=SourceType.MANUAL,
        external_id=None,
        name=name,
        slug=resolved_slug,
        content_type=content_type,
        listing_status=listing_status,
        release_date=release_date,
        developer=developer,
        description=description,
        manual_image_url=manual_image_url,
        manual_website_url=manual_website_url,
    )

    game.full_clean()
    with transaction.atomic():
        game.save()
    return game


def update_manual_game(
    game: Game,
    *,
    name: str | None = None,
    slug: str | None = None,
    content_type: str | None = None,
    listing_status: str | None = None,
    release_date: date | None | _Unset = _UNSET,
    developer: str | None = None,
    description: str | None = None,
    manual_image_url: str | None = None,
    manual_website_url: str | None = None,
) -> Game:
    """Edit a canonical manual Game.

    Only manual Games may be edited.  ``None`` means "keep the existing
    value" for most fields (including ``description`` and the ``manual_*``
    asset fields, whose valid empty value can be passed explicitly).

    ``release_date`` uses a distinct ``_UNSET`` sentinel as its default so
    callers can keep it (omit the argument), set a date (pass a ``date``), or
    clear it (pass ``None``).

    Steam-owned fields, source identity, and the editorial classification are
    never touched.
    """
    if not isinstance(game, Game):
        raise TypeError(f"game must be a Game instance, got {type(game).__name__}.")
    if game.pk is None:
        raise ManualGameError("game must be saved before updating.")
    if not can_manual_edit(game):
        raise ManualGameError(
            f"Only manual games can be edited (game {game.pk} is {game.source_type})."
        )

    changed = False

    if name is not None:
        _validate_name(name)
        game.name = name
        changed = True
    if slug is not None:
        _validate_slug(slug)
        game.slug = slug
        changed = True
    if content_type is not None:
        game.content_type = content_type
        changed = True
    if listing_status is not None:
        game.listing_status = listing_status
        changed = True
    if release_date is not _UNSET:
        game.release_date = release_date
        changed = True
    if developer is not None:
        game.developer = developer
        changed = True
    if description is not None:
        game.description = description
        changed = True
    if manual_image_url is not None:
        game.manual_image_url = manual_image_url
        changed = True
    if manual_website_url is not None:
        game.manual_website_url = manual_website_url
        changed = True

    if not changed:
        return game

    game.full_clean()
    with transaction.atomic():
        game.save()
    return game


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_slug(name: str, slug: str | None) -> str:
    """Return the explicit slug, or derive one from *name*."""
    if slug is not None:
        _validate_slug(slug)
        return slug
    derived = slugify(name)
    if not derived:
        raise ValueError(
            "Cannot derive a slug from the given name; provide an explicit slug."
        )
    return _truncate_slug(derived, 255)


def _truncate_slug(value: str, limit: int) -> str:
    return value[:limit].rstrip("-")


def _validate_name(name: str) -> None:
    if not isinstance(name, str):
        raise TypeError(f"name must be a string, got {type(name).__name__}.")
    if name.strip() == "":
        raise ValueError("name must not be blank.")


def _validate_slug(slug: str) -> None:
    if not isinstance(slug, str):
        raise TypeError(f"slug must be a string, got {type(slug).__name__}.")
    if slug.strip() == "":
        raise ValueError("slug must not be blank.")
