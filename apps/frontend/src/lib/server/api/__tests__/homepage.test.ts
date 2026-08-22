/**
 * Behavioural tests for the homepage carousel API boundary (SBGC-189).
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

const CARDS = {
  games: [
    {
      slug: "hades",
      name: "Hades",
      library_capsule_url: "https://example.com/hades-capsule.jpg",
    },
    {
      slug: "elden-ring",
      name: "Elden Ring",
      library_capsule_url: "https://example.com/er-capsule.jpg",
    },
  ],
};

describe("getHomepageCarousel", () => {
  beforeEach(() => {
    setEnv("http://backend.test");
  });

  it("returns the parsed card list on a 200 response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(CARDS));
    vi.stubGlobal("fetch", fetchMock);

    const { getHomepageCarousel } = await importGames();
    const games = await getHomepageCarousel();

    expect(games).toHaveLength(2);
    expect(games[0].slug).toBe("hades");
    expect(games[0].name).toBe("Hades");
    expect(games[0].library_capsule_url).toBe(
      "https://example.com/hades-capsule.jpg",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("calls the homepage endpoint path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(CARDS));
    vi.stubGlobal("fetch", fetchMock);

    const { getHomepageCarousel } = await importGames();
    await getHomepageCarousel();

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("http://backend.test/api/v1/games/homepage");
  });

  it("throws BackendApiError on a Django 500", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ error: { code: "INTERNAL_SERVER_ERROR" } }, 500),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { BackendApiError, getHomepageCarousel } = await importGames();
    await expect(getHomepageCarousel()).rejects.toBeInstanceOf(BackendApiError);
  });

  it("throws BackendApiError on a network failure", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    vi.stubGlobal("fetch", fetchMock);

    const { getHomepageCarousel } = await importGames();
    await expect(getHomepageCarousel()).rejects.toMatchObject({
      name: "BackendApiError",
    });
  });
});
