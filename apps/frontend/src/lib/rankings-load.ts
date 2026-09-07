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

// ── AbortController-managed fetch (SBGC-200) ──────────────────────────────

/** The in-flight ranking request's controller, or null when none is pending. */
let activeAbortController: AbortController | null = null;

/** Exposed for tests: the controller backing the latest unresolved request. */
export function activeRankingsAbortController(): AbortController | null {
  return activeAbortController;
}

/**
 * Fetch rankings with in-flight request cancellation.
 *
 * Starting a new request aborts any unresolved previous request before
 * dispatching, so rapid tab/sort/page interactions never leave superseded
 * requests consuming bandwidth or server compute.  An optional external
 * ``signal`` is forwarded to ``fetch``; when absent, the module-level
 * controller's signal is used and cleared once the request settles.
 */
export async function fetchRankings(
  target: RankingsLoadTarget,
  signal?: AbortSignal,
): Promise<RankingResponse> {
  if (activeAbortController) {
    activeAbortController.abort();
  }

  const controller = new AbortController();
  activeAbortController = controller;
  const requestSignal = signal ?? controller.signal;

  try {
    const response = await fetch(buildRankingsUrl(target), {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: requestSignal,
    });
    if (!response.ok) {
      throw new Error(`HTTP error: ${response.status}`);
    }
    return (await response.json()) as RankingResponse;
  } finally {
    if (activeAbortController === controller) {
      activeAbortController = null;
    }
  }
}
