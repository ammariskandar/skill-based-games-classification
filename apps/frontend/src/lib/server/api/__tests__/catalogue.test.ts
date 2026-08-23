/**
 * Behavioural tests for the game-catalogue API boundary (SBGC-77).
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

const CATALOGUE = {
  count: 2,
  page: 1,
  page_size: 24,
  total_pages: 1,
  results: [
    {
      slug: "hades",
      name: "Hades",
      source: "steam",
      image_url: "https://example.com/hades-header.jpg",
      library_capsule_url: "https://example.com/hades-capsule.jpg",
      classification: {
        status: "READY",
        challenge: { micro: 51, macro: 31, mystiko: 18 },
        reward: { micro: 17, macro: 29, mystiko: 54 },
        confidence_level: 80,
        confidence_label: "High",
        is_stale: false,
      },
    },
    {
      slug: "manual-game",
      name: "Manual Game",
      source: "manual",
      image_url: "https://example.com/manual.jpg",
      library_capsule_url: null,
      classification: null,
    },
  ],
};

describe("getGameCatalogue", () => {
  beforeEach(() => {
    setEnv("http://backend.test");
  });

  it("returns the parsed catalogue envelope on a 200 response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(CATALOGUE));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameCatalogue } = await importGames();
    const catalogue = await getGameCatalogue();

    expect(catalogue.count).toBe(2);
    expect(catalogue.total_pages).toBe(1);
    expect(catalogue.results).toHaveLength(2);
    expect(catalogue.results[0].slug).toBe("hades");
    expect(catalogue.results[0].source).toBe("steam");
    expect(catalogue.results[0].library_capsule_url).toBe(
      "https://example.com/hades-capsule.jpg",
    );
    expect(catalogue.results[0].classification?.challenge).toEqual({
      micro: 51,
      macro: 31,
      mystiko: 18,
    });
    expect(catalogue.results[1].classification).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("calls the catalogue endpoint with its trailing slash and no params by default", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(CATALOGUE));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameCatalogue } = await importGames();
    await getGameCatalogue();

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("http://backend.test/api/v1/games/");
  });

  it("serializes the page parameter onto the catalogue endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(CATALOGUE));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameCatalogue } = await importGames();
    await getGameCatalogue({ page: 3 });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("http://backend.test/api/v1/games/?page=3");
  });

  it("serializes page and pageSize parameters together", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(CATALOGUE));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameCatalogue } = await importGames();
    await getGameCatalogue({ page: 2, pageSize: 50 });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("http://backend.test/api/v1/games/?page=2&page_size=50");
  });

  it("throws BackendApiError on a Django 500", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ error: { code: "INTERNAL_SERVER_ERROR" } }, 500),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { BackendApiError, getGameCatalogue } = await importGames();
    await expect(getGameCatalogue()).rejects.toBeInstanceOf(BackendApiError);
  });

  it("throws BackendApiError on a network failure", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameCatalogue } = await importGames();
    await expect(getGameCatalogue()).rejects.toMatchObject({
      name: "BackendApiError",
      failure: { error: { code: "NETWORK_ERROR" } },
    });
  });

  it("throws BackendApiError with an INVALID_RESPONSE code on malformed JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("{not json", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { getGameCatalogue } = await importGames();
    await expect(getGameCatalogue()).rejects.toMatchObject({
      name: "BackendApiError",
      failure: { error: { code: "INVALID_RESPONSE" } },
    });
  });

  it("throws BackendApiError on an empty 204 success response", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const { BackendApiError, getGameCatalogue } = await importGames();
    await expect(getGameCatalogue()).rejects.toBeInstanceOf(BackendApiError);
  });
});
