/**
 * Presentation-only helpers for the Rankings page — SBGC-82.
 *
 * Pure TypeScript — no fetch, no Django domain policy.  Owns the URL state
 * model, the six sort choices, score display rounding, and the viewport-driven
 * page-size math.  The SBGC-81 backend remains the sole authority for score
 * derivation, ordering, and pagination; the frontend never recomputes a
 * ranking or a Unified score.
 */

export type RankingProfile = "unified" | "challenge" | "reward";
export type RankingDimension = "micro" | "macro" | "mystiko";
export type RankingDirection = "desc" | "asc";

export interface RankingsState {
  profile: RankingProfile;
  dimension: RankingDimension;
  direction: RankingDirection;
  page: number;
  /** Selected Game slug, or null when no Game is selected. */
  game: string | null;
}

export const RANKING_PROFILES: readonly RankingProfile[] = [
  "unified",
  "challenge",
  "reward",
];

/** Dimension order for the six sort choices (canonical [micro, macro, mystiko]). */
export const RANKING_DIMENSIONS: readonly RankingDimension[] = [
  "micro",
  "macro",
  "mystiko",
];

export const RANKING_DIRECTIONS: readonly RankingDirection[] = ["desc", "asc"];

export const PROFILE_LABELS: Record<RankingProfile, string> = {
  unified: "Unified",
  challenge: "Challenge",
  reward: "Reward",
};

export const DEFAULT_RANKINGS_STATE: RankingsState = {
  profile: "unified",
  dimension: "micro",
  direction: "desc",
  page: 1,
  game: null,
};

export interface SortOption {
  dimension: RankingDimension;
  direction: RankingDirection;
  label: string;
}

/** The single sort control's six choices, in display order. */
export const SORT_OPTIONS: readonly SortOption[] = [
  { dimension: "micro", direction: "desc", label: "Micro — High to Low" },
  { dimension: "micro", direction: "asc", label: "Micro — Low to High" },
  { dimension: "macro", direction: "desc", label: "Macro — High to Low" },
  { dimension: "macro", direction: "asc", label: "Macro — Low to High" },
  { dimension: "mystiko", direction: "desc", label: "Mystiko — High to Low" },
  { dimension: "mystiko", direction: "asc", label: "Mystiko — Low to High" },
];

/** Stable key for the current (dimension, direction) selection. */
export function sortKeyFor(
  dimension: RankingDimension,
  direction: RankingDirection,
): string {
  return `${dimension}-${direction}`;
}

function normalizeProfile(raw: string | null): RankingProfile {
  return raw !== null && RANKING_PROFILES.includes(raw as RankingProfile)
    ? (raw as RankingProfile)
    : DEFAULT_RANKINGS_STATE.profile;
}

function normalizeDimension(raw: string | null): RankingDimension {
  return raw !== null && RANKING_DIMENSIONS.includes(raw as RankingDimension)
    ? (raw as RankingDimension)
    : DEFAULT_RANKINGS_STATE.dimension;
}

function normalizeDirection(raw: string | null): RankingDirection {
  return raw === "asc" ? "asc" : DEFAULT_RANKINGS_STATE.direction;
}

function parsePositiveInt(raw: string | null): number {
  if (raw === null) return 1;
  const trimmed = raw.trim();
  if (!/^[0-9]+$/.test(trimmed)) return 1;
  const value = Number(trimmed);
  return Number.isSafeInteger(value) && value >= 1 ? value : 1;
}

function normalizeGame(raw: string | null): string | null {
  const trimmed = (raw ?? "").trim();
  return trimmed === "" ? null : trimmed;
}

/**
 * Parse ranking URL search params into a normalized state.  Invalid values
 * fall back to the default state; the backend remains authoritative.
 */
export function parseRankingsState(
  searchParams: URLSearchParams,
): RankingsState {
  return {
    profile: normalizeProfile(searchParams.get("profile")),
    dimension: normalizeDimension(searchParams.get("dimension")),
    direction: normalizeDirection(searchParams.get("direction")),
    page: parsePositiveInt(searchParams.get("page")),
    game: normalizeGame(searchParams.get("game")),
  };
}

/**
 * Build a canonical ranking href.  Defaults are omitted so `/rankings` is the
 * default state URL; `page_size` is never part of the URL.
 */
