/**
 * Auth-status cache tests — SBGC-217 follow-up.
 *
 * Locks the `sessionStorage` cache contract shared by the navbar auth island
 * and the login page: instant paint across navigations, malformed-payload
 * rejection, and graceful degradation when storage is unavailable.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AUTH_STATUS_CACHE_KEY,
  clearCachedAuthStatus,
  readCachedAuthStatus,
  writeCachedAuthStatus,
} from "./auth-status";

function fakeStorage(initial: Record<string, string> = {}) {
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

afterEach(() => vi.unstubAllGlobals());

describe("auth-status cache", () => {
  it("returns null when storage is empty", () => {
    vi.stubGlobal("sessionStorage", fakeStorage());
    expect(readCachedAuthStatus()).toBeNull();
  });

  it("round-trips a written status", () => {
    const storage = fakeStorage();
    vi.stubGlobal("sessionStorage", storage);

    writeCachedAuthStatus({ authenticated: true, username: "ammaris" });
    expect(readCachedAuthStatus()).toEqual({
      authenticated: true,
      username: "ammaris",
    });
    expect(storage.getItem(AUTH_STATUS_CACHE_KEY)).toContain("ammaris");
  });

  it("stores an authenticated-false state", () => {
    vi.stubGlobal("sessionStorage", fakeStorage());

    writeCachedAuthStatus({ authenticated: false, username: null });
    expect(readCachedAuthStatus()).toEqual({
      authenticated: false,
      username: null,
    });
  });

  it("returns null for unparseable payloads", () => {
    vi.stubGlobal(
      "sessionStorage",
      fakeStorage({ [AUTH_STATUS_CACHE_KEY]: "{not json" }),
    );
    expect(readCachedAuthStatus()).toBeNull();
  });

  it("returns null for wrong-shape payloads", () => {
    vi.stubGlobal(
      "sessionStorage",
      fakeStorage({
        [AUTH_STATUS_CACHE_KEY]: JSON.stringify({ username: "ammaris" }),
      }),
    );
    expect(readCachedAuthStatus()).toBeNull();
  });

  it("clears the stored status", () => {
    vi.stubGlobal(
      "sessionStorage",
      fakeStorage({
        [AUTH_STATUS_CACHE_KEY]: JSON.stringify({
          authenticated: true,
          username: "ammaris",
        }),
      }),
    );

    clearCachedAuthStatus();
    expect(readCachedAuthStatus()).toBeNull();
  });

  it("degrades gracefully when storage is unavailable", () => {
    vi.stubGlobal("sessionStorage", {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
      removeItem: () => {
        throw new Error("denied");
      },
    });

    expect(readCachedAuthStatus()).toBeNull();
    // None of the calls below may throw — callers fall back to the fetch.
    writeCachedAuthStatus({ authenticated: true, username: "ammaris" });
    clearCachedAuthStatus();
  });
});
