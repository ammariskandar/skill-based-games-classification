/**
 * Score-submission store tests — SBGC-215.
 *
 * Locks the localStorage round-trip, cache-miss behaviour, graceful degradation,
 * and the temporary auth bridge (session cookie + `mock_auth_logged_in`).
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getCachedSubmission,
  isUserAuthenticated,
  saveSubmissionToCache,
  type StoredSubmission,
} from "./score-submission-store";

function fakeLocalStorage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
    removeItem: (key: string) => {
      map.delete(key);
    },
  };
}

const submission: StoredSubmission = {
  gameSlug: "hades",
  submittedAt: "2026-09-07T00:00:00.000Z",
  challenge: { micro: 40, mystiko: 30, macro: 30 },
  reward: { micro: 20, mystiko: 40, macro: 40 },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("score-submission store", () => {
  it("returns null when there is no cached submission", () => {
    vi.stubGlobal("window", { localStorage: fakeLocalStorage() });
    expect(getCachedSubmission("hades")).toBeNull();
  });

  it("round-trips a saved submission", () => {
    const storage = fakeLocalStorage();
    vi.stubGlobal("window", { localStorage: storage });

    saveSubmissionToCache(submission);
    expect(getCachedSubmission("hades")).toEqual(submission);
  });

  it("returns null for unparseable cache entries", () => {
    vi.stubGlobal("window", {
      localStorage: fakeLocalStorage({ mygamedna_submission_hades: "{nope" }),
    });
    expect(getCachedSubmission("hades")).toBeNull();
  });

  it("degrades gracefully when storage is unavailable", () => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => {
          throw new Error("denied");
        },
        setItem: () => {
          throw new Error("denied");
        },
        removeItem: () => {
          throw new Error("denied");
        },
      },
    });

    expect(getCachedSubmission("hades")).toBeNull();
    // Must not throw.
    saveSubmissionToCache(submission);
  });

  it("returns false outside the browser", () => {
    // `window` is not stubbed in this node environment.
    expect(isUserAuthenticated()).toBe(false);
    expect(getCachedSubmission("hades")).toBeNull();
  });

  it("authenticates via the mock dev flag", () => {
    vi.stubGlobal("window", {
      localStorage: fakeLocalStorage({ mock_auth_logged_in: "true" }),
    });
    vi.stubGlobal("document", { cookie: "" });

    expect(isUserAuthenticated()).toBe(true);
  });

  it("authenticates via a sessionid cookie", () => {
    vi.stubGlobal("window", { localStorage: fakeLocalStorage() });
    vi.stubGlobal("document", { cookie: "sessionid=abc123; path=/" });

    expect(isUserAuthenticated()).toBe(true);
  });

  it("reports unauthenticated with no cookie and no flag", () => {
    vi.stubGlobal("window", { localStorage: fakeLocalStorage() });
    vi.stubGlobal("document", { cookie: "" });

    expect(isUserAuthenticated()).toBe(false);
  });
});
