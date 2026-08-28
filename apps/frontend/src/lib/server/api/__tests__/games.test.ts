/**
 * Behavioural tests for the game-detail API boundary (SBGC-72).
 *
 * Every test mocks globalThis.fetch — no real network requests are made.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiFailure } from "../types";

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
  library_hero_url: "https://example.com/library_hero.jpg",
  library_capsule_url: "https://example.com/library_600x900.jpg",
  metadata_updated_at: "2026-08-21T00:00:00Z",
};

describe("getGameDetail", () => {
  beforeEach(() => {
    setEnv("https://backend.test");
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
    expect(detail.game.library_hero_url).toBe(
      "https://example.com/library_hero.jpg",
    );
    expect(detail.game.library_capsule_url).toBe(
      "https://example.com/library_600x900.jpg",
    );
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
    expect(url).toContain("https://backend.test/api/v1/games/my%20game");
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

    const { getGameDetail } = await importGames();
    await expect(getGameDetail("portal-2")).rejects.toMatchObject({
      name: "BackendApiError",
      failure: { error: { code: "NETWORK_ERROR" } },
    });
  });

  it("throws BackendApiError with a TIMEOUT code when the transport aborts", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValue(new DOMException("Aborted", "AbortError"));
    vi.stubGlobal("fetch", fetchMock);

    const { getGameDetail } = await importGames();
    await expect(getGameDetail("portal-2")).rejects.toMatchObject({
      name: "BackendApiError",
      failure: { error: { code: "TIMEOUT" } },
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

    const { getGameDetail } = await importGames();
    await expect(getGameDetail("portal-2")).rejects.toMatchObject({
      name: "BackendApiError",
      failure: { error: { code: "INVALID_RESPONSE" } },
    });
  });

  it("throws BackendApiError on an empty 204 success response", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const { BackendApiError, getGameDetail } = await importGames();
    await expect(getGameDetail("portal-2")).rejects.toBeInstanceOf(
      BackendApiError,
    );
  });
});

describe("BackendApiError", () => {
  it("exposes the structured apiError from its failure", async () => {
    const { BackendApiError } = await importGames();
    const apiError = {
      code: "VALIDATION_ERROR",
      message: "Invalid sort",
      details: [],
    };
    const failure: ApiFailure = {
      ok: false,
      status: 422,
      error: { code: "HTTP_ERROR", message: "Invalid sort" },
      apiError,
    };

    const error = new BackendApiError("Invalid sort", failure);
    expect(error.failure).toBe(failure);
    expect(error.apiError).toEqual(apiError);
  });

  it("returns undefined apiError when there is no failure", async () => {
    const { BackendApiError } = await importGames();
    expect(new BackendApiError("boom").apiError).toBeUndefined();
  });
});

describe("adapter signal forwarding", () => {
  beforeEach(() => {
    setEnv("https://backend.test");
  });

  async function assertSignalAborts(
    invoke: (signal: AbortSignal) => Promise<unknown>,
  ): Promise<void> {
    const controller = new AbortController();
    const fetchMock = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const pending = invoke(controller.signal);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    controller.abort();

    await expect(pending).rejects.toMatchObject({
      name: "BackendApiError",
      failure: { error: { code: "ABORTED" } },
    });
  }

  it("forwards the caller signal through getGameDetail", async () => {
    const { getGameDetail } = await importGames();
    await assertSignalAborts((signal) => getGameDetail("hades", { signal }));
  });

  it("forwards the caller signal through getGameCatalogue", async () => {
    const { getGameCatalogue } = await importGames();
    await assertSignalAborts((signal) => getGameCatalogue({}, { signal }));
  });

  it("forwards the caller signal through getGameRankings", async () => {
    const { getGameRankings } = await importGames();
    await assertSignalAborts((signal) => getGameRankings({}, { signal }));
  });

  it("forwards the caller signal through getGameSearchIndex", async () => {
    const { getGameSearchIndex } = await importGames();
    await assertSignalAborts((signal) => getGameSearchIndex({ signal }));
  });
});
