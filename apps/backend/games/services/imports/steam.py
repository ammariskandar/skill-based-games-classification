"""
Steam game import persistence and orchestration — SBGC-54.

Layers:

- ``SteamGamePersistenceService`` — persists a prepared
  ``SteamGameImportCandidate`` as a canonical ``Game`` row.  No network
  and no transport imports — only the ORM-free DTO package, the pure
  image-URL validator, and the payload error taxonomy.
- ``SteamGameImportService`` — orchestrates SBGC-53's
  ``SteamImportFoundation`` (network) with the persistence layer.

Critical boundary: candidate preparation (network) happens *before* any
database transaction opens.  The persistence service owns the only
transaction in the import path.

Identity: an existing Steam Game is matched exclusively through
``source_type=steam AND external_id=app_id``.  Name and slug are never
identity keys, and manual Games are never merged or converted.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from django.db import IntegrityError, transaction
from django.utils.text import slugify

from games.models import Game, SourceType
from games.services.steam.cdn import validate_steam_image_url
from games.services.steam.dto import (
    LookupStatus,
    SteamAppId,
    SteamGameImportCandidate,
)
from games.services.steam.import_foundation import SteamImportFoundation

# ---------------------------------------------------------------------------
# Import outcomes
# ---------------------------------------------------------------------------


class SteamGameImportStatus(StrEnum):
    """Outcome of a single Steam game import."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SteamGameImportResult:
    """Result of importing one Steam app into canonical storage.

    Invariants:
    - ``CREATED`` / ``UPDATED`` / ``UNCHANGED`` require a ``game_id``.
    - ``UNAVAILABLE`` requires ``game_id=None``.
    """

    status: SteamGameImportStatus
    app_id: SteamAppId
    game_id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, SteamGameImportStatus):
            raise TypeError(
                "status must be a SteamGameImportStatus, "
                f"got {type(self.status).__name__}."
            )
        if not isinstance(self.app_id, SteamAppId):
            raise TypeError(
                f"app_id must be a SteamAppId, got {type(self.app_id).__name__}."
            )
        if self.status == SteamGameImportStatus.UNAVAILABLE:
            if self.game_id is not None:
                raise ValueError("UNAVAILABLE results must not carry a game_id.")
            return
        if self.game_id is None:
            raise ValueError(f"{self.status.value} results require a game_id.")
        if isinstance(self.game_id, bool) or not isinstance(self.game_id, int):
            raise TypeError("game_id must be an integer.")


# ---------------------------------------------------------------------------
# Deterministic slug allocation
# ---------------------------------------------------------------------------


def _truncate_slug(base: str, limit: int) -> str:
    """Truncate *base* to *limit* chars without a trailing hyphen."""
    return base[:limit].rstrip("-")


