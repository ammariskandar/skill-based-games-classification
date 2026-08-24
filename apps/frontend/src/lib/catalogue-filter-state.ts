/**
 * Catalogue filter-disclosure preference — SBGC-79.
 *
 * The expanded/collapsed state of the catalogue filter card is a browser UI
 * preference persisted in `localStorage`.  It is deliberately **not** catalogue
 * query/filter state: it never touches the URL, the Django API, sessions, or
 * cookies.  This module owns the versioned key and the boolean serialization
 * contract so the runtime script and the tests share one source of truth.
 */

/** Versioned, project-scoped storage key for the filter-card disclosure. */
export const CATALOGUE_FILTER_EXPANDED_STORAGE_KEY =
  "mygamedna:catalogue-filters-expanded:v1";

/** Serialize the disclosure preference to its stored string form. */
export function serializeFilterExpanded(expanded: boolean): "true" | "false" {
  return expanded ? "true" : "false";
}

/**
 * Parse a stored disclosure value.  Returns `null` when absent or unrecognized
 * so the caller can fall back to its SSR/default state.
 */
export function parseFilterExpanded(raw: string | null): boolean | null {
  if (raw === "true") return true;
  if (raw === "false") return false;
  return null;
}
