/**
 * IndexedDB cache for enhanced game images — SBGC-184.
 *
 * Browser-only. Stores binary Blob data (never localStorage/base64) and enforces
 * the 10-entry LRU policy from `game-image-upscale.ts`. Every operation degrades
 * safely (returns null / no-ops) so an unavailable or corrupt cache never breaks
 * the page.
 */

import {
  accessCache,
  MAX_ENHANCED_GAME_IMAGES,
  type AssetRole,
  type LruCacheEntry,
} from "./game-image-upscale";

const DB_NAME = "mygamedna-game-image-cache";
const DB_VERSION = 1;
const STORE_NAME = "enhanced";

export interface CachedGameImage {
  key: string;
  gameSlug: string;
  assetRole: AssetRole;
  sourceUrl: string;
  modelVersion: string;
  blob: Blob;
  createdAt: number;
  lastAccessedAt: number;
}

let dbPromise: Promise<IDBDatabase | null> | null = null;

function openDb(): Promise<IDBDatabase | null> {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve) => {
    try {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: "key" });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(null);
      request.onblocked = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
  return dbPromise;
}

function requestToPromise<T>(request: IDBRequest<T>): Promise<T | null> {
  return new Promise((resolve) => {
    request.onsuccess = () => resolve(request.result ?? null);
    request.onerror = () => resolve(null);
  });
}

async function listEntries(db: IDBDatabase): Promise<CachedGameImage[]> {
  const tx = db.transaction(STORE_NAME, "readonly");
  const request = tx.objectStore(STORE_NAME).getAll();
  const result = await requestToPromise(request);
  return Array.isArray(result) ? (result as CachedGameImage[]) : [];
}

/** Read a cached image and refresh its recency. Returns null on any failure. */
export async function getCachedImage(
  key: string,
): Promise<CachedGameImage | null> {
  const db = await openDb();
  if (!db) return null;
  try {
    const record = await requestToPromise(
      db.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).get(key),
    );
    if (!record || !(record.blob instanceof Blob)) return null;
    // Refresh recency (best-effort; failures are ignored).
    const now = Date.now();
    await requestToPromise(
      db
        .transaction(STORE_NAME, "readwrite")
        .objectStore(STORE_NAME)
        .put({ ...record, lastAccessedAt: now } as CachedGameImage),
    );
    return record as CachedGameImage;
  } catch {
    return null;
  }
}

/** Persist a cached image, evicting LRU entries to stay within capacity. */
export async function putCachedImage(record: CachedGameImage): Promise<void> {
  const db = await openDb();
  if (!db) return;
  try {
    const existing = await listEntries(db);
    const entries: LruCacheEntry[] = existing.map((e) => ({
      key: e.key,
      lastAccessedAt: e.lastAccessedAt,
    }));
    const { evicted } = accessCache(
      entries,
      record.key,
      record.lastAccessedAt,
      MAX_ENHANCED_GAME_IMAGES,
    );

    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    for (const key of evicted) store.delete(key);
    store.put(record);
  } catch {
    // Cache write failure must not affect the page.
  }
}
