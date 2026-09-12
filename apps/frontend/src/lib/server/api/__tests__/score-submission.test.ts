/**
 * Behavioural tests for the manual score-submission API boundary (SBGC-225).
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

async function importScoreSubmission() {
  vi.resetModules();
  return import("../score-submission");
}

const PAYLOAD = {
  challenge: { micro: 40, mystiko: 30, macro: 30 },
  reward: { micro: 35, mystiko: 35, macro: 30 },
  aesthetic: "SENSORY",
  secondary_aesthetic: "FANTASY",
};

const CREATED = {
  id: 12,
  game_slug: "hades",
  aesthetic: "SENSORY",
  secondary_aesthetic: "FANTASY",
  is_duplicate: false,
  is_updated: false,
  is_created: true,
  submitted_at: "2026-09-11T00:00:00Z",
};

describe("submitManualScore", () => {
  beforeEach(() => {
    setEnv("https://backend.test");
  });

  it("returns the created outcome with its status and forwards the cookie", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(CREATED, 201));
    vi.stubGlobal("fetch", fetchMock);

    const { submitManualScore } = await importScoreSubmission();
    const result = await submitManualScore("hades", PAYLOAD, {
      sessionId: "abc",
    });

    expect(result.ok).toBe(true);
    expect(result.statusCode).toBe(201);
    if (result.ok) {
      expect(result.data.is_created).toBe(true);
      expect(result.data.id).toBe(12);
    }

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(
      "https://backend.test/api/v1/classifications/games/hades/submit-score",
    );
    expect(init.method).toBe("POST");
    expect(init.headers.get("Cookie")).toBe("sessionid=abc");
    expect(init.headers.get("Content-Type")).toBe("application/json");
  });

  it("returns the in-place update outcome on 200", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(
            { ...CREATED, is_created: false, is_updated: true },
            200,
          ),
        ),
    );

    const { submitManualScore } = await importScoreSubmission();
    const result = await submitManualScore("hades", PAYLOAD);

    expect(result.ok).toBe(true);
    expect(result.statusCode).toBe(200);
    if (result.ok) expect(result.data.is_updated).toBe(true);
  });

  it("surfaces a 422 validation body without throwing", async () => {
    const errorBody = {
      error: {
        code: "VALIDATION_ERROR",
        message: "Challenge scores must sum to exactly 100.",
        details: [],
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(errorBody, 422)),
    );

    const { submitManualScore } = await importScoreSubmission();
    const result = await submitManualScore("hades", PAYLOAD);

    expect(result.ok).toBe(false);
    expect(result.statusCode).toBe(422);
    expect(result.data).toEqual(errorBody);
  });

  it("propagates a transport failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("fetch failed")),
    );

    const { submitManualScore } = await importScoreSubmission();
    await expect(submitManualScore("hades", PAYLOAD)).rejects.toBeInstanceOf(
      TypeError,
    );
  });
});