def build_steam_game_slug(
    name: str,
    app_id: str,
    *,
    is_occupied: Callable[[str], bool] | None = None,
    max_length: int = 255,
) -> str:
    """Return a deterministic slug for a NEW Steam Game.

    Never used for existing Games — re-imports preserve the stored slug.

    Allocation order:

    1. ``slugify(name)`` — preferred when free.
    2. ``slugify(name)-steam-<app_id>`` — when the preferred slug is
       occupied by another Game.  The app-ID suffix is never truncated.
    3. ``steam-<app_id>`` — fallback for blank slugified names
       (e.g. Unicode-only names) or when both previous candidates are
       occupied.

    All candidates are truncated to ``max_length``.  If every candidate
    is occupied a ``ValueError`` is raised — the importer must not
    allocate random suffixes or modify unrelated Games.
    """
    if not isinstance(name, str):
        raise TypeError(f"name must be a string, got {type(name).__name__}.")
    if not isinstance(app_id, str):
        raise TypeError(f"app_id must be a string, got {type(app_id).__name__}.")
    if isinstance(max_length, bool) or not isinstance(max_length, int):
        raise TypeError("max_length must be an integer.")
    if max_length < 1:
        raise ValueError("max_length must be ≥ 1.")
    if not isinstance(is_occupied, Callable) and is_occupied is not None:
        raise TypeError("is_occupied must be callable or None.")

    app_id_clean = app_id.strip()
    if not app_id_clean or not app_id_clean.isdigit():
        raise ValueError(f"app_id must be a decimal digit string, got {app_id!r}.")
    if int(app_id_clean) == 0:
        raise ValueError("app_id must not be zero.")

    occupied: Callable[[str], bool] = (
        is_occupied if is_occupied is not None else lambda _slug: False
    )

    base = slugify(name).strip("-")
    suffix = f"-steam-{app_id_clean}"
    fallback = f"steam-{app_id_clean}"

    if not base:
        if occupied(fallback):
            raise ValueError(
                f"Cannot allocate deterministic slug: {fallback!r} is occupied."
            )
        return fallback

    preferred = _truncate_slug(base, max_length)
    if not occupied(preferred):
        return preferred

    if len(suffix) >= max_length:
        if occupied(fallback):
            raise ValueError(
                f"Cannot allocate deterministic slug: {fallback!r} is occupied."
            )
        return fallback

    suffixed = _truncate_slug(base, max_length - len(suffix)) + suffix
    if not occupied(suffixed):
        return suffixed

    if not occupied(fallback):
        return fallback

    raise ValueError(
        f"Cannot allocate a deterministic slug for Steam app {app_id_clean}: "
        "preferred, suffixed, and fallback slugs are all occupied."
    )


# ---------------------------------------------------------------------------
# Persistence service (no network)
# ---------------------------------------------------------------------------


