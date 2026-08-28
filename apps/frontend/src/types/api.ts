/**
 * Shared frontend API contract (SBGC-89).
 *
 * Hand-authored TypeScript DTOs that mirror the Django Ninja response schemas
 * for every public endpoint the Astro frontend consumes.  Django is the single
 * source of truth for field names, nullability, and value domains — these types
 * only *describe* the wire payload and never calculate scores, resolve image
 * precedence, or reinterpret a value locally.
 */

/* ── Canonical enums & unions ──────────────────────────────────────────── */

export type GameSource = "steam" | "manual";

export type ClassificationRegime = "provisional" | "unified" | "none";

export type RankingProfile = "unified" | "challenge" | "reward";

export type RankingDimension = "micro" | "macro" | "mystiko";

export type RankingDirection = "desc" | "asc";

export type CatalogueSort =
  "name_asc" | "name_desc" | "recent" | "micro" | "mystiko" | "macro";

export type CatalogueProfile = "challenge" | "reward";

export type CatalogueDominant = "micro" | "mystiko" | "macro";

/* ── Classification & dimension DTOs ───────────────────────────────────── */

/**
 * A three-component skill profile in Django's canonical display order
 * (`micro`, `macro`, `mystiko`).  Never fabricated: missing data is expressed
 * as `null` on the parent field, never as a `0/0/0` vector.
 */
export interface SkillDimensionsDto {
  micro: number;
  macro: number;
  mystiko: number;
}

/** The currently published Final Classification, or `null` when none exists. */
export interface PublishedClassificationDto {
  status: string;
  regime: ClassificationRegime | null;
  challenge: SkillDimensionsDto | null;
  reward: SkillDimensionsDto | null;
  confidence_level: number | null;
  confidence_label: string | null;
  submission_count: number | null;
  calculation_version: string | null;
  calculated_at: string | null;
  is_stale: boolean;
}

/* ── Game detail DTOs ──────────────────────────────────────────────────── */

/** Normalized public Game identity and persisted metadata (SBGC-71). */
export interface PublicGameDetailDto {
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

export interface GameDetailResponseDto {
  game: PublicGameDetailDto;
  classification: PublishedClassificationDto | null;
}

/* ── Homepage carousel DTOs ────────────────────────────────────────────── */

export interface HomepageCarouselCardDto {
  slug: string;
  name: string;
  library_capsule_url: string;
}

export interface HomepageCarouselResponseDto {
  games: HomepageCarouselCardDto[];
}

/* ── Catalogue DTOs ────────────────────────────────────────────────────── */

/** Narrow public classification summary for a catalogue item (SBGC-76). */
export interface GameCatalogueClassificationDto {
  status: string;
  challenge: SkillDimensionsDto | null;
  reward: SkillDimensionsDto | null;
  confidence_level: number | null;
  confidence_label: string | null;
  is_stale: boolean;
}

export interface GameCatalogueItemDto {
  slug: string;
  name: string;
  source: GameSource;
  image_url: string;
  library_capsule_url: string | null;
  classification: GameCatalogueClassificationDto | null;
}

/** Paginated public Game catalogue envelope (SBGC-76). */
export interface GameCatalogueResponseDto {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: GameCatalogueItemDto[];
}

/* ── Search index DTOs ─────────────────────────────────────────────────── */

export interface GameSearchIndexItemDto {
  slug: string;
  name: string;
  capsule_url: string | null;
  image_url: string | null;
}

export interface GameSearchIndexResponseDto {
  games: GameSearchIndexItemDto[];
}

/* ── Rankings DTOs ─────────────────────────────────────────────────────── */

/**
 * One public ranking row (SBGC-81).  `score` is integer for Challenge/Reward
 * and `(Challenge + Reward) / 2` for Unified (which may end in `.5`).
 */
export interface RankingItemDto {
  slug: string;
  name: string;
  hero_url: string;
  score: number;
}

/** Paginated public ranking envelope (SBGC-81). */
export interface RankingResponseDto {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: RankingItemDto[];
}

/* ── Request query inputs ──────────────────────────────────────────────── */

/** Catalogue request inputs (SBGC-76/78/79).  `pageSize` is never URL state. */
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

/** Ranking request inputs (SBGC-81).  `pageSize` is viewport-derived. */
export interface RankingQuery {
  profile?: RankingProfile;
  dimension?: RankingDimension;
  direction?: RankingDirection;
  page?: number;
  pageSize?: number;
}

/* ── Standard error envelope ───────────────────────────────────────────── */

/** One validation or error detail entry. */
export interface ApiErrorDetailDto {
  location: Array<string | number>;
  message: string;
  type: string;
}

/** Standardised machine-readable error body. */
export interface ApiErrorDto {
  code: string;
  message: string;
  details: ApiErrorDetailDto[];
}

/** Top-level error response envelope (`{ "error": { ... } }`). */
export interface ApiErrorResponseDto {
  error: ApiErrorDto;
}
