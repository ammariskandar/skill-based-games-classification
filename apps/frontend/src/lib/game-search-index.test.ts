/**
 * Search-index loader / cache tests — SBGC-78.
 */

import { describe, expect, it, vi } from "vitest";

import {
  createSearchIndexLoader,
  fetchSearchIndex,
  isCacheValid,
  SEARCH_INDEX_TIMEOUT_MS,
  SEARCH_INDEX_TTL_MS,
  SEARCH_INDEX_VERSION,
  type SearchIndexStorage,
} from "./game-search-index";
import type { GameSearchIndexItem } from "./server/api/games";

const GAMES: GameSearchIndexItem[] = [
  { slug: "hades", name: "Hades", capsule_url: null, image_url: null },
];

function memoryStorage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  const storage: SearchIndexStorage & { map: Map<string, string> } = {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => {
      map.set(key, value);
    },
    map,
  };
  return storage;
}

describe("isCacheValid", () => {
  it("accepts a valid, fresh cache", () => {
    expect(
      isCacheValid(
        { version: 1, loadedAt: 1000, games: [] },
        1000,
        SEARCH_INDEX_VERSION,
        SEARCH_INDEX_TTL_MS,
      ),
    ).toBe(true);
  });

  it("rejects a wrong version", () => {
    expect(
      isCacheValid(
        { version: 2, loadedAt: 1000, games: [] },
        1000,
        SEARCH_INDEX_VERSION,
        SEARCH_INDEX_TTL_MS,
      ),
    ).toBe(false);
  });

  it("rejects a malformed shape", () => {
    expect(isCacheValid(null, 1000)).toBe(false);
    expect(isCacheValid("nope", 1000)).toBe(false);
    expect(isCacheValid({ version: 1 }, 1000)).toBe(false);
    expect(isCacheValid({ version: 1, loadedAt: 1, games: "x" }, 1000)).toBe(
      false,
    );
  });

  it("rejects an expired cache", () => {
    expect(
      isCacheValid(
        { version: 1, loadedAt: 0, games: [] },
        1000 + SEARCH_INDEX_TTL_MS + 1,
        SEARCH_INDEX_VERSION,
        SEARCH_INDEX_TTL_MS,
      ),
    ).toBe(false);
  });
});

describe("createSearchIndexLoader", () => {
  it("fetches over the network on a cold cache", async () => {
    const fetcher = vi.fn().mockResolvedValue(GAMES);
    const loader = createSearchIndexLoader({ fetcher });

    await expect(loader.load()).resolves.toEqual(GAMES);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("serves the memory cache on subsequent calls", async () => {
    const fetcher = vi.fn().mockResolvedValue(GAMES);
    const loader = createSearchIndexLoader({ fetcher });

    await loader.load();
    await loader.load();

    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("hydrates from a valid session cache without network", async () => {
    const storage = memoryStorage({
      "mygamedna:game-search-index:v1": JSON.stringify({
        version: 1,
        loadedAt: Date.now(),
        games: GAMES,
      }),
    });
    const fetcher = vi.fn().mockResolvedValue(GAMES);
    const loader = createSearchIndexLoader({ fetcher, storage });

    await expect(loader.load()).resolves.toEqual(GAMES);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("ignores a malformed session cache and fetches", async () => {
    const storage = memoryStorage({
      "mygamedna:game-search-index:v1": "{not json",
    });
    const fetcher = vi.fn().mockResolvedValue(GAMES);
    const loader = createSearchIndexLoader({ fetcher, storage });

    await expect(loader.load()).resolves.toEqual(GAMES);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("ignores a wrong-version session cache and fetches", async () => {
    const storage = memoryStorage({
      "mygamedna:game-search-index:v1": JSON.stringify({
        version: 99,
        loadedAt: Date.now(),
        games: GAMES,
      }),
    });
    const fetcher = vi.fn().mockResolvedValue(GAMES);
    const loader = createSearchIndexLoader({ fetcher, storage });

    await expect(loader.load()).resolves.toEqual(GAMES);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("ignores an expired session cache and fetches", async () => {
    const now = 1_000_000;
    const storage = memoryStorage({
      "mygamedna:game-search-index:v1": JSON.stringify({
        version: 1,
        loadedAt: now - SEARCH_INDEX_TTL_MS - 1,
        games: GAMES,
      }),
    });
    const fetcher = vi.fn().mockResolvedValue(GAMES);
    const loader = createSearchIndexLoader({
      fetcher,
      storage,
      now: () => now,
    });

    await expect(loader.load()).resolves.toEqual(GAMES);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("reuses one in-flight request across concurrent callers", async () => {
    let resolveFetcher!: (games: GameSearchIndexItem[]) => void;
    const fetcher = vi.fn(
      () =>
        new Promise<GameSearchIndexItem[]>((resolve) => {
          resolveFetcher = resolve;
        }),
    );
    const loader = createSearchIndexLoader({ fetcher });

    const first = loader.load();
    const second = loader.load();

    resolveFetcher(GAMES);

    await expect(first).resolves.toEqual(GAMES);
    await expect(second).resolves.toEqual(GAMES);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("survives a throwing sessionStorage (falls back to network)", async () => {
    const throwingStorage: SearchIndexStorage = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
    };
    const fetcher = vi.fn().mockResolvedValue(GAMES);
    const loader = createSearchIndexLoader({
      fetcher,
      storage: throwingStorage,
    });

    await expect(loader.load()).resolves.toEqual(GAMES);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("propagates a network failure", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("network"));
    const loader = createSearchIndexLoader({ fetcher });

    await expect(loader.load()).rejects.toThrow("network");
  });

  it("writes a fetched index to storage", async () => {
    const storage = memoryStorage();
    const fetcher = vi.fn().mockResolvedValue(GAMES);
    const loader = createSearchIndexLoader({ fetcher, storage });

    await loader.load();

    const raw = storage.map.get("mygamedna:game-search-index:v1");
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw as string);
    expect(parsed.version).toBe(1);
    expect(parsed.games).toEqual(GAMES);
  });
});

describe("fetchSearchIndex — SBGC-102 timeout bound", () => {
  it("aborts a hung request after the timeout budget", async () => {
    vi.useFakeTimers();
    const abortSpy = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () => {
              abortSpy();
              reject(new Error("Search index request aborted"));
            });
          }),
      ),
    );

    let failure: unknown;
    try {
      const pending = fetchSearchIndex().catch((error: unknown) => {
        failure = error;
      });
      await vi.advanceTimersByTimeAsync(SEARCH_INDEX_TIMEOUT_MS);
      await pending;

      expect(abortSpy).toHaveBeenCalledTimes(1);
      expect(failure).toBeInstanceOf(Error);
      expect(String((failure as Error).message)).toContain("aborted");
    } finally {
      vi.useRealTimers();
      vi.unstubAllGlobals();
    }
  });

  it("clears the timeout when the response arrives in time", async () => {
    vi.useFakeTimers();
    const response = {
      ok: true,
      json: async () => ({ games: [] }),
    } as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    try {
      await expect(fetchSearchIndex()).resolves.toEqual([]);
      // The fetch settled, so the abort timer must have been cleared.
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
      vi.unstubAllGlobals();
    }
  });

  it("throws for a non-OK response", async () => {
    const response = { ok: false, status: 503 } as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    try {
      await expect(fetchSearchIndex()).rejects.toThrow("503");
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
