/**
 * Presentation-only helpers for the Game catalogue page — SBGC-77.
 *
 * Pure TypeScript — no fetch, no Django domain policy. Shapes the SBGC-76
 * catalogue DTO into page numbers, result summaries, pagination hrefs, and a
 * narrow classification state so the route and components stay thin.
 */

import type {
  ClassificationProfile,
  GameCatalogueClassification,
} from "./server/api/games";

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
  return page <= 1 ? "/catalogue" : `/catalogue?page=${page}`;
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
