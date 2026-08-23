import type { APIRoute } from "astro";

import { getGameSearchIndex } from "../../lib/server/api";

/**
 * Same-origin proxy for the compact public Game search index (SBGC-78).
 *
 * The browser never calls Django directly (CORS deny-by-default); this Astro
 * server route delegates to the SBGC-78 `GET /api/v1/games/search-index` on
 * the backend and returns the JSON to the client, which then caches it in
 * `sessionStorage`.
 */
export const prerender = false;

export const GET: APIRoute = async () => {
  try {
    const games = await getGameSearchIndex();
    return new Response(JSON.stringify({ games }), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        // sessionStorage is the cache; never let an HTTP cache serve a stale
        // index across the TTL boundary.
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
