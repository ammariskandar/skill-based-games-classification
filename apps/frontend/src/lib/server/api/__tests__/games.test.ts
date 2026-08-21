/**
 * Behavioural tests for the game-detail API boundary (SBGC-72).
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

const GAME = {
  id: 1,
  slug: "portal-2",
  name: "Portal 2",
  source: "steam",
  external_id: "620",
  content_type: "game",
  description: "A puzzle game.",
  release_date: null,
  developer: "Valve",
  image_url: "https://example.com/header.jpg",
  metadata_updated_at: "2026-08-21T00:00:00Z",
};

describe("getGameDetail", () => {
  beforeEach(() => {
    setEnv("http://backend.test");
  });

  it("returns the parsed DTO on a 200 response", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ game: GAME, classification: null }));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameDetail } = await importGames();
    const detail = await getGameDetail("portal-2");

    expect(detail.game.name).toBe("Portal 2");
    expect(detail.game.source).toBe("steam");
    expect(detail.classification).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("encodes the slug and calls the expected path", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ game: GAME, classification: null }));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameDetail } = await importGames();
    await getGameDetail("my game");

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("http://backend.test/api/v1/games/my%20game");
  });

  it("throws GameNotFoundError on a Django 404", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ error: { code: "GAME_NOT_FOUND" } }, 404),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { GameNotFoundError, getGameDetail } = await importGames();
    await expect(getGameDetail("nope")).rejects.toBeInstanceOf(
      GameNotFoundError,
    );
  });

  it("throws BackendApiError on a Django 500", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ error: { code: "INTERNAL_SERVER_ERROR" } }, 500),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { BackendApiError, getGameDetail } = await importGames();
    await expect(getGameDetail("portal-2")).rejects.toBeInstanceOf(
      BackendApiError,
    );
  });

  it("throws BackendApiError on a network failure", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    vi.stubGlobal("fetch", fetchMock);

    const { BackendApiError, getGameDetail } = await importGames();
    await expect(getGameDetail("portal-2")).rejects.toBeInstanceOf(
      BackendApiError,
    );
  });
});
