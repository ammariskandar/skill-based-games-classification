/**
 * Behavioural tests for the rankings API boundary (SBGC-82).
 *
 * Every test mocks globalThis.fetch — no real network requests are made.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

function setEnv(value: string) {
  vi.stubEnv("DJANGO_API_URL", value);
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function importGames() {
  vi.resetModules();
  return import("../games");
}

const RANKING = {
  count: 2,
  page: 1,
  page_size: 5,
  total_pages: 1,
  results: [
    {
      slug: "hades",
      name: "Hades",
      hero_url: "https://example.com/hades-hero.jpg",
      score: 70,
    },
    {
      slug: "portal-2",
      name: "Portal 2",
      hero_url: "",
      score: 67.5,
    },
  ],
};

describe("getGameRankings", () => {
  beforeEach(() => {
    setEnv("https://backend.test");
  });

  it("returns the parsed ranking envelope on a 200 response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(RANKING));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameRankings } = await importGames();
    const ranking = await getGameRankings();

    expect(ranking.count).toBe(2);
    expect(ranking.page_size).toBe(5);
    expect(ranking.results).toHaveLength(2);
    expect(ranking.results[0]).toEqual({
      slug: "hades",
      name: "Hades",
      hero_url: "https://example.com/hades-hero.jpg",
      score: 70,
    });
    // Unified .5 score is preserved verbatim, never rounded in the boundary.
    expect(ranking.results[1].score).toBe(67.5);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("calls the rankings endpoint with its trailing slash and no params by default", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(RANKING));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameRankings } = await importGames();
    await getGameRankings();

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("https://backend.test/api/v1/rankings/");
  });

  it("serializes profile, dimension, direction, page, and pageSize", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(RANKING));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameRankings } = await importGames();
    await getGameRankings({
      profile: "reward",
      dimension: "mystiko",
      direction: "asc",
      page: 2,
      pageSize: 8,
    });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe(
      "https://backend.test/api/v1/rankings/?profile=reward&dimension=mystiko&direction=asc&page=2&page_size=8",
    );
  });

  it("throws BackendApiError on a Django 500", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ error: { code: "INTERNAL_SERVER_ERROR" } }, 500),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { BackendApiError, getGameRankings } = await importGames();
    await expect(getGameRankings()).rejects.toBeInstanceOf(BackendApiError);
  });
});
