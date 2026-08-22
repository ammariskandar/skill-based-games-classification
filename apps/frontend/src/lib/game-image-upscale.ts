/**
 * Pure, testable game-image upscaling policy — SBGC-184.
 *
 * This module owns every deterministic decision (eligibility, output geometry,
 * cache key, LRU policy, enhancement decision, reveal mode). It is deliberately
 * free of browser APIs (IndexedDB, WebGPU, WebSR, Worker) so it runs under
 * Node/Vitest.
 */

/** Hard product limit on cached enhanced images. */
export const MAX_ENHANCED_GAME_IMAGES = 10;

/**
 * A source narrower than this width (px) is treated as materially undersampled
 * for the maximum intended Game-detail display width (~800px) and is eligible
 * for 2x enhancement. Width-only keeps the rule aspect-ratio agnostic so an
 * otherwise adequate wide-but-short image is not flagged as deficient.
 */
export const ELIGIBILITY_WIDTH_THRESHOLD = 800;

/** WebSR network used (small 2x CNN). */
export const NETWORK_NAME = "anime4k/cnn-2x-s";

/**
 * Cache/model identity. Changing the WebSR package version or the weight file
 * invalidates incompatible cached entries.
 */
export const MODEL_VERSION = "websr-0.0.16/cnn-2x-s-3d";

/** Exact upscale factor — never iterate beyond this. */
export const UPSCALE_FACTOR = 2;

export interface ImageDimensions {
  width: number;
  height: number;
}

/** Whether a decoded source image is materially undersampled and eligible. */
export function isEligibleForUpscale(width: number, height: number): boolean {
  if (!Number.isFinite(width) || !Number.isFinite(height)) return false;
  if (width <= 0 || height <= 0) return false;
  return width < ELIGIBILITY_WIDTH_THRESHOLD;
}

/** Exact 2x output dimensions, preserving aspect ratio. */
export function upscaleDimensions(
  width: number,
  height: number,
): ImageDimensions {
  return {
    width: width * UPSCALE_FACTOR,
    height: height * UPSCALE_FACTOR,
  };
}

export interface CacheKeyInput {
  gameSlug: string;
  sourceUrl: string;
  modelVersion: string;
}

/** Stable, content-and-model-addressed cache key. */
export function buildCacheKey(input: CacheKeyInput): string {
  return `game:${input.gameSlug}|source:${input.sourceUrl}|model:${input.modelVersion}`;
}

export interface LruCacheEntry {
  key: string;
  lastAccessedAt: number;
}

export interface AccessCacheResult {
  /** Entries ordered by `lastAccessedAt` ascending (oldest first). */
  entries: LruCacheEntry[];
  /** Keys evicted by this access, in eviction order. */
  evicted: string[];
}

/**
 * Record an access to `key`, updating its recency and evicting the
 * least-recently-used entries until the cache is at most `capacity`.
 *
 * `now` must be monotonically non-decreasing across calls (real timestamps or a
 * synthetic counter both work). Input entries need not be pre-sorted.
 */
export function accessCache(
  entries: LruCacheEntry[],
  key: string,
  now: number,
  capacity: number = MAX_ENHANCED_GAME_IMAGES,
): AccessCacheResult {
  const without = entries.filter((entry) => entry.key !== key);
  const next = [...without, { key, lastAccessedAt: now }];
  next.sort((a, b) => a.lastAccessedAt - b.lastAccessedAt);

  const evicted: string[] = [];
  while (next.length > capacity) {
    const removed = next.shift();
    if (removed) evicted.push(removed.key);
  }
  return { entries: next, evicted };
}

export type EnhancementDecision = "not-eligible" | "cache-hit" | "cache-miss";

/** Decide the enhancement path. A cache hit bypasses inference entirely. */
export function decideEnhancement(
  eligible: boolean,
  cached: boolean,
): EnhancementDecision {
  if (!eligible) return "not-eligible";
  if (cached) return "cache-hit";
  return "cache-miss";
}

export type RevealMode = "animated" | "instant";

/** Reduced motion swaps the enhanced image in instantly instead of animating. */
export function revealMode(prefersReducedMotion: boolean): RevealMode {
  return prefersReducedMotion ? "instant" : "animated";
}