class SteamGamePersistenceService:
    """Persist ``SteamGameImportCandidate`` values as canonical ``Game`` rows.

    No network access — this layer never imports the Steam transport
    (``SteamClient``) or any HTTP machinery.  Image URLs are validated
    structurally by the pure ``validate_steam_image_url`` helper; the
    URL is never fetched, HEADed, or resolved.
    """

    def persist(self, candidate: SteamGameImportCandidate) -> SteamGameImportResult:
        """Create or refresh the canonical Game for *candidate*.

        Raises the candidate's field errors (``ValueError``/``TypeError``
        from ``SteamAppId``, ``ValidationError`` from model validation)
        and unexpected ``IntegrityError``s unchanged.
        """
        app_id = SteamAppId(candidate.app_id)

        with transaction.atomic():
            existing = self._find_existing(app_id.value)
            if existing is not None:
                return self._refresh_existing(existing, candidate, app_id)
            return self._create_new(candidate, app_id)

    # -- identity ---------------------------------------------------------------

    def _find_existing(self, app_id: str) -> Game | None:
        """Find the canonical Steam Game by (steam, app_id) — nothing else."""
        return (
            Game.objects.filter(
                source_type=SourceType.STEAM,
                external_id=app_id,
            ).first()
            or None
        )

    # -- refresh path -----------------------------------------------------------

    def _refresh_existing(
        self,
        existing: Game,
        candidate: SteamGameImportCandidate,
        app_id: SteamAppId,
    ) -> SteamGameImportResult:
        """Update source-owned fields only.  Preserve everything else.

        Missing-image semantics (SBGC-55, reused by SBGC-56): a valid
        HTTPS URL updates ``steam_image_url``; ``None``/blank/invalid
        upstream values preserve the existing stored URL — upstream
        absence is ambiguous (no image vs. malformed payload) and never
        clears editorial state.
        """
        changed = False

        if existing.name != candidate.name:
            existing.name = candidate.name
            changed = True
        if existing.content_type != candidate.content_type:
            existing.content_type = candidate.content_type
            changed = True

        image_url = self._normalised_image_url(candidate)
        if image_url is not None and existing.steam_image_url != image_url:
            existing.steam_image_url = image_url
            changed = True

        if not changed:
            return SteamGameImportResult(
                status=SteamGameImportStatus.UNCHANGED,
                app_id=app_id,
                game_id=existing.pk,
            )

        existing.full_clean()
        existing.save()
        return SteamGameImportResult(
            status=SteamGameImportStatus.UPDATED,
            app_id=app_id,
            game_id=existing.pk,
        )

    # -- create path --------------------------------------------------------------

    def _create_new(
        self,
        candidate: SteamGameImportCandidate,
        app_id: SteamAppId,
    ) -> SteamGameImportResult:
        """Create a canonical Steam Game for *candidate*.

        New Games start as ``draft`` — imports never publish.  Manual
        metadata fields are not populated from Steam data.
        """
        slug = self._allocate_slug(candidate, app_id)

        game = Game(
            source_type=SourceType.STEAM,
            external_id=app_id.value,
            name=candidate.name,
            content_type=candidate.content_type,
            slug=slug,
            steam_image_url=self._normalised_image_url(candidate) or "",
        )
        # Field and model validation only — deliberately NOT
        # ``validate_constraints()``/``validate_unique()``.  The database
        # unique constraint is the concurrency authority: a pre-check
        # would race with a parallel import.
        game.clean_fields()
        game.clean()

        try:
            with transaction.atomic():
                game.save()
        except IntegrityError:
            # Identity race: a concurrent import of the same App ID won.
            # Adopt the winner's row — one canonical Game survives.
            raced = self._find_existing(app_id.value)
            if raced is not None:
                return self._refresh_existing(raced, candidate, app_id)

            # Slug race: an unrelated Game (e.g. a different Steam App ID
            # with the same name) acquired our allocated slug between
            # allocation and INSERT.  Recompute deterministically — the
            # fresh allocation falls through to the suffixed/fallback
            # candidate — and retry the INSERT once.
            if not Game.objects.filter(slug=slug).exists():
                raise
            game.slug = self._allocate_slug(candidate, app_id)
            try:
                with transaction.atomic():
                    game.save()
            except IntegrityError:
                raced = self._find_existing(app_id.value)
                if raced is not None:
                    return self._refresh_existing(raced, candidate, app_id)
                raise

        return SteamGameImportResult(
            status=SteamGameImportStatus.CREATED,
            app_id=app_id,
            game_id=game.pk,
        )

    def _allocate_slug(
        self,
        candidate: SteamGameImportCandidate,
        app_id: SteamAppId,
    ) -> str:
        """Allocate a deterministic slug for *candidate*, checking the DB."""
        return build_steam_game_slug(
            candidate.name,
            app_id.value,
            is_occupied=lambda value: Game.objects.filter(slug=value).exists(),
        )

    def _normalised_image_url(
        self,
        candidate: SteamGameImportCandidate,
    ) -> str | None:
        """Return the canonical validated image URL for *candidate*.

        ``None`` means "no usable upstream image URL".  Non-string values
        raise ``SteamMalformedPayloadError``.  Never performs network
        access — the URL is validated structurally only.
        """
        return validate_steam_image_url(candidate.header_image_url)


# ---------------------------------------------------------------------------
# Import orchestration
# ---------------------------------------------------------------------------


class SteamGameImportService:
    """Orchestrate Steam lookup and canonical persistence.

    Network work (``SteamImportFoundation.prepare_candidate``) runs
    before any transaction opens.  The persistence service owns the only
    database transaction in this path.
    """

    def __init__(
        self,
        foundation: SteamImportFoundation,
        persistence: SteamGamePersistenceService,
    ) -> None:
        self._foundation = foundation
        self._persistence = persistence

    def import_app(self, app_id: str) -> SteamGameImportResult:
        """Import one Steam App ID into canonical storage.

        Transport and malformed-payload exceptions from the foundation
        propagate unchanged — nothing is written when preparation fails.
        """
        lookup = self._foundation.prepare_candidate(app_id)

        if lookup.status == LookupStatus.UNAVAILABLE:
            return SteamGameImportResult(
                status=SteamGameImportStatus.UNAVAILABLE,
                app_id=SteamAppId(lookup.app_id),
            )

        candidate = lookup.candidate
        if candidate is None:
            raise ValueError("FOUND lookup must include an import candidate.")

        return self._persistence.persist(candidate)


__all__ = [
    "SteamGameImportResult",
    "SteamGameImportService",
    "SteamGameImportStatus",
    "SteamGamePersistenceService",
    "build_steam_game_slug",
]
