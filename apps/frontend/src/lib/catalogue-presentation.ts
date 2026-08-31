/**
 * Presentation-only helpers for the Game catalogue page — SBGC-77 / SBGC-79.
 *
 * Pure TypeScript — no fetch, no Django domain policy. Shapes the SBGC-76
 * catalogue DTO into page numbers, result summaries, pagination hrefs, a narrow
 * classification state, and the SBGC-79 filter/sort query state so the route
 * and components stay thin.
 */

import type {
  CatalogueDominant,
  CatalogueProfile,
  CatalogueSort,
  ClassificationProfile,
  GameCatalogueClassification,
  GameSource,
} from "./server/api/games";
import { getSafeQueryString } from "./server/api/query";

/** Normalize the `?page=` query value to a safe positive page number. */
export function parsePageParam(raw: string | null): number {
  if (raw === null) return 1;
  const trimmed = raw.trim();
  if (!/^[0-9]+$/.test(trimmed)) return 1;
  const value = Number(trimmed);
  return Number.isSafeInteger(value) && value >= 1 ? value : 1;
}

/** "0 games", "1 game", "42 games". */
export function formatGameCount(count: number): string {
  return `${count} ${count === 1 ? "game" : "games"}`;
}

export interface ResultRange {
  start: number;
  end: number;
}

/** 1-based inclusive range of items shown on a page, or null when empty. */
export function computeResultRange(
  count: number,
  page: number,
  pageSize: number,
): ResultRange | null {
  if (count <= 0 || page < 1 || pageSize < 1) return null;
  const start = (page - 1) * pageSize + 1;
  if (start > count) return null;
  const end = Math.min(start + pageSize - 1, count);
  return { start, end };
}

/** "Showing 1–24 of 42 games", or just the count when the page is out of range. */
export function formatResultSummary(
  count: number,
  page: number,
  pageSize: number,
): string {
  const range = computeResultRange(count, page, pageSize);
  if (range === null) return formatGameCount(count);
  return `Showing ${range.start}–${range.end} of ${formatGameCount(count)}`;
}

/** Canonical catalogue href for a page number (page 1 is the bare route). */
export function cataloguePageHref(page: number): string {
  return catalogueHref({ page });
}

// ── SBGC-79 filter/sort query state ────────────────────────────────────────

const SORT_IDS: readonly string[] = [
  "name_asc",
  "name_desc",
  "recent",
  "micro",
  "mystiko",
  "macro",
];

const DOMINANT_IDS: readonly string[] = ["micro", "mystiko", "macro"];

export const DEFAULT_CATALOGUE_SORT: CatalogueSort = "name_asc";
export const DEFAULT_CATALOGUE_PROFILE: CatalogueProfile = "challenge";

/** Whether a sort is a skill-score sort (Micro / Mystiko / Macro). */
export function isSkillSort(sort: CatalogueSort): boolean {
  return sort === "micro" || sort === "mystiko" || sort === "macro";
}

/** Normalized catalogue query state (defaults applied, invalid values dropped). */
export interface CatalogueQueryState {
  q: string;
  page: number;
  source: GameSource | null;
  classified: boolean | null;
  sort: CatalogueSort;
  profile: CatalogueProfile;
  dominant: CatalogueDominant | null;
  coverlessLast: boolean;
}

function parseOptionalBool(raw: string | null): boolean | null {
  if (raw === "true") return true;
  if (raw === "false") return false;
  return null;
}

function normalizeSort(raw: string | null): CatalogueSort {
  return raw !== null && SORT_IDS.includes(raw)
    ? (raw as CatalogueSort)
    : DEFAULT_CATALOGUE_SORT;
}

function normalizeProfile(raw: string | null): CatalogueProfile {
  return raw === "reward" ? "reward" : DEFAULT_CATALOGUE_PROFILE;
}

function normalizeDominant(raw: string | null): CatalogueDominant | null {
  return raw !== null && DOMINANT_IDS.includes(raw)
    ? (raw as CatalogueDominant)
    : null;
}

function normalizeSource(raw: string | null): GameSource | null {
  return raw === "steam" || raw === "manual" ? raw : null;
}

/**
 * Parse the catalogue URL search params into a normalized state.
 *
 * Invalid values fall back to the default/absent state (the backend is
 * authoritative, so the page never renders a broken combination).  The
 * cover-last checkbox is checked by default; only an explicit
 * ``coverless_last=false`` turns it off.
 */
