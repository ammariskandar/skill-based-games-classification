/**
 * Game-detail API boundary — SBGC-72.
 *
 * Server-side only: fetches the SBGC-71 public game-detail DTO from Django.
 * Distinguishes a game-not-found (Django 404) from backend/service failures
 * so the route can render a real 404 versus a real error page.
 */

import { getJSON } from "./client";
import type { ApiFailure } from "./types";

export type GameSource = "steam" | "manual";

export type ClassificationRegime = "provisional" | "unified" | "none";

export interface GameDetailGame {
  id: number;
  slug: string;
  name: string;
  source: GameSource;
  external_id: string | null;
  content_type: string;
  description: string;
  release_date: string | null;
  developer: string;
  image_url: string;
  library_hero_url: string | null;
  library_capsule_url: string | null;
  metadata_updated_at: string;
}

export interface ClassificationProfile {
  micro: number;
  macro: number;
  mystiko: number;
}

export interface GameFinalClassification {
  status: string;
  regime: ClassificationRegime | null;
  challenge: ClassificationProfile | null;
  reward: ClassificationProfile | null;
  confidence_level: number | null;
  confidence_label: string | null;
  submission_count: number | null;
  calculation_version: string | null;
  calculated_at: string | null;
  is_stale: boolean;
}

export interface GameDetailResponse {
  game: GameDetailGame;
  classification: GameFinalClassification | null;
}

/** One homepage carousel card: slug, name, and the Library Capsule URL. */
export interface HomepageCarouselCard {
  slug: string;
  name: string;
  library_capsule_url: string;
}

export interface HomepageCarouselResponse {
  games: HomepageCarouselCard[];
}

/** Narrow public classification summary for a catalogue item (SBGC-76). */
export interface GameCatalogueClassification {
  status: string;
  challenge: ClassificationProfile | null;
  reward: ClassificationProfile | null;
  confidence_level: number | null;
  confidence_label: string | null;
  is_stale: boolean;
}

/** One public catalogue item with effective artwork (SBGC-76). */
export interface GameCatalogueItem {
  slug: string;
  name: string;
  source: GameSource;
  image_url: string;
  library_capsule_url: string | null;
  classification: GameCatalogueClassification | null;
}

/** Paginated public Game catalogue envelope (SBGC-76). */
export interface GameCatalogueResponse {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: GameCatalogueItem[];
}

/** One compact search-index entry for client-side autocomplete (SBGC-78). */
export interface GameSearchIndexItem {
  slug: string;
  name: string;
  capsule_url: string | null;
  image_url: string | null;
}

/** Complete compact public Game search index (SBGC-78). */
export interface GameSearchIndexResponse {
  games: GameSearchIndexItem[];
}

/** Primary catalogue sort identifiers (SBGC-79). */
export type CatalogueSort =
  "name_asc" | "name_desc" | "recent" | "micro" | "mystiko" | "macro";

/** Explicit Challenge/Reward profile for score sort and dominant filter. */
export type CatalogueProfile = "challenge" | "reward";

/** Dominant skill category for the dominant filter. */
export type CatalogueDominant = "micro" | "mystiko" | "macro";

/** Catalogue request inputs (SBGC-76/78/79). */
export interface GameCatalogueQuery {
  q?: string;
  page?: number;
  pageSize?: number;
  source?: GameSource;
  classified?: boolean;
  sort?: CatalogueSort;
  profile?: CatalogueProfile;
  dominant?: CatalogueDominant;
  coverlessLast?: boolean;
}

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
