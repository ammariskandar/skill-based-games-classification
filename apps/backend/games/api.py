"""
Games API router — SBGC-38 / SBGC-57.

Router ownership boundary for game-domain API operations.

SBGC-57 adds two authorized Steam mutation endpoints over the existing
import and refresh services:

    POST /api/v1/games/steam/import           import one Steam App ID
    POST /api/v1/games/{game_id}/steam/refresh  refresh one Steam Game

The HTTP layer stays thin: it validates the request schema, enforces
authorization, delegates to the existing service, and maps the typed
result (or domain/transport error) into an explicit response schema.
It owns none of Steam payload parsing, DTO construction, slug
allocation, persistence, transaction policy, image validation, or
refresh mapping.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from api.errors import STANDARD_ERROR_RESPONSES, ApiException
from api.schemas import ApiErrorResponse, ApiRequestSchema
from django.shortcuts import get_object_or_404
from ninja import Router, Schema, Status
from ninja.errors import AuthorizationError
from ninja.security import django_auth

from games.models import Game
from games.services.imports.steam import (
    SteamGameImportResult,
    SteamGameImportStatus,
    SteamGameRefreshResult,
    SteamRefreshError,
)
from games.services.steam.adapters import SteamAdapterError
from games.services.steam.errors import SteamError, SteamRateLimitedError

logger = logging.getLogger(__name__)

router = Router(tags=["Games"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class SteamImportRequest(ApiRequestSchema):
    """``POST /games/steam/import`` request body."""

    app_id: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class GameSummary(Schema):
    """Small reusable canonical Game summary exposed by mutation endpoints.

    Only persisted, application-owned fields are exposed.  Manual/editorial
    metadata and unpersisted Steam DTO metadata are deliberately omitted.
    """

    id: int
    source_type: str
    external_id: str | None
    name: str
    slug: str
    content_type: str
    listing_status: str
    steam_image_url: str
    last_steam_refresh_at: datetime | None


class SteamImportResponse(Schema):
    """Import outcome: a status plus the canonical Game (when present)."""

    status: str
    app_id: str
    game: GameSummary | None = None


class SteamRefreshResponse(Schema):
    """Refresh outcome: a status, the canonical Game, and changed fields."""

    status: str
    game: GameSummary
    changed_fields: list[str]


# ---------------------------------------------------------------------------
# Public game-detail schemas (SBGC-71)
# ---------------------------------------------------------------------------


class PublicGameDetail(Schema):
    """Normalized public Game identity and persisted metadata."""

    id: int
    slug: str
    name: str
    source: str
    external_id: str | None
    content_type: str
    description: str
    release_date: date | None
    developer: str
    image_url: str
    metadata_updated_at: datetime


class PublicClassificationProfile(Schema):
    """A three-component profile in canonical display order."""

    micro: int
    macro: int
    mystiko: int


class PublicFinalClassification(Schema):
    """The currently published Final Classification, when one exists."""

    status: str
    regime: str | None = None
    challenge: PublicClassificationProfile | None = None
    reward: PublicClassificationProfile | None = None
    confidence_level: float | None = None
    confidence_label: str | None = None
    submission_count: int | None = None
    calculation_version: str | None = None
    calculated_at: datetime | None = None
    is_stale: bool = False


class GameDetailResponse(Schema):
    """Public game-detail payload: Game plus current persisted classification."""

    game: PublicGameDetail
    classification: PublicFinalClassification | None = None


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def _require_staff(request) -> None:
    """Reject authenticated non-staff callers (403).

    Authentication (session + CSRF) is enforced by ``auth=django_auth``
    on each operation; this helper only enforces the staff authorization
    requirement.  Service code remains authorization-free — this check
    lives at the HTTP boundary.
    """
    if not request.user.is_staff:
        raise AuthorizationError()


# ---------------------------------------------------------------------------
# Composition roots
# ---------------------------------------------------------------------------


def _build_steam_import_service():
    """Composition root for the Steam import endpoint.

    Lazy imports keep the transport wiring out of the module import
    surface.  Tests patch this factory — no network in automated tests.
    """
    from config.steam import steam_client_config_from_settings

    from games.services.imports.steam import (
        SteamGameImportService,
        SteamGamePersistenceService,
    )
    from games.services.steam.adapters.app_details import SteamAppDetailsAdapter
    from games.services.steam.client import SteamClient
    from games.services.steam.import_foundation import SteamImportFoundation

    client = SteamClient(steam_client_config_from_settings())
    foundation = SteamImportFoundation(SteamAppDetailsAdapter(client))
    return SteamGameImportService(foundation, SteamGamePersistenceService())


def _build_steam_refresh_service():
    """Composition root for the Steam refresh endpoint (SBGC-56)."""
    from config.steam import steam_client_config_from_settings

    from games.services.imports.steam import (
        SteamGamePersistenceService,
        SteamGameRefreshService,
    )
    from games.services.steam.adapters.app_details import SteamAppDetailsAdapter
    from games.services.steam.client import SteamClient
    from games.services.steam.import_foundation import SteamImportFoundation

    client = SteamClient(steam_client_config_from_settings())
    foundation = SteamImportFoundation(SteamAppDetailsAdapter(client))
    return SteamGameRefreshService(foundation, SteamGamePersistenceService())


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def _map_steam_service_error(exc: Exception) -> ApiException:
    """Translate a Steam/refresh domain error into a safe ``ApiException``.

    Mapping branches (grouped where the public HTTP contract is the same):

    - invalid Steam App ID             → 400 BAD_REQUEST
    - ``SteamRefreshError`` (manual
      Game, identity violation, or
      missing canonical row)           → 400 BAD_REQUEST
    - ``SteamRateLimitedError``        → 429 RATE_LIMITED
    - all other Steam transport/data
      errors                           → 503 SERVICE_UNAVAILABLE

    Steam "unavailable" is a *domain outcome* (a result status), never an
    exception here — the service already converted ``success=false`` to
    ``UNAVAILABLE`` before this boundary.
    """
    if isinstance(exc, SteamAdapterError) and exc.code == "STEAM_INVALID_APP_ID":
        return ApiException(400, "BAD_REQUEST", "Invalid Steam App ID.")

    if isinstance(exc, SteamRefreshError):
        logger.warning("Steam refresh rejected: %s", exc)
        return ApiException(
            400,
            "BAD_REQUEST",
            "The requested game cannot be refreshed from Steam.",
        )

    if isinstance(exc, SteamRateLimitedError):
        logger.warning("Steam rate limited")
        return ApiException(429, "RATE_LIMITED", "Steam rate limit exceeded.")

    if isinstance(exc, (SteamError, SteamAdapterError)):
        logger.warning("Steam service failure: %s", type(exc).__name__)
        return ApiException(
            503,
            "SERVICE_UNAVAILABLE",
            "Steam service is unavailable.",
        )

    # Unreachable given the handlers' except tuples — propagate as unexpected.
    raise exc


# ---------------------------------------------------------------------------
# Response mapping
# ---------------------------------------------------------------------------


def _game_summary(game: Game) -> GameSummary:
    return GameSummary(
        id=game.pk,
        source_type=game.source_type,
        external_id=game.external_id,
        name=game.name,
        slug=game.slug,
        content_type=game.content_type,
        listing_status=game.listing_status,
        steam_image_url=game.steam_image_url,
        last_steam_refresh_at=game.last_steam_refresh_at,
    )


def _import_response(
    result: SteamGameImportResult,
) -> tuple[int, SteamImportResponse]:
    game: GameSummary | None = None
    if result.game_id is not None:
        game = _game_summary(Game.objects.get(pk=result.game_id))

    body = SteamImportResponse(
        status=result.status.value,
        app_id=str(result.app_id),
        game=game,
    )
    status_code = 201 if result.status == SteamGameImportStatus.CREATED else 200
    return status_code, body


def _refresh_response(result: SteamGameRefreshResult) -> SteamRefreshResponse:
    game = _game_summary(Game.objects.get(pk=result.game_id))
    return SteamRefreshResponse(
        status=result.status.value,
        game=game,
        changed_fields=list(result.changed_fields),
    )


# ---------------------------------------------------------------------------
# Public game-detail mapping (SBGC-71)
# ---------------------------------------------------------------------------


def _public_game_detail(game: Game) -> PublicGameDetail:
    return PublicGameDetail(
        id=game.pk,
        slug=game.slug,
        name=game.name,
        source=game.source_type,
        external_id=game.external_id,
        content_type=game.content_type,
        description=game.manual_description,
        release_date=game.release_date,
        developer=game.developer,
        image_url=game.display_image_url,
        metadata_updated_at=game.updated_at,
    )


def _classification_profile(values) -> PublicClassificationProfile | None:
    """Map the persisted integer profile list to named components.

    ``ClassificationSnapshot`` stores the unified integer profiles as a
    three-element list in canonical display order ``[micro, macro, mystiko]``
    (see ``Profile.components()``).  The mapping is positional but pinned by
    that frozen order; tests use asymmetric values to catch any drift.
    """
    if not values or len(values) != 3:
        return None
    micro, macro, mystiko = values
    return PublicClassificationProfile(micro=micro, macro=macro, mystiko=mystiko)


def _public_final_classification(published) -> PublicFinalClassification | None:
    """Map the canonical published read result to the public schema.

    ``published.status == "NO_SNAPSHOT"`` means no Final Classification exists
    at all; every other status (READY or a legitimate non-ready domain status)
    yields a classification object with only the persisted fields populated.
    """
    if published.status == "NO_SNAPSHOT":
        return None

    challenge = None
    reward = None
    unified = published.unified
    if unified is not None:
        challenge = _classification_profile(unified.get("challenge"))
        reward = _classification_profile(unified.get("reward"))

    versions = published.versions or {}
    return PublicFinalClassification(
        status=published.status,
        regime=published.regime,
        challenge=challenge,
        reward=reward,
        confidence_level=published.confidence,
        confidence_label=published.confidence_label,
        submission_count=published.validated_submission_count,
        calculation_version=versions.get("master"),
        calculated_at=published.calculated_at,
        is_stale=published.is_stale,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/steam/import",
    auth=django_auth,
    response={
        200: SteamImportResponse,
        201: SteamImportResponse,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="steam_import",
    summary="Import a Steam game",
    description=(
        "Import (or re-import) one Steam App ID into canonical storage. "
        "Returns CREATED, UPDATED, UNCHANGED, or UNAVAILABLE with the "
        "canonical Game summary when a Game exists."
    ),
    url_name="steam-import",
)
def steam_import(request, payload: SteamImportRequest):
    _require_staff(request)
    service = _build_steam_import_service()
    try:
        result = service.import_app(payload.app_id)
    except (SteamAdapterError, SteamError, SteamRefreshError) as exc:
        raise _map_steam_service_error(exc) from exc

    status_code, body = _import_response(result)
    return Status(status_code, body)


@router.post(
    "/{game_id}/steam/refresh",
    auth=django_auth,
    response={
        200: SteamRefreshResponse,
        **STANDARD_ERROR_RESPONSES,
        422: ApiErrorResponse,
    },
    operation_id="steam_refresh",
    summary="Refresh a Steam game",
    description=(
        "Refresh one canonical Steam Game from Steam metadata.  The Game is "
        "identified by its internal ID; the persisted Steam identity is the "
        "only App ID used.  Returns UPDATED, UNCHANGED, or UNAVAILABLE."
    ),
    url_name="steam-refresh",
)
def steam_refresh(request, game_id: int):
    _require_staff(request)
    game = get_object_or_404(Game, pk=game_id)
    service = _build_steam_refresh_service()
    try:
        result = service.refresh(game)
    except (SteamAdapterError, SteamError, SteamRefreshError) as exc:
        raise _map_steam_service_error(exc) from exc

    return _refresh_response(result)


@router.get(
    "/{slug}",
    response={200: GameDetailResponse, **STANDARD_ERROR_RESPONSES},
    operation_id="game_detail",
    summary="Get a public game detail",
    description=(
        "Return the normalized public identity and persisted metadata for one "
        "publicly-listed base Game, together with its currently persisted "
        "Final Classification (if any).  Reads persisted state only — never "
        "contacts Steam and never recalculates classification."
    ),
    url_name="game-detail",
)
def game_detail(request, slug: str):
    game = Game.objects.publicly_listable().filter(slug=slug).first()
    if game is None:
        raise ApiException(404, "GAME_NOT_FOUND", "Game not found.")

    # Lazy import keeps the classification engine out of the games API module
    # import surface; this is a read-only boundary, not a calculation path.
    from classifications.services.calculations import get_published_classification

    published = get_published_classification(game)
    return GameDetailResponse(
        game=_public_game_detail(game),
        classification=_public_final_classification(published),
    )
