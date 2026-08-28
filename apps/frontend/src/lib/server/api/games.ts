/**
 * Game-detail API boundary — SBGC-72.
 *
 * Server-side only: fetches the SBGC-71 public game-detail DTO from Django.
 * Distinguishes a game-not-found (Django 404) from backend/service failures
 * so the route can render a real 404 versus a real error page.
 *
 * The DTO response shapes are owned by `../../types/api` (SBGC-89); this module
 * keeps legacy aliases so existing import sites are unchanged while the shared
 * contract remains the single source of truth.
 */

import { getJSON } from "./client";
import type { ApiFailure } from "./types";
import type {
  GameCatalogueClassificationDto,
  GameCatalogueItemDto,
  GameCatalogueQuery,
  GameCatalogueResponseDto,
  GameDetailResponseDto,
  GameSearchIndexItemDto,
  GameSearchIndexResponseDto,
  HomepageCarouselCardDto,
  HomepageCarouselResponseDto,
  PublicGameDetailDto,
  PublishedClassificationDto,
  RankingItemDto,
  RankingQuery,
  RankingResponseDto,
  SkillDimensionsDto,
} from "../../../types/api";

/* ── Legacy aliases (SBGC-89) ───────────────────────────────────────────── */

export type ClassificationProfile = SkillDimensionsDto;
export type GameFinalClassification = PublishedClassificationDto;
export type GameDetailGame = PublicGameDetailDto;
export type GameDetailResponse = GameDetailResponseDto;
export type HomepageCarouselCard = HomepageCarouselCardDto;
export type HomepageCarouselResponse = HomepageCarouselResponseDto;
export type GameCatalogueClassification = GameCatalogueClassificationDto;
export type GameCatalogueItem = GameCatalogueItemDto;
export type GameCatalogueResponse = GameCatalogueResponseDto;
export type GameSearchIndexItem = GameSearchIndexItemDto;
export type GameSearchIndexResponse = GameSearchIndexResponseDto;
export type RankingItem = RankingItemDto;
export type RankingResponse = RankingResponseDto;

export type { GameCatalogueQuery, RankingQuery };

export type {
  CatalogueDominant,
  CatalogueProfile,
  CatalogueSort,
  ClassificationRegime,
  GameSource,
  RankingDimension,
  RankingDirection,
  RankingProfile,
} from "../../../types/api";

/* ── Domain errors ──────────────────────────────────────────────────────── */

/** The slug does not resolve to a publicly-listed Game (SBGC-71 404). */
export class GameNotFoundError extends Error {
  constructor(readonly slug: string) {
    super(`Game not found: ${slug}`);
    this.name = "GameNotFoundError";
  }
}

/** Any backend/service failure that is not a game-not-found. */
export class BackendApiError extends Error {
  constructor(
    message: string,
    readonly failure?: ApiFailure,
  ) {
    super(message);
    this.name = "BackendApiError";
  }
}

/* ── API client functions ───────────────────────────────────────────────── */

/** Fetch one public Game detail from Django (SBGC-71). */
export async function getGameDetail(slug: string): Promise<GameDetailResponse> {
  const result = await getJSON<GameDetailResponse>(
    `/api/v1/games/${encodeURIComponent(slug)}`,
  );
  if (result.ok) {
    if ("data" in result) return result.data;
    throw new BackendApiError("Unexpected empty response from the API.");
  }
  if (result.status === 404) {
    throw new GameNotFoundError(slug);
  }
  throw new BackendApiError(result.error.message, result);
}

/**
 * Fetch the random Steam carousel selection for the homepage (SBGC-189).
 *
 * Django owns eligibility (public Steam base Games with a Library Capsule) and
 * random selection; the frontend never downloads the whole catalogue.
 */
export async function getHomepageCarousel(): Promise<HomepageCarouselCard[]> {
  const result = await getJSON<HomepageCarouselResponse>(
    "/api/v1/games/homepage",
  );
  if (result.ok) {
    if ("data" in result) return result.data.games;
    throw new BackendApiError("Unexpected empty response from the API.");
  }
  throw new BackendApiError(result.error.message, result);
}

/**
 * Fetch one page of the public Game catalogue from Django (SBGC-76).
 *
 * Django owns eligibility, search, filtering, ordering, and pagination; the
 * frontend only passes the page/page_size it wants to render.
 */
export async function getGameCatalogue(
  query: GameCatalogueQuery = {},
): Promise<GameCatalogueResponse> {
  const params: Record<string, string> = {};
  if (query.q !== undefined && query.q !== "") params.q = query.q;
  if (query.page !== undefined) params.page = String(query.page);
  if (query.pageSize !== undefined) params.page_size = String(query.pageSize);
  if (query.source !== undefined) params.source = query.source;
  if (query.classified !== undefined) {
    params.classified = query.classified ? "true" : "false";
  }
  if (query.sort !== undefined) params.sort = query.sort;
  if (query.profile !== undefined) params.profile = query.profile;
  if (query.dominant !== undefined) params.dominant = query.dominant;
  // Only send the explicit unchecked state; the backend defaults to true.
  if (query.coverlessLast === false) params.coverless_last = "false";

  const result = await getJSON<GameCatalogueResponse>("/api/v1/games/", {
    params,
  });
  if (result.ok) {
    if ("data" in result) return result.data;
    throw new BackendApiError("Unexpected empty response from the API.");
  }
  throw new BackendApiError(result.error.message, result);
}

/**
 * Fetch the complete compact public Game search index from Django (SBGC-78).
 *
 * Django owns eligibility and effective-artwork resolution; the frontend never
 * downloads catalogue pages to reconstruct this.  Deterministic order.
 */
export async function getGameSearchIndex(): Promise<GameSearchIndexItem[]> {
  const result = await getJSON<GameSearchIndexResponse>(
    "/api/v1/games/search-index",
  );
  if (result.ok) {
    if ("data" in result) return result.data.games;
    throw new BackendApiError("Unexpected empty response from the API.");
  }
  throw new BackendApiError(result.error.message, result);
}

/**
 * Fetch one page of the public Game ranking from Django (SBGC-81).
 *
 * Django owns eligibility, profile/dimension/direction score derivation,
 * dominance, ordering, and pagination; the frontend only renders the score it
 * is given and never recomputes Unified.
 */
export async function getGameRankings(
  query: RankingQuery = {},
): Promise<RankingResponse> {
  const params: Record<string, string> = {};
  if (query.profile !== undefined) params.profile = query.profile;
  if (query.dimension !== undefined) params.dimension = query.dimension;
  if (query.direction !== undefined) params.direction = query.direction;
  if (query.page !== undefined) params.page = String(query.page);
  if (query.pageSize !== undefined) params.page_size = String(query.pageSize);

  const result = await getJSON<RankingResponse>("/api/v1/rankings/", {
    params,
  });
  if (result.ok) {
    if ("data" in result) return result.data;
    throw new BackendApiError("Unexpected empty response from the API.");
  }
  throw new BackendApiError(result.error.message, result);
}