export function parseCatalogueQuery(
  searchParams: URLSearchParams,
): CatalogueQueryState {
  // A checked cover-last checkbox submits `coverless_last=true` alongside a
  // hidden `coverless_last=false`, so the key may appear twice.  Treat an
  // explicit `true` anywhere as checked and absence as the default checked
  // state — the exact mirror of the backend's
  // `"true" in request.GET.getlist("coverless_last")` contract.
  const coverValues = searchParams.getAll("coverless_last");
  const sort = normalizeSort(searchParams.get("sort"));
  return {
    // SBGC-102: strip control characters, trim, and cap at the backend's
    // 100-char `max_length` so an over-long/malformed query can never 422.
    q: getSafeQueryString(searchParams, "q") ?? "",
    page: parsePageParam(searchParams.get("page")),
    source: normalizeSource(searchParams.get("source")),
    classified: parseOptionalBool(searchParams.get("classified")),
    sort,
    // Profile only matters for skill sorts; drop any irrelevant `profile`
    // (e.g. `profile=reward` with `sort=name_asc`) back to the default.
    profile: isSkillSort(sort)
      ? normalizeProfile(searchParams.get("profile"))
      : DEFAULT_CATALOGUE_PROFILE,
    dominant: normalizeDominant(searchParams.get("dominant")),
    coverlessLast: coverValues.length === 0 || coverValues.includes("true"),
  };
}

export interface CatalogueHrefParams {
  page?: number;
  q?: string;
  source?: GameSource | null;
  classified?: boolean | null;
  sort?: CatalogueSort;
  profile?: CatalogueProfile;
  dominant?: CatalogueDominant | null;
  coverlessLast?: boolean;
}

/**
 * Build a catalogue href preserving any active query parameters.
 *
 * Defaults are omitted to keep URLs canonical: page 1, ``name_asc`` sort,
 * ``challenge`` profile, and a checked cover-last checkbox.  An explicitly
 * unchecked cover-last state is represented as ``coverless_last=false``.
 */
export function catalogueHref(params: CatalogueHrefParams = {}): string {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.page !== undefined && params.page > 1) {
    search.set("page", String(params.page));
  }
  if (params.source) search.set("source", params.source);
  if (params.classified !== undefined && params.classified !== null) {
    search.set("classified", params.classified ? "true" : "false");
  }
  if (params.sort !== undefined && params.sort !== DEFAULT_CATALOGUE_SORT) {
    search.set("sort", params.sort);
  }
  if (
    params.profile !== undefined &&
    params.profile !== DEFAULT_CATALOGUE_PROFILE
  ) {
    search.set("profile", params.profile);
  }
  if (params.dominant) search.set("dominant", params.dominant);
  if (params.coverlessLast === false) search.set("coverless_last", "false");
  const query = search.toString();
  return query ? `/catalogue?${query}` : "/catalogue";
}

/**
 * Whether a catalogue query state is non-default and therefore should be
 * ``noindex``.  Base catalogue (no search/filter/non-default sort) stays
 * indexable; an explicitly unchecked cover-last state is also non-default.
 */
export function catalogueNeedsNoindex(state: CatalogueQueryState): boolean {
  return (
    state.q !== "" ||
    state.source !== null ||
    state.classified !== null ||
    state.sort !== DEFAULT_CATALOGUE_SORT ||
    state.profile !== DEFAULT_CATALOGUE_PROFILE ||
    state.dominant !== null ||
    !state.coverlessLast
  );
}

/** Build a catalogue href from a parsed state, optionally overriding the page. */
export function catalogueHrefFromState(
  state: CatalogueQueryState,
  page?: number,
): string {
  return catalogueHref({
    q: state.q || undefined,
    page,
    source: state.source,
    classified: state.classified,
    sort: state.sort,
    profile: state.profile,
    dominant: state.dominant,
    coverlessLast: state.coverlessLast,
  });
}

/** Public Game-detail href for a slug (used by the catalogue card link). */
export function gameHref(slug: string): string {
  return `/games/${slug}`;
}

export type CatalogueClassificationPresentation =
  | { kind: "unclassified" }
  | {
      kind: "classified";
      challenge: ClassificationProfile;
      reward: ClassificationProfile;
      isStale: boolean;
    };

/**
 * Narrow a catalogue classification summary into an unclassified or classified
 * state. `null` (or a missing profile) is treated as "not yet classified".
 */
export function presentCatalogueClassification(
  classification: GameCatalogueClassification | null,
): CatalogueClassificationPresentation {
  if (
    classification === null ||
    classification.challenge === null ||
    classification.reward === null
  ) {
    return { kind: "unclassified" };
  }
  return {
    kind: "classified",
    challenge: classification.challenge,
    reward: classification.reward,
    isStale: classification.is_stale,
  };
}
