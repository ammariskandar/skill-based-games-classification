/**
 * Comprehensive frontend failure-path matrix — SBGC-103.
 *
 * Final audit + matrix suite for the SBGC-15 epic.  Pins, at the adapter
 * boundary (`lib/server/api/games.ts`), that:
 *
 * - structured `{ error: { code, message, details } }` envelopes are parsed
 *   and surfaced through `BackendApiError.apiError` (with `details` preserved);
 * - non-JSON gateway/HTML failures map to the status-aware fallback codes;
 * - the route error boundaries throw the typed `GameNotFoundError` (404
 *   rewrite) and `BackendApiError` (service-disruption card) exceptions.
 *
 * Every test stubs `globalThis.fetch` — no real network requests.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BackendApiError } from "../games";
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

function htmlResponse(status: number): Response {
  return new Response("<html><body>gateway error</body></html>", {
    status,
    headers: { "Content-Type": "text/html" },
  });
}

function emptyResponse(status: number): Response {
  return new Response("", { status });
}

function envelope(code: string, details: unknown[] = []) {
  return { error: { code, message: `${code} message`, details } };
}

async function importGames() {
  vi.resetModules();
  return import("../games");
}

async function capture<T>(promise: Promise<T>): Promise<Error> {
  try {
    await promise;
  } catch (error) {
    return error as Error;
  }
  throw new Error("Expected promise to reject");
}

function failureOf(error: Error): ApiFailure | undefined {
  return (error as { failure?: ApiFailure }).failure;
}

describe("envelope parsing & typing", () => {
  beforeEach(() => setEnv("https://backend.test"));

  it("resolves a VALIDATION_ERROR envelope and preserves details", async () => {
    const details = [
      {
        location: ["query", "page"],
        message: "Input should be greater than or equal to 1",
        type: "greater_than_equal",
      },
    ];
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(envelope("VALIDATION_ERROR", details), 422),
        ),
    );

    const { BackendApiError, getGameCatalogue } = await importGames();
    const error = await capture(getGameCatalogue({}));

    expect(error).toBeInstanceOf(BackendApiError);
    const apiError = (error as BackendApiError).apiError;
    expect(apiError?.code).toBe("VALIDATION_ERROR");
    expect(apiError?.details).toEqual(details);
  });

  it("resolves a RATE_LIMITED envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(envelope("RATE_LIMITED"), 429)),
    );

    const { BackendApiError, getGameRankings } = await importGames();
    const error = await capture(getGameRankings({}));

    expect(error).toBeInstanceOf(BackendApiError);
    expect((error as BackendApiError).apiError?.code).toBe("RATE_LIMITED");
  });

  it("resolves a SERVICE_UNAVAILABLE envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(jsonResponse(envelope("SERVICE_UNAVAILABLE"), 503)),
    );

    const { BackendApiError, getGameCatalogue } = await importGames();
    const error = await capture(getGameCatalogue({}));

    expect(error).toBeInstanceOf(BackendApiError);
    expect((error as BackendApiError).apiError?.code).toBe(
      "SERVICE_UNAVAILABLE",
    );
  });

  it("resolves an INTERNAL_SERVER_ERROR envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(envelope("INTERNAL_SERVER_ERROR"), 500),
        ),
    );

    const { BackendApiError, getGameDetail } = await importGames();
    const error = await capture(getGameDetail("portal-2"));

    expect(error).toBeInstanceOf(BackendApiError);
    expect((error as BackendApiError).apiError?.code).toBe(
      "INTERNAL_SERVER_ERROR",
    );
  });

  it("resolves a GAME_NOT_FOUND envelope through the 404 boundary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(envelope("GAME_NOT_FOUND"), 404)),
    );

    const { GameNotFoundError, getGameDetail } = await importGames();
    const error = await capture(getGameDetail("missing"));

    expect(error).toBeInstanceOf(GameNotFoundError);
    expect((error as { slug?: string }).slug).toBe("missing");
  });
});

describe("reverse proxy & HTML fallback mapping", () => {
  beforeEach(() => setEnv("https://backend.test"));

  const fallbackCases: Array<[number, string]> = [
    [404, "NOT_FOUND"],
    [422, "VALIDATION_ERROR"],
    [429, "RATE_LIMITED"],
    [500, "SERVICE_UNAVAILABLE"],
    [502, "SERVICE_UNAVAILABLE"],
    [503, "SERVICE_UNAVAILABLE"],
    [504, "SERVICE_UNAVAILABLE"],
  ];

  for (const [status, code] of fallbackCases) {
    it(`maps an HTML ${status} body to ${code}`, async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(htmlResponse(status)));

      const { BackendApiError, getGameCatalogue } = await importGames();
      const error = await capture(getGameCatalogue({}));

      expect(error).toBeInstanceOf(BackendApiError);
      const failure = failureOf(error);
      expect(failure?.status).toBe(status);
      expect(failure?.error.code).toBe(code);
      expect((error as BackendApiError).apiError).toBeUndefined();
    });
  }

  it("maps an empty (0-byte) 5xx body to a status-aware fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(emptyResponse(500)));

    const { BackendApiError, getGameCatalogue } = await importGames();
    const error = await capture(getGameCatalogue({}));

    expect(error).toBeInstanceOf(BackendApiError);
    const failure = failureOf(error);
    expect(failure?.status).toBe(500);
    expect(failure?.error.code).toBe("SERVICE_UNAVAILABLE");
    expect(failure?.error.message).toBe("Server returned 500");
  });
});

describe("route error boundary contracts", () => {
  beforeEach(() => setEnv("https://backend.test"));

  it("getGameDetail throws GameNotFoundError on 404 (404 rewrite)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(envelope("GAME_NOT_FOUND"), 404)),
    );

    const { GameNotFoundError, getGameDetail } = await importGames();
    const error = await capture(getGameDetail("missing"));

    expect(error).toBeInstanceOf(GameNotFoundError);
  });

  it("getGameDetail throws BackendApiError with SERVICE_UNAVAILABLE on 503", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(htmlResponse(503)));

    const { BackendApiError, getGameDetail } = await importGames();
    const error = await capture(getGameDetail("portal-2"));

    expect(error).toBeInstanceOf(BackendApiError);
    expect(failureOf(error)?.error.code).toBe("SERVICE_UNAVAILABLE");
  });

  it("getGameCatalogue throws BackendApiError on an upstream 5xx", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(htmlResponse(503)));

    const { BackendApiError, getGameCatalogue } = await importGames();
    const error = await capture(getGameCatalogue({}));

    expect(error).toBeInstanceOf(BackendApiError);
    expect(failureOf(error)?.error.code).toBe("SERVICE_UNAVAILABLE");
  });

  it("getGameRankings throws BackendApiError on an upstream 5xx", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(htmlResponse(500)));

    const { BackendApiError, getGameRankings } = await importGames();
    const error = await capture(getGameRankings({}));

    expect(error).toBeInstanceOf(BackendApiError);
    expect(failureOf(error)?.error.code).toBe("SERVICE_UNAVAILABLE");
  });
});
