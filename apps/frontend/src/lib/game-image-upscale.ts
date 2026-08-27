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
 *
 * Used for the header fallback and Manual primary image.
 */
export const ELIGIBILITY_WIDTH_THRESHOLD = 800;

/**
 * Conservative quality headroom applied to the effective physical-pixel target
 * for the Library Capsule. `required = renderedCssSize × devicePixelRatio`;
 * `target = required × 1.25`. A capsule meeting or exceeding the target is not
 * enhanced. This is display-density headroom, not a native 1.25x neural model —
 * WebSR remains a 2x model internally.
 */
export const QUALITY_HEADROOM = 1.25;

/** WebSR network used (small 2x CNN). */
export const NETWORK_NAME = "anime4k/cnn-2x-s";

/**
 * Cache/model identity. Changing the WebSR package version or the weight file
 * invalidates incompatible cached entries.
 */
export const MODEL_VERSION = "websr-0.0.16/cnn-2x-s-3d";

/** Exact upscale factor — never iterate beyond this. */
export const UPSCALE_FACTOR = 2;

/** Which canonical artwork role is being enhanced. */
export type AssetRole = "library-capsule" | "header" | "manual-primary";

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

/**
 * Whether a source image is materially undersampled for how it is actually
 * rendered on screen (the Library Capsule rule).
 *
 * - `sourceWidth`/`sourceHeight` are the decoded intrinsic dimensions.
 * - `renderedCssWidth`/`renderedCssHeight` are the on-screen CSS dimensions.
 * - `devicePixelRatio` is the physical-pixel multiplier.
 *
 * A source is undersampled when it fails to meet the required physical pixels
 * plus `QUALITY_HEADROOM` on either axis. Aspect-ratio differences alone never
 * trigger this (the axes are compared independently).
 */
export function isEligibleForUpscaleByDensity(
  sourceWidth: number,
  sourceHeight: number,
  renderedCssWidth: number,
  renderedCssHeight: number,
  devicePixelRatio: number,
): boolean {
  if (!Number.isFinite(sourceWidth) || !Number.isFinite(sourceHeight)) {
    return false;
  }
  if (
    !Number.isFinite(renderedCssWidth) ||
    !Number.isFinite(renderedCssHeight)
  ) {
    return false;
  }
  if (!Number.isFinite(devicePixelRatio) || devicePixelRatio <= 0) return false;
  if (sourceWidth <= 0 || sourceHeight <= 0) return false;
  if (renderedCssWidth <= 0 || renderedCssHeight <= 0) return false;

  const targetWidth = renderedCssWidth * devicePixelRatio * QUALITY_HEADROOM;
  const targetHeight = renderedCssHeight * devicePixelRatio * QUALITY_HEADROOM;

  return sourceWidth < targetWidth || sourceHeight < targetHeight;
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
  assetRole: AssetRole;
  sourceUrl: string;
  modelVersion: string;
}

/** Stable, content-and-model-addressed cache key including the asset role. */
export function buildCacheKey(input: CacheKeyInput): string {
  return (
    `game:${input.gameSlug}|role:${input.assetRole}` +
    `|source:${input.sourceUrl}|model:${input.modelVersion}`
  );
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

export type TransitionMode = "crossfade" | "wipe";

/**
 * The portrait foreground Capsule crossfades; the full-frame header and Manual
 * images keep the top-to-bottom wipe already established in SBGC-184.
 */
export function transitionMode(assetRole: AssetRole): TransitionMode {
  return assetRole === "library-capsule" ? "crossfade" : "wipe";
}

/* ── SBGC-202: feature gate, environmental gating, byte-bounded cache ── */

/** Automatic WebSR upscaling is disabled by default and enabled only via the
 * explicit public build flag `PUBLIC_ENABLE_IMAGE_UPSCALE === "true"`. */
export function isImageUpscalingEnabled(
  raw: string | boolean | undefined,
): boolean {
  return raw === "true" || raw === true;
}

/** Total byte ceiling for cached enhanced images (25 MiB). */
export const MAX_ENHANCED_CACHE_BYTES = 25 * 1024 * 1024;

/** A cache entry carrying an estimated byte size for byte-bounded LRU. */
export interface SizedCacheEntry extends LruCacheEntry {
  size: number;
}

/**
 * Plan which cache keys to evict so the resulting store respects both the
 * entry-count cap and the byte ceiling.  Eviction is oldest-first (LRU by
 * `lastAccessedAt`).  A single entry larger than `maxBytes` is evicted.
 */
export function planCacheEvictions(
  existing: SizedCacheEntry[],
  incoming: SizedCacheEntry,
  maxEntries: number,
  maxBytes: number,
): string[] {
  const combined = [
    ...existing.filter((entry) => entry.key !== incoming.key),
    incoming,
  ].sort((a, b) => a.lastAccessedAt - b.lastAccessedAt);

  const evicted: string[] = [];
  const remaining = [...combined];

  while (remaining.length > maxEntries) {
    const removed = remaining.shift();
    if (removed) evicted.push(removed.key);
  }

  let totalBytes = remaining.reduce((sum, entry) => sum + entry.size, 0);
  while (remaining.length > 0 && totalBytes > maxBytes) {
    const removed = remaining.shift();
    if (removed) {
      evicted.push(removed.key);
      totalBytes -= removed.size;
    }
  }

  return evicted;
}

/** Environmental gates that must all pass before inference may run. */
export interface InferenceGates {
  isIntersecting: boolean;
  isVisible: boolean;
  saveData: boolean;
}

/** Inference runs only when in view, foregrounded, and not data-saver. */
export function shouldRunInference(gates: InferenceGates): boolean {
  return gates.isIntersecting && gates.isVisible && !gates.saveData;
}

/** Race a promise against a timeout.  On timeout, calls `onTimeout` (the caller
 * should terminate the worker) and rejects; on settle, clears the timer. */
export function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  onTimeout: () => void,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      onTimeout();
      reject(new Error(`timed out after ${timeoutMs}ms`));
    }, timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}
