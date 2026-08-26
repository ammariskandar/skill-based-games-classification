/**
 * Ranking transition loader — SBGC-83.
 *
 * Owns the same-origin ranking fetch, its URL construction, and the in-flight
 * request ordering guard so a slow/earlier response can never overwrite a newer
 * one.  Pure of DOM — the Astro page controller supplies the fetch function and
 * interprets the discriminated outcome (success / error / stale).
 */

import type {
  RankingDimension,
  RankingDirection,
  RankingProfile,
} from "./rankings-state";
import type { RankingResponse } from "./server/api";

export interface RankingsLoadTarget {
  profile: RankingProfile;
  dimension: RankingDimension;
  direction: RankingDirection;
  page: number;
  pageSize: number;
}

export type RankingsLoadOutcome =
  | { kind: "success"; data: RankingResponse }
  | { kind: "error" }
  | { kind: "stale" };

/** Build the same-origin ranking proxy URL for a transition target. */
export function buildRankingsUrl(target: RankingsLoadTarget): string {
  const params = new URLSearchParams({
    profile: target.profile,
    dimension: target.dimension,
    direction: target.direction,
    page: String(target.page),
    page_size: String(target.pageSize),
  });
  return `/api/rankings?${params.toString()}`;
}

/**
 * Create a single-owner ranking transition loader.
 *
 * Every call increments a monotonically-increasing request id.  Only the newest
 * in-flight request may report ``success`` or ``error``; earlier requests that
 * settle after a newer one was started report ``stale`` so their payload is
 * discarded by the caller.
 */
export function createRankingsLoader(
  fetchFn: (url: string) => Promise<Response>,
): (target: RankingsLoadTarget) => Promise<RankingsLoadOutcome> {
  let inflight = 0;

  return async function load(
    target: RankingsLoadTarget,
  ): Promise<RankingsLoadOutcome> {
    const id = ++inflight;
    try {
      const response = await fetchFn(buildRankingsUrl(target));
      if (!response.ok) {
        throw new Error(`ranking fetch failed (${response.status})`);
      }
      const data = (await response.json()) as RankingResponse;
      if (id !== inflight) return { kind: "stale" };
      return { kind: "success", data };
    } catch {
      if (id !== inflight) return { kind: "stale" };
      return { kind: "error" };
    }
  };
}
