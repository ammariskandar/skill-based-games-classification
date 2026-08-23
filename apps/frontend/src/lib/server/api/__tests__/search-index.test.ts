/**
 * Behavioural tests for the game search-index API boundary (SBGC-78).
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

const INDEX = {
  games: [
    {
      slug: "hades",
      name: "Hades",
      capsule_url: "https://example.com/hades-capsule.jpg",
      image_url: "https://example.com/hades-header.jpg",
    },
    {
      slug: "bare-manual",
      name: "Bare Manual",
      capsule_url: null,
      image_url: null,
    },
  ],
};

describe("getGameSearchIndex", () => {
  beforeEach(() => {
    setEnv("http://backend.test");
  });

  it("returns the parsed game list on a 200 response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(INDEX));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameSearchIndex } = await importGames();
    const games = await getGameSearchIndex();

    expect(games).toHaveLength(2);
    expect(games[0].slug).toBe("hades");
    expect(games[0].capsule_url).toBe("https://example.com/hades-capsule.jpg");
    expect(games[1].capsule_url).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("calls the search-index endpoint path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(INDEX));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameSearchIndex } = await importGames();
    await getGameSearchIndex();

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("http://backend.test/api/v1/games/search-index");
  });

  it("throws BackendApiError on a Django 500", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ error: { code: "INTERNAL_SERVER_ERROR" } }, 500),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { BackendApiError, getGameSearchIndex } = await importGames();
    await expect(getGameSearchIndex()).rejects.toBeInstanceOf(BackendApiError);
  });

  it("throws BackendApiError on a network failure", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameSearchIndex } = await importGames();
    await expect(getGameSearchIndex()).rejects.toMatchObject({
      name: "BackendApiError",
    });
  });
});