export function rankingsHref(state: Partial<RankingsState>): string {
  const merged: RankingsState = { ...DEFAULT_RANKINGS_STATE, ...state };
  const params = new URLSearchParams();
  if (merged.profile !== "unified") params.set("profile", merged.profile);
  if (merged.dimension !== "micro") params.set("dimension", merged.dimension);
  if (merged.direction !== "desc") params.set("direction", merged.direction);
  if (merged.page > 1) params.set("page", String(merged.page));
  if (merged.game !== null) params.set("game", merged.game);
  const query = params.toString();
  return query ? `/rankings?${query}` : "/rankings";
}

/** Whether a ranking state is non-default and therefore `noindex`. */
export function rankingsNeedsNoindex(state: RankingsState): boolean {
  return (
    state.profile !== "unified" ||
    state.dimension !== "micro" ||
    state.direction !== "desc" ||
    state.page > 1 ||
    state.game !== null
  );
}

/**
 * Round a ranking score for display only (integer display).  Ordinary
 * mathematical rounding: `67.4 → 67`, `67.5 → 68`, `67.6 → 68`.  Never used
 * for sorting — sorting is the SBGC-81 backend's responsibility.
 */
export function formatRankingScore(score: number): number {
  return Math.round(score);
}

/**
 * Number of complete ranking rows that fit in `availableHeight` when each row
 * is `rowHeight` plus `gap`.  Accounts for the trailing gap and never returns
 * less than 1.
 */
export function calculatePageSize(
  availableHeight: number,
  rowHeight: number,
  gap: number,
): number {
  if (
    !Number.isFinite(availableHeight) ||
    !Number.isFinite(rowHeight) ||
    !Number.isFinite(gap)
  ) {
    return 1;
  }
  if (rowHeight <= 0) return 1;
  const step = rowHeight + gap;
  if (step <= 0) return 1;
  return Math.max(1, Math.floor((availableHeight + gap) / step));
}

/** Minimal identity shape shared by ranking rows and detail results. */
export interface RankingSelectionItem {
  slug: string;
  name: string;
}

/**
 * Resolve the Game shown in the detail pane from URL state (SBGC-83).
 *
 * A requested slug that is present on the active page wins; otherwise a
 * separately-resolved detail (e.g. ``getGameDetail``) is used.  When neither
 * resolves — a deleted/stale/unclassifiable ``?game=`` slug — the top-ranked
 * item is returned so the pane never shows a broken or empty selection.
 * ``null`` is returned only when there is no request and no data at all.
 */
export function resolveRankingSelection(
  requestedGame: string | null,
  results: readonly RankingSelectionItem[],
  resolvedDetail: RankingSelectionItem | null,
): RankingSelectionItem | null {
  if (requestedGame === null) return null;
  const inPage = results.find((game) => game.slug === requestedGame);
  if (inPage) return { slug: inPage.slug, name: inPage.name };
  if (resolvedDetail)
    return { slug: resolvedDetail.slug, name: resolvedDetail.name };
  if (results.length > 0)
    return { slug: results[0].slug, name: results[0].name };
  return null;
}

/** Classify the rankings empty state for truthful SSR rendering (SBGC-83). */
export type RankingsEmptyKind = "no-games" | "page-empty" | null;

/**
 * ``no-games`` when nothing is ranked at all, ``page-empty`` when an
 * out-of-range page slice has no rows, or ``null`` for a populated list.
 */
export function rankingsEmptyKind(
  count: number,
  resultsCount: number,
): RankingsEmptyKind {
  if (count === 0) return "no-games";
  if (resultsCount === 0) return "page-empty";
  return null;
}

/**
 * Normalize a raw ``page_size`` query value to a safe integer.
 *
 * ``null``/non-numeric/non-positive values fall back to ``fallback``; values
 * above ``max`` are clamped.  Used by the same-origin rankings proxy, never by
 * shareable URL state.
 */
export function normalizePageSize(
  raw: string | null,
  fallback: number,
  max: number,
): number {
  if (raw === null) return fallback;
  const trimmed = raw.trim();
  if (!/^[0-9]+$/.test(trimmed)) return fallback;
  const value = Number(trimmed);
  if (!Number.isSafeInteger(value) || value < 1) return fallback;
  return Math.min(value, max);
}
