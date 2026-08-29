"""
Steam game import persistence, orchestration, and refresh — SBGC-54/56.

Layers:

- ``SteamGamePersistenceService`` — persists a prepared
  ``SteamGameImportCandidate`` as a canonical ``Game`` row.  No network
  and no transport imports — only the ORM-free DTO package, the pure
  image-URL validator, and the payload error taxonomy.
- ``SteamGameImportService`` — orchestrates SBGC-53's
  ``SteamImportFoundation`` (network) with the persistence layer.
- ``SteamGameRefreshService`` — refreshes an existing canonical Steam
  Game from Steam (SBGC-56): eligibility checks, network lookup outside
  any transaction, identity verification, then Steam-owned field
  updates via the shared mapping helper.

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
from django.utils import timezone
from django.utils.text import slugify

from games.models import Game, SourceType
from games.services.source_policy import can_steam_refresh
from games.services.steam.cdn import validate_steam_image_url
from games.services.steam.dto import (
    LookupStatus,
    SteamAppId,
    SteamGameImportCandidate,
)
from games.services.steam.import_foundation import SteamImportFoundation
from games.services.steam.library_assets import build_steam_library_asset_urls
from games.types import ContentType

# ---------------------------------------------------------------------------
# Shared Steam-owned field mapping (single owner)
# ---------------------------------------------------------------------------

#: Steam-owned fields refreshable from a candidate, in deterministic order.
_REFRESHABLE_FIELDS = (
    "name",
    "content_type",
    "steam_image_url",
    "library_hero_url",
    "library_capsule_url",
    "description",
    "developer",
    "release_date",
)


def _library_asset_urls(candidate: SteamGameImportCandidate) -> tuple[str, str]:
    """Return the derived Steam Library ``(hero, capsule)`` URLs.

    Only base Games receive Library artwork; non-game Steam content and Manual
    Games carry empty URLs (the fallback ladder treats empty as "absent").
    The URLs are a pure function of the validated App ID — never network access.
    """
    if candidate.content_type != ContentType.GAME:
        return "", ""
    return build_steam_library_asset_urls(candidate.app_id)


def _apply_overrideable_field(
    game: Game,
    field_name: str,
    upstream_value: object,
    overridden: bool,
) -> list[str]:
    """Apply one overridable Steam metadata field, honouring ownership.

    Returns ``[field_name]`` when the field changed, else ``[]``.
    - ``overridden`` → preserve the human value (no write).
    - ``upstream_value is None`` → absent/unusable → preserve current value.
    - otherwise → update when different.
    """
    if overridden or upstream_value is None:
        return []
    current = getattr(game, field_name)
    if current == upstream_value:
        return []
    setattr(game, field_name, upstream_value)
    return [field_name]


def _apply_steam_metadata(
    existing: Game,
    candidate: SteamGameImportCandidate,
) -> tuple[str, ...]:
    """Apply Steam-managed metadata from *candidate* onto *existing*.

    The single owner of the field-mapping table shared by import updates and
    metadata refresh.  Handles always-Steam-owned fields (name, images) and
    the overridable fields (content_type, description, developer, release
    date), each of which is preserved when its per-field override flag is set.

    Mutates *existing* in memory only — the caller decides whether to save.
    Returns the changed field names in the deterministic ``_REFRESHABLE_FIELDS``
    order.
    """
    image_url = validate_steam_image_url(candidate.header_image_url)
    hero_url, capsule_url = _library_asset_urls(candidate)

    changed: list[str] = []
    if existing.name != candidate.name:
        existing.name = candidate.name
        changed.append("name")
    # A human-set content_type override survives refresh (SBGC-96); otherwise
    # the upstream Steam type is authoritative.
    if (
        not existing.content_type_overridden
        and existing.content_type != candidate.content_type
    ):
        existing.content_type = candidate.content_type
        changed.append("content_type")
    if image_url is not None and existing.steam_image_url != image_url:
        existing.steam_image_url = image_url
        changed.append("steam_image_url")
    if existing.library_hero_url != hero_url:
        existing.library_hero_url = hero_url
        changed.append("library_hero_url")
    if existing.library_capsule_url != capsule_url:
        existing.library_capsule_url = capsule_url
        changed.append("library_capsule_url")

    changed.extend(
        _apply_overrideable_field(
            existing,
            "description",
            candidate.description,
            existing.description_overridden,
        )
    )
    changed.extend(
        _apply_overrideable_field(
            existing, "developer", candidate.developer, existing.developer_overridden
        )
    )
    changed.extend(
        _apply_overrideable_field(
            existing,
            "release_date",
            candidate.release_date,
            existing.release_date_overridden,
        )
    )

    return tuple(changed)


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
        """Update Steam-managed fields only.  Preserve everything else.

        Delegates to ``_apply_steam_metadata`` — the single owner
        of the field-mapping table shared with ``SteamGameRefreshService``.
        """
        changed = _apply_steam_metadata(existing, candidate)

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

        New Games start as ``draft`` — imports never publish.  The three
        editable fields (description, developer, release date) are populated
        from Steam on initial import; their override flags default to False
        (Steam-managed).  ``manual_image_url`` / ``manual_website_url`` are
        never populated from Steam.
        """
        slug = self._allocate_slug(candidate, app_id)
        hero_url, capsule_url = _library_asset_urls(candidate)

        game = Game(
            source_type=SourceType.STEAM,
            external_id=app_id.value,
            name=candidate.name,
            content_type=candidate.content_type,
            slug=slug,
            steam_image_url=self._normalised_image_url(candidate) or "",
            library_hero_url=hero_url,
            library_capsule_url=capsule_url,
            description=candidate.description or "",
            developer=candidate.developer or "",
            release_date=candidate.release_date,
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

        ``None`` means exactly one thing: the candidate carried no usable
        upstream image field (absent/null/blank).  Non-string values and
        nonblank malformed strings raise ``SteamMalformedPayloadError``
        — persistence never weakens the adapter's strict contract by
        reclassifying malformed metadata as absence.

        Never performs network access — structural validation only.
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


# ---------------------------------------------------------------------------
# Metadata refresh (SBGC-56)
# ---------------------------------------------------------------------------


class SteamRefreshError(Exception):
    """Domain error for invalid refresh targets or identity violations."""


class SteamGameRefreshStatus(StrEnum):
    """Outcome of refreshing one canonical Steam Game."""

    UPDATED = "updated"
    UNCHANGED = "unchanged"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SteamGameRefreshResult:
    """Result of refreshing one canonical Steam Game from Steam.

    Invariants:
    - ``UPDATED`` requires a non-empty ``changed_fields``.
    - ``UNCHANGED`` / ``UNAVAILABLE`` require empty ``changed_fields``.
    - ``changed_fields`` contains only source-owned field names.
    """

    status: SteamGameRefreshStatus
    game_id: int
    changed_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, SteamGameRefreshStatus):
            raise TypeError(
                "status must be a SteamGameRefreshStatus, "
                f"got {type(self.status).__name__}."
            )
        if isinstance(self.game_id, bool) or not isinstance(self.game_id, int):
            raise TypeError("game_id must be an integer.")
        if not isinstance(self.changed_fields, tuple) or any(
            not isinstance(field, str) for field in self.changed_fields
        ):
            raise TypeError("changed_fields must be a tuple of strings.")
        unknown = set(self.changed_fields) - set(_REFRESHABLE_FIELDS)
        if unknown:
            raise ValueError(
                "changed_fields must be Steam-owned fields only, "
                f"got {sorted(unknown)}."
            )
        if self.status == SteamGameRefreshStatus.UPDATED:
            if not self.changed_fields:
                raise ValueError("UPDATED results require non-empty changed_fields.")
        elif self.changed_fields:
            raise ValueError(
                f"{self.status.value} results require empty changed_fields."
            )


