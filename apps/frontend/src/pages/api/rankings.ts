import type { APIRoute } from "astro";

import { getGameRankings, type CatalogueDominant } from "../../lib/server/api";
import {
  normalizePageSize,
  parseRankingsState,
} from "../../lib/rankings-state";

/**
 * Same-origin proxy for the SBGC-81 public Game ranking endpoint.
 *
 * The browser never calls Django directly (CORS deny-by-default); this Astro
 * server route validates/normalizes the ranking parameters, delegates to
 * `getGameRankings`, and returns the ranking DTO.  It owns no ranking
 * calculation — only transport and normalization.
 *
 * `page_size` is viewport-derived and is accepted here (but never part of the
 * shareable URL state).
 */
export const prerender = false;

const DEFAULT_PAGE_SIZE = 5;
const MAX_PAGE_SIZE = 50;

/** Normalize a raw `dominant` query value; invalid or absent values are dropped. */
function normalizeDominant(raw: string | null): CatalogueDominant | undefined {
  if (raw === "micro" || raw === "mystiko" || raw === "macro") return raw;
  return undefined;
}

export const GET: APIRoute = async ({ url, request }) => {
  const state = parseRankingsState(url.searchParams);
  const dominant = normalizeDominant(url.searchParams.get("dominant"));
  const pageSize = normalizePageSize(
    url.searchParams.get("page_size"),
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
  );

  try {
    const data = await getGameRankings(
      {
        profile: state.profile,
        dimension: state.dimension,
        direction: state.direction,
        dominant,
        page: state.page,
        pageSize,
      },
      { signal: request.signal },
    );
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        // The ranking is live persisted data; never cache a stale page.
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return new Response(
      JSON.stringify({ error: { code: "SERVICE_UNAVAILABLE" } }),
      {
        status: 503,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
};
