/**
 * Compact public Game search-index loader — SBGC-78.
 *
 * Client-only.  A single shared loader backs both low-priority background
 * preload on discovery pages and immediate on-open loading elsewhere, with:
 *
 * - a memory cache (instant on repeat calls);
 * - a versioned `sessionStorage` cache (survives same-tab navigations);
 * - a shared in-flight Promise (no duplicate network requests);
 * - graceful degradation (storage/network failures never break Search).
 *
 * The autocomplete index is a progressive enhancement: form submission always
 * navigates to `/catalogue?q=...` and never depends on this loader.
 */

import type { GameSearchIndexItem } from "./server/api/games";

/** Versioned sessionStorage key (JSON only — no image blobs). */
export const SEARCH_INDEX_CACHE_KEY = "mygamedna:game-search-index:v1";
export const SEARCH_INDEX_VERSION = 1;
/** Reasonable freshness window; catalogue search remains authoritative. */
export const SEARCH_INDEX_TTL_MS = 15 * 60 * 1000;

/** Minimal storage surface satisfied by `sessionStorage`. */
export interface SearchIndexStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** Persisted cache envelope. */
export interface StoredSearchIndex {
  version: number;
  loadedAt: number;
  games: GameSearchIndexItem[];
}

/**
 * Whether a persisted value is a valid, non-expired index for `now`.
 * Malformed JSON is rejected by the caller; this only checks shape + freshness.
 */
export function isCacheValid(
  value: unknown,
  now: number,
  version = SEARCH_INDEX_VERSION,
  ttlMs = SEARCH_INDEX_TTL_MS,
): value is StoredSearchIndex {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<StoredSearchIndex>;
  return (
    candidate.version === version &&
    typeof candidate.loadedAt === "number" &&
    Array.isArray(candidate.games) &&
    now - candidate.loadedAt <= ttlMs
  );
}

export interface SearchIndexLoaderDeps {
  fetcher: () => Promise<GameSearchIndexItem[]>;
  storage?: SearchIndexStorage | null;
  now?: () => number;
  key?: string;
  version?: number;
  ttlMs?: number;
}

export interface SearchIndexLoader {
  load(): Promise<GameSearchIndexItem[]>;
  /** Clear memory and in-flight state (used in tests). */
  reset(): void;
}

/**
 * Build a search-index loader.  Dependency injection keeps the cache/race
 * behaviour unit-testable without a real network or `sessionStorage`.
 */
export function createSearchIndexLoader(
  deps: SearchIndexLoaderDeps,
): SearchIndexLoader {
  const {
    fetcher,
    storage = null,
    now = () => Date.now(),
    key = SEARCH_INDEX_CACHE_KEY,
    version = SEARCH_INDEX_VERSION,
    ttlMs = SEARCH_INDEX_TTL_MS,
  } = deps;

  let memory: GameSearchIndexItem[] | null = null;
  let inFlight: Promise<GameSearchIndexItem[]> | null = null;

  function readCache(): GameSearchIndexItem[] | null {
    if (!storage) return null;
    try {
      const raw = storage.getItem(key);
      if (!raw) return null;
      const parsed: unknown = JSON.parse(raw);
      return isCacheValid(parsed, now(), version, ttlMs) ? parsed.games : null;
    } catch {
      return null;
    }
  }

  function writeCache(games: GameSearchIndexItem[]): void {
    if (!storage) return;
    try {
      storage.setItem(key, JSON.stringify({ version, loadedAt: now(), games }));
    } catch {
      // Storage unavailable/quota exceeded — memory + network still work.
    }
  }

  async function load(): Promise<GameSearchIndexItem[]> {
    if (memory) return memory;

    const cached = readCache();
    if (cached) {
      memory = cached;
      return memory;
    }

    if (inFlight) return inFlight;

    inFlight = (async () => {
      const games = await fetcher();
      memory = games;
      writeCache(games);
      return games;
    })().finally(() => {
      inFlight = null;
    });

    return inFlight;
  }

  return {
    load,
    reset() {
      memory = null;
      inFlight = null;
    },
  };
}

/** Schedule a low-priority background task without blocking LCP. */
export function scheduleIdle(callback: () => void): void {
  if (
    "requestIdleCallback" in globalThis &&
    typeof globalThis.requestIdleCallback === "function"
  ) {
    globalThis.requestIdleCallback(() => callback(), { timeout: 2000 });
  } else {
    setTimeout(callback, 0);
  }
}

async function fetchSearchIndex(): Promise<GameSearchIndexItem[]> {
  const response = await fetch("/api/search-index", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Search index request failed: ${response.status}`);
  }
  const data = (await response.json()) as { games?: GameSearchIndexItem[] };
  if (!Array.isArray(data.games)) {
    throw new Error("Search index response missing games");
  }
  return data.games;
}

function getSessionStorage(): SearchIndexStorage | null {
  try {
    const storage = globalThis.sessionStorage;
    if (!storage) return null;
    // Probe access: some browsers throw when storage is unavailable.
    storage.getItem(SEARCH_INDEX_CACHE_KEY);
    return storage;
  } catch {
    return null;
  }
}

const singleton = createSearchIndexLoader({
  fetcher: fetchSearchIndex,
  storage: getSessionStorage(),
});

/** Shared entry point for background preload and explicit Search open. */
export function loadGameSearchIndex(): Promise<GameSearchIndexItem[]> {
  return singleton.load();
}
