/**
 * Pure game-image upscaling policy tests — SBGC-184.
 */

import { describe, expect, it } from "vitest";

import {
  accessCache,
  buildCacheKey,
  decideEnhancement,
  isEligibleForUpscale,
  MAX_ENHANCED_GAME_IMAGES,
  revealMode,
  type LruCacheEntry,
  upscaleDimensions,
} from "./game-image-upscale";

describe("isEligibleForUpscale", () => {
  it("flags a clearly low-resolution source as eligible", () => {
    expect(isEligibleForUpscale(460, 215)).toBe(true);
  });

  it("skips an adequately wide source", () => {
    expect(isEligibleForUpscale(800, 450)).toBe(false);
    expect(isEligibleForUpscale(1280, 720)).toBe(false);
  });

  it("does not trigger on aspect-ratio difference alone", () => {
    // 800 wide but short (2.33:1) — adequate width, not deficient.
    expect(isEligibleForUpscale(800, 343)).toBe(false);
  });

  it("treats zero/negative/NaN dimensions as not eligible", () => {
    expect(isEligibleForUpscale(0, 0)).toBe(false);
    expect(isEligibleForUpscale(-1, 100)).toBe(false);
    expect(isEligibleForUpscale(Number.NaN, 100)).toBe(false);
    expect(isEligibleForUpscale(460, Number.NaN)).toBe(false);
  });
});

describe("upscaleDimensions", () => {
  it("maps input dimensions to exactly 2x output", () => {
    expect(upscaleDimensions(460, 215)).toEqual({ width: 920, height: 430 });
  });

  it("is a single 2x step, never iterative >2x", () => {
    expect(upscaleDimensions(460, 215).width).toBe(920);
    expect(upscaleDimensions(460, 215).height).toBe(430);
  });
});

describe("buildCacheKey", () => {
  it("is content- and model-addressed", () => {
    const a = buildCacheKey({
      gameSlug: "portal-2",
      sourceUrl: "https://cdn.example.com/header.jpg",
      modelVersion: "websr-0.0.16/cnn-2x-s-3d",
    });
    expect(a).toBe(
      "game:portal-2|source:https://cdn.example.com/header.jpg|model:websr-0.0.16/cnn-2x-s-3d",
    );
  });

  it("changes when the source URL changes", () => {
    const a = buildCacheKey({
      gameSlug: "portal-2",
      sourceUrl: "https://cdn.example.com/header.jpg",
      modelVersion: "websr-0.0.16/cnn-2x-s-3d",
    });
    const b = buildCacheKey({
      gameSlug: "portal-2",
      sourceUrl: "https://cdn.example.com/header-v2.jpg",
      modelVersion: "websr-0.0.16/cnn-2x-s-3d",
    });
    expect(a).not.toBe(b);
  });

  it("changes when the model version changes", () => {
    const a = buildCacheKey({
      gameSlug: "portal-2",
      sourceUrl: "https://cdn.example.com/header.jpg",
      modelVersion: "websr-0.0.16/cnn-2x-s-3d",
    });
    const b = buildCacheKey({
      gameSlug: "portal-2",
      sourceUrl: "https://cdn.example.com/header.jpg",
      modelVersion: "websr-0.0.17/cnn-2x-s-3d",
    });
    expect(a).not.toBe(b);
  });
});

describe("accessCache (LRU)", () => {
  it("inserts on a miss", () => {
    const result = accessCache([], "a", 1);
    expect(result.evicted).toEqual([]);
    expect(result.entries).toEqual([{ key: "a", lastAccessedAt: 1 }]);
  });

  it("updates recency on access without duplicating", () => {
    const first = accessCache([], "a", 1);
    const second = accessCache(first.entries, "a", 2);
    expect(second.evicted).toEqual([]);
    expect(second.entries).toEqual([{ key: "a", lastAccessedAt: 2 }]);
  });

  it("evicts the least-recently-used entry past capacity", () => {
    // Fill with a..j (10 entries).
    let entries: LruCacheEntry[] = [];
    for (let i = 0; i < 10; i += 1) {
      entries = accessCache(
        entries,
        String.fromCharCode(97 + i),
        i + 1,
      ).entries;
    }
    // Touch "a" so "b" becomes the least recently used.
    entries = accessCache(entries, "a", 11).entries;
    // Insert "k" — should evict "b".
    const result = accessCache(entries, "k", 12);
    expect(result.evicted).toEqual(["b"]);
    expect(result.entries.length).toBe(MAX_ENHANCED_GAME_IMAGES);
    expect(result.entries.some((e) => e.key === "b")).toBe(false);
    expect(result.entries.some((e) => e.key === "a")).toBe(true);
    expect(result.entries.some((e) => e.key === "k")).toBe(true);
  });

  it("enforces capacity even for a single large insertion", () => {
    let entries: LruCacheEntry[] = [];
    for (let i = 0; i < 15; i += 1) {
      entries = accessCache(entries, `k${i}`, i + 1).entries;
    }
    expect(entries.length).toBe(MAX_ENHANCED_GAME_IMAGES);
  });
});

describe("decideEnhancement", () => {
  it("skips when not eligible", () => {
    expect(decideEnhancement(false, false)).toBe("not-eligible");
    expect(decideEnhancement(false, true)).toBe("not-eligible");
  });

  it("returns cache-hit when eligible and cached (avoids inference)", () => {
    expect(decideEnhancement(true, true)).toBe("cache-hit");
  });

  it("returns cache-miss when eligible and uncached", () => {
    expect(decideEnhancement(true, false)).toBe("cache-miss");
  });
});

describe("revealMode", () => {
  it("animates normally", () => {
    expect(revealMode(false)).toBe("animated");
  });

  it("swaps instantly under reduced motion", () => {
    expect(revealMode(true)).toBe("instant");
  });
});
