/**
 * Behavioural tests for the user-profile API boundary (SBGC-221).
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

async function importUsers() {
  vi.resetModules();
  return import("../users");
}

const PROFILE = {
  username: "thenamesammaris",
  first_name: "",
  last_name: "",
  bio: "A sample bio",
  avatar_key: "anime_male_4",
  border_type: "PRESET",
  border_preset_id: 1,
  border_color: "",
  is_steam_linked: true,
  steam_profile_url: "https://steamcommunity.com/id/thenamesammaris",
  top_games: [],
  dna_scores: null,
  is_viewer_owner: false,
};

describe("getUserProfile", () => {
  beforeEach(() => {
    setEnv("https://backend.test");
  });

  it("returns the parsed DTO on a 200 response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(PROFILE)));

    const { getUserProfile } = await importUsers();
    const profile = await getUserProfile("thenamesammaris");

    expect(profile.username).toBe("thenamesammaris");
    expect(profile.is_steam_linked).toBe(true);
    expect(profile.avatar_key).toBe("anime_male_4");
  });

  it("forwards the session cookie when provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(PROFILE));
    vi.stubGlobal("fetch", fetchMock);

    const { getUserProfile } = await importUsers();
    await getUserProfile("thenamesammaris", { sessionId: "abc123" });

    const init = fetchMock.mock.calls[0][1];
    expect(init.headers.get("Cookie")).toBe("sessionid=abc123");
  });

  it("throws UserNotFoundError on a 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "NOT_FOUND",
              message: "User not found.",
              details: [],
            },
          },
          404,
        ),
      ),
    );

    const { getUserProfile, UserNotFoundError } = await importUsers();
    await expect(getUserProfile("nope")).rejects.toBeInstanceOf(
      UserNotFoundError,
    );
  });

  it("throws BackendApiError on a 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "SERVICE_UNAVAILABLE",
              message: "boom",
              details: [],
            },
          },
          500,
        ),
      ),
    );

    const { getUserProfile } = await importUsers();
    await expect(getUserProfile("thenamesammaris")).rejects.toThrow(/boom/);
  });
});
