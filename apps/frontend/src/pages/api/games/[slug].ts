import type { APIRoute } from "astro";

import {
  GameNotFoundError,
  getGameDetail,
} from "../../../lib/server/api/games";

/**
 * Same-origin proxy for a single public Game detail (SBGC-87).
 *
 * The browser never calls Django directly (CORS deny-by-default). The rankings
 * detail pane fetches this route to obtain the selected Game's Challenge/Reward
 * classification so it can render the radar without a full page navigation.
 */
export const prerender = false;

const json = (body: unknown, status: number): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });

export const GET: APIRoute = async ({ params }) => {
  const slug = params.slug;
  if (!slug) {
    return json({ error: { code: "GAME_NOT_FOUND" } }, 404);
  }

  try {
    const detail = await getGameDetail(slug);
    return json(detail, 200);
  } catch (error) {
    if (error instanceof GameNotFoundError) {
      return json({ error: { code: "GAME_NOT_FOUND" } }, 404);
    }
    return json({ error: { code: "SERVICE_UNAVAILABLE" } }, 503);
  }
};