class SteamGameRefreshService:
    """Refresh one canonical Steam Game from Steam.

    - Eligibility: only ``source_type=steam`` Games; the stored
      ``external_id`` is the only accepted App ID (validated through
      ``SteamAppId``) — no replacement App IDs.
    - Network (``prepare_candidate``) runs strictly before any database
      transaction opens.
    - Identity invariant: the lookup and candidate must match
      ``game.external_id`` — mismatches raise with zero writes.
    - Steam-managed fields update through the shared ``_apply_steam_metadata``
      helper (single owner): name, content_type, images, plus the editable
      description/developer/release_date unless their override flag is set.
      Slug, listing status, ``manual_image_url``/``manual_website_url``,
      classifications, ``created_at``, and ``source_type``/``external_id``/``id``
      are never touched.
    - ``last_steam_refresh_at`` records successful verifications:
      ``UPDATED`` via the model save; ``UNCHANGED`` via a queryset
      update so ``updated_at`` stays untouched.
    """

    def __init__(
        self,
        foundation: SteamImportFoundation,
        persistence: SteamGamePersistenceService,
    ) -> None:
        self._foundation = foundation
        self._persistence = persistence

    def refresh(self, game: Game) -> SteamGameRefreshResult:
        """Refresh *game* from Steam and return a typed result.

        Raises:
            SteamRefreshError: Manual game, unsaved game, invalid stored
                App ID, identity mismatch, or missing canonical row.
            SteamMalformedPayloadError / SteamAdapterError / transport
                errors: propagated unchanged from the foundation.
        """
        if not isinstance(game, Game):
            raise TypeError(f"game must be a Game instance, got {type(game).__name__}.")
        if game.pk is None:
            raise SteamRefreshError("game must be saved before refreshing.")
        if not can_steam_refresh(game):
            raise SteamRefreshError(
                f"Only Steam-sourced games can refresh (game {game.pk} is "
                f"{game.source_type})."
            )

        # The stored external ID is the only accepted App ID.
        try:
            app_id = SteamAppId(game.external_id)
        except (TypeError, ValueError) as exc:
            raise SteamRefreshError(
                f"Stored Steam external ID {game.external_id!r} is invalid: {exc}"
            ) from exc

        # -- Network: strictly outside any database transaction ---------------
        lookup = self._foundation.prepare_candidate(app_id.value)

        if lookup.status == LookupStatus.UNAVAILABLE:
            # Preserve the Game completely — no writes at all.
            return SteamGameRefreshResult(
                status=SteamGameRefreshStatus.UNAVAILABLE,
                game_id=game.pk,
            )

        candidate = lookup.candidate
        if candidate is None:
            raise ValueError("FOUND lookup must include an import candidate.")

        # -- Identity invariant: zero writes on mismatch -----------------------
        if lookup.app_id != game.external_id:
            raise SteamRefreshError(
                f"Lookup returned App ID {lookup.app_id!r}, expected "
                f"{game.external_id!r}."
            )
        if candidate.app_id != game.external_id:
            raise SteamRefreshError(
                f"Candidate carries App ID {candidate.app_id!r}, expected "
                f"{game.external_id!r}."
            )

        # Malformed candidate metadata raises before any transaction/write.
        validate_steam_image_url(candidate.header_image_url)

        # -- DB work: the only transaction in this path -------------------------
        with transaction.atomic():
            existing = self._persistence._find_existing(app_id.value)
            if existing is None:
                raise SteamRefreshError(
                    f"Canonical Steam Game row for App ID {app_id.value} no "
                    "longer exists."
                )

            changed = _apply_steam_metadata(existing, candidate)
            now = timezone.now()

            if changed:
                existing.last_steam_refresh_at = now
                existing.full_clean()
                existing.save()
                return SteamGameRefreshResult(
                    status=SteamGameRefreshStatus.UPDATED,
                    game_id=existing.pk,
                    changed_fields=changed,
                )

            # UNCHANGED: record the successful verification without a model
            # save so updated_at remains untouched.
            Game.objects.filter(pk=existing.pk).update(last_steam_refresh_at=now)
            return SteamGameRefreshResult(
                status=SteamGameRefreshStatus.UNCHANGED,
                game_id=existing.pk,
            )


__all__ = [
    "SteamGameImportResult",
    "SteamGameImportService",
    "SteamGameImportStatus",
    "SteamGamePersistenceService",
    "SteamGameRefreshResult",
    "SteamGameRefreshService",
    "SteamGameRefreshStatus",
    "SteamRefreshError",
    "build_steam_game_slug",
]
