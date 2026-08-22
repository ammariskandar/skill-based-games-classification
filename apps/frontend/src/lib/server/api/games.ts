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
