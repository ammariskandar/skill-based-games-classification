/**
 * Pure autocomplete matcher for the compact public Game search index — SBGC-78.
 *
 * No fetch, no DOM, no fuzzy dependency: for ~200 Games a single linear scan is
 * plenty. Ranks prefix matches before substring matches, preserving the
 * backend's deterministic `name ASC, id ASC` order as a stable alphabetical
 * tie-break.
 */

import type { GameSearchIndexItem } from "./server/api/games";

/** Maximum suggestions shown at once. */
export const MAX_SEARCH_SUGGESTIONS = 6;

/** Normalize user input for matching: trim + lowercase. */
export function normalizeQuery(raw: string): string {
  return raw.trim().toLowerCase();
}

/**
 * Return up to `max` matching Games for `rawQuery`.
 *
 * An empty (or whitespace-only) query returns no suggestions.  Matching is
 * against the canonical Game name only, case-insensitively.
 */
export function searchGames(
  games: readonly GameSearchIndexItem[],
  rawQuery: string,
  max: number = MAX_SEARCH_SUGGESTIONS,
): GameSearchIndexItem[] {
  const query = normalizeQuery(rawQuery);
  if (query === "") return [];

  const startsWith: GameSearchIndexItem[] = [];
  const contains: GameSearchIndexItem[] = [];

  for (const game of games) {
    const name = game.name.toLowerCase();
    if (name.startsWith(query)) {
      startsWith.push(game);
    } else if (name.includes(query)) {
      contains.push(game);
    }
  }

  // The input is already deterministic (name ASC, id ASC), so concatenating the
  // two buckets preserves a stable alphabetical order within each rank.
  return [...startsWith, ...contains].slice(0, max);
}
