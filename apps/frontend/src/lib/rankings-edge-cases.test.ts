/**
 * Rankings edge-case tests — SBGC-83.
 *
 * Locks down URL normalization, empty-state classification, selected-game
 * fallback, page-size clamping, the fetch URL builder, and the in-flight
 * request race/error handling.  Pure helpers and a DOM-free loader are tested;
 * no network or browser is required.
 */

import { describe, expect, it, vi } from "vitest";

import {
  normalizePageSize,
  parseRankingsState,
  rankingsEmptyKind,
  resolveRankingSelection,
} from "./rankings-state";
import { buildRankingsUrl, createRankingsLoader } from "./rankings-load";
import type { RankingsLoadTarget } from "./rankings-load";
import type { RankingResponse } from "./server/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function rankingResponse(results: RankingResponse["results"]): RankingResponse {
  return {
    count: results.length,
    page: 1,
    page_size: 24,
    total_pages: 1,
    results,
  };
}

const TARGET: RankingsLoadTarget = {
  profile: "challenge",
  dimension: "micro",
  direction: "desc",
  page: 1,
  pageSize: 5,
};

describe("parseRankingsState edge cases", () => {
  it("normalizes negative and non-integer pages to 1", () => {
    expect(parseRankingsState(new URLSearchParams("page=-5")).page).toBe(1);
    expect(parseRankingsState(new URLSearchParams("page=abc")).page).toBe(1);
    expect(parseRankingsState(new URLSearchParams("page=1.5")).page).toBe(1);
  });

  it("normalizes invalid profile/dimension/direction to defaults", () => {
    const state = parseRankingsState(
      new URLSearchParams("profile=bogus&dimension=unknown&direction=sideways"),
    );
    expect(state).toEqual({
      profile: "unified",
      dimension: "micro",
      direction: "desc",
      page: 1,
      game: null,
    });
  });

  it("keeps a valid ascending direction", () => {
    const state = parseRankingsState(new URLSearchParams("direction=asc"));
    expect(state.direction).toBe("asc");
  });
});

describe("normalizePageSize", () => {
  it("clamps non-positive and non-numeric values to the fallback", () => {
    expect(normalizePageSize(null, 5, 50)).toBe(5);
    expect(normalizePageSize("0", 5, 50)).toBe(5);
    expect(normalizePageSize("-10", 5, 50)).toBe(5);
    expect(normalizePageSize("abc", 5, 50)).toBe(5);
  });

  it("clamps values above the maximum", () => {
    expect(normalizePageSize("1000", 5, 50)).toBe(50);
  });

  it("keeps valid in-range values", () => {
    expect(normalizePageSize("8", 5, 50)).toBe(8);
  });
});

describe("rankingsEmptyKind", () => {
  it("classifies zero ranked games as no-games", () => {
    expect(rankingsEmptyKind(0, 0)).toBe("no-games");
  });

  it("classifies an out-of-range page as page-empty", () => {
    expect(rankingsEmptyKind(10, 0)).toBe("page-empty");
  });

  it("returns null for a populated list", () => {
    expect(rankingsEmptyKind(10, 10)).toBeNull();
  });
});

describe("resolveRankingSelection", () => {
  const results = [
    { slug: "top", name: "Top" },
    { slug: "second", name: "Second" },
  ];

  it("returns null when nothing is requested", () => {
    expect(resolveRankingSelection(null, results, null)).toBeNull();
  });

  it("prefers the in-page row", () => {
    expect(resolveRankingSelection("second", results, null)).toEqual({
      slug: "second",
      name: "Second",
    });
  });

  it("uses a separately-resolved detail when not on the page", () => {
    expect(
      resolveRankingSelection("off-page", results, {
        slug: "off-page",
        name: "Off Page",
      }),
    ).toEqual({ slug: "off-page", name: "Off Page" });
  });

  it("falls back to the top-ranked item for an unresolvable slug", () => {
    expect(resolveRankingSelection("does-not-exist", results, null)).toEqual({
      slug: "top",
      name: "Top",
    });
  });

  it("returns null when there are no results at all", () => {
    expect(resolveRankingSelection("anything", [], null)).toBeNull();
  });
});

describe("buildRankingsUrl", () => {
  it("serializes profile, dimension, direction, page, and pageSize", () => {
    expect(buildRankingsUrl(TARGET)).toBe(
      "/api/rankings?profile=challenge&dimension=micro&direction=desc&page=1&page_size=5",
    );
  });
});

describe("createRankingsLoader", () => {
  it("reports success and the parsed envelope for the newest request", async () => {
    const body = rankingResponse([
      { slug: "hades", name: "Hades", hero_url: "", score: 70 },
    ]);
    const load = createRankingsLoader(
      vi.fn().mockResolvedValue(jsonResponse(body)),
    );
    const outcome = await load(TARGET);
    expect(outcome).toEqual({ kind: "success", data: body });
  });

  it("discards a stale slow response that settles after a newer one", async () => {
    const calls: Array<{ url: string; resolve: (r: Response) => void }> = [];
    const fetchFn = (url: string) =>
      new Promise<Response>((resolve) => {
        calls.push({ url, resolve });
      });

    const load = createRankingsLoader(fetchFn);
    const slow = load(TARGET);
    const fast = load({ ...TARGET, page: 2 });

    // Newer request settles first.
    calls[1].resolve(jsonResponse(rankingResponse([])));
    const fastOutcome = await fast;
    expect(fastOutcome.kind).toBe("success");

    // Older request settles later and must be classified stale.
    calls[0].resolve(jsonResponse(rankingResponse([])));
    const slowOutcome = await slow;
    expect(slowOutcome.kind).toBe("stale");
  });

  it("reports error when the fetch rejects", async () => {
    const load = createRankingsLoader(
      vi.fn().mockRejectedValue(new Error("network")),
    );
    expect(await load(TARGET)).toEqual({ kind: "error" });
  });

  it("reports error on a non-2xx response", async () => {
    const load = createRankingsLoader(
      vi.fn().mockResolvedValue(jsonResponse({ error: {} }, 500)),
    );
    expect(await load(TARGET)).toEqual({ kind: "error" });
  });
});
