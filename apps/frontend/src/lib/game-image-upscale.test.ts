/**
 * Pure game-image upscaling policy tests — SBGC-184.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  accessCache,
  buildCacheKey,
  decideEnhancement,
  isEligibleForUpscale,
  isEligibleForUpscaleByDensity,
  isImageUpscalingEnabled,
  MAX_ENHANCED_CACHE_BYTES,
  MAX_ENHANCED_GAME_IMAGES,
  planCacheEvictions,
  QUALITY_HEADROOM,
  revealMode,
  shouldRunInference,
  transitionMode,
  withTimeout,
  type LruCacheEntry,
  type SizedCacheEntry,
  upscaleDimensions,
} from "./game-image-upscale";

describe("isEligibleForUpscale (width rule)", () => {
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

describe("isEligibleForUpscaleByDensity (capsule rule)", () => {
  it("flags a source that fails the density target", () => {
    // 300x450 source rendered at 250x375 CSS on a 2x display needs
    // 250*2*1.25 = 625 wide and 375*2*1.25 = 937.5 tall — undersampled.
    expect(isEligibleForUpscaleByDensity(300, 450, 250, 375, 2)).toBe(true);
  });

  it("skips a source that meets the density target", () => {
    // 800x1200 source rendered at 250x375 on a 2x display: the target is
    // 625x937.5, so the source clears it on both axes.
    expect(isEligibleForUpscaleByDensity(800, 1200, 250, 375, 2)).toBe(false);
  });

  it("higher DPR can make an adequate source insufficient", () => {
    // 600x900 source: adequate at DPR 1.5 (target 469x703) but insufficient at
    // DPR 3 (target 938x1406).
    expect(isEligibleForUpscaleByDensity(600, 900, 250, 375, 1.5)).toBe(false);
    expect(isEligibleForUpscaleByDensity(600, 900, 250, 375, 3)).toBe(true);
  });

  it("aspect-ratio difference alone does not trigger", () => {
    // A square source with plenty of pixels on both axes is not undersampled
    // merely because the rendered box is a different aspect ratio.
    expect(isEligibleForUpscaleByDensity(1000, 1000, 250, 375, 2)).toBe(false);
  });

  it("treats invalid inputs as not eligible", () => {
    expect(isEligibleForUpscaleByDensity(0, 0, 250, 375, 2)).toBe(false);
    expect(isEligibleForUpscaleByDensity(300, 450, 0, 0, 2)).toBe(false);
    expect(isEligibleForUpscaleByDensity(300, 450, 250, 375, 0)).toBe(false);
    expect(isEligibleForUpscaleByDensity(Number.NaN, 450, 250, 375, 2)).toBe(
      false,
    );
  });

  it("applies the documented 1.25 quality headroom", () => {
    // A source exactly equal to `rendered × DPR` (no headroom) is still
    // undersampled; the headroom constant is what makes it insufficient.
    const renderedWidth = 250;
    const renderedHeight = 375;
    const dpr = 2;
    expect(
      isEligibleForUpscaleByDensity(
        500,
        750,
        renderedWidth,
        renderedHeight,
        dpr,
      ),
    ).toBe(true);
    expect(QUALITY_HEADROOM).toBe(1.25);
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
  const base = {
    gameSlug: "portal-2",
    assetRole: "header" as const,
    sourceUrl: "https://cdn.example.com/header.jpg",
    modelVersion: "websr-0.0.16/cnn-2x-s-3d",
  };

  it("is content- and model-addressed", () => {
    expect(buildCacheKey(base)).toBe(
      "game:portal-2|role:header|source:https://cdn.example.com/header.jpg|model:websr-0.0.16/cnn-2x-s-3d",
    );
  });

  it("changes when the source URL changes", () => {
    const b = buildCacheKey({
      ...base,
      sourceUrl: "https://cdn.example.com/header-v2.jpg",
    });
    expect(b).not.toBe(buildCacheKey(base));
  });

  it("changes when the model version changes", () => {
    const b = buildCacheKey({
      ...base,
      modelVersion: "websr-0.0.17/cnn-2x-s-3d",
    });
    expect(b).not.toBe(buildCacheKey(base));
  });

  it("distinguishes the asset role", () => {
    const capsule = buildCacheKey({ ...base, assetRole: "library-capsule" });
    const header = buildCacheKey({ ...base, assetRole: "header" });
    expect(capsule).not.toBe(header);
    expect(capsule).toContain("role:library-capsule");
    expect(header).toContain("role:header");
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
    let entries: LruCacheEntry[] = [];
    for (let i = 0; i < 10; i += 1) {
      entries = accessCache(
        entries,
        String.fromCharCode(97 + i),
        i + 1,
      ).entries;
    }
    entries = accessCache(entries, "a", 11).entries;
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

describe("transitionMode", () => {
  it("crossfades the portrait Library Capsule", () => {
    expect(transitionMode("library-capsule")).toBe("crossfade");
  });

  it("wipes the header fallback and Manual primary image", () => {
    expect(transitionMode("header")).toBe("wipe");
    expect(transitionMode("manual-primary")).toBe("wipe");
  });
});

describe("isImageUpscalingEnabled (SBGC-202 gate)", () => {
  it("is disabled by default", () => {
    expect(isImageUpscalingEnabled(undefined)).toBe(false);
    expect(isImageUpscalingEnabled("false")).toBe(false);
    expect(isImageUpscalingEnabled(false)).toBe(false);
  });

  it("is enabled only on an explicit true value", () => {
    expect(isImageUpscalingEnabled("true")).toBe(true);
    expect(isImageUpscalingEnabled(true)).toBe(true);
  });
});

describe("shouldRunInference (environmental gating)", () => {
  it("requires intersection, visibility, and non-data-saver", () => {
    expect(
      shouldRunInference({
        isIntersecting: true,
        isVisible: true,
        saveData: false,
      }),
    ).toBe(true);
  });

  it("suppresses when the image is offscreen", () => {
    expect(
      shouldRunInference({
        isIntersecting: false,
        isVisible: true,
        saveData: false,
      }),
    ).toBe(false);
  });

  it("suppresses when the tab is backgrounded", () => {
    expect(
      shouldRunInference({
        isIntersecting: true,
        isVisible: false,
        saveData: false,
      }),
    ).toBe(false);
  });

  it("suppresses when data saver is active", () => {
    expect(
      shouldRunInference({
        isIntersecting: true,
        isVisible: true,
        saveData: true,
      }),
    ).toBe(false);
  });
});

describe("withTimeout (worker termination)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("resolves before the timeout and never calls onTimeout", async () => {
    vi.useFakeTimers();
    const onTimeout = vi.fn();
    const result = await withTimeout(Promise.resolve("done"), 5000, onTimeout);
    expect(result).toBe("done");
    expect(onTimeout).not.toHaveBeenCalled();
  });

  it("times out and invokes the termination callback", async () => {
    vi.useFakeTimers();
    const onTimeout = vi.fn();
    const never = new Promise<never>(() => {});
    const result = withTimeout(never, 5000, onTimeout);
    const rejection = result.catch((error: unknown) => error);

    await vi.advanceTimersByTimeAsync(5000);
    await rejection;

    expect(onTimeout).toHaveBeenCalledTimes(1);
  });
});

describe("planCacheEvictions (byte-bounded LRU)", () => {
  const MB = 1024 * 1024;

  it("evicts oldest entries until total bytes fit the budget", () => {
    const existing: SizedCacheEntry[] = [
      { key: "a", lastAccessedAt: 1, size: 10 * MB },
      { key: "b", lastAccessedAt: 2, size: 10 * MB },
      { key: "c", lastAccessedAt: 3, size: 10 * MB },
      { key: "d", lastAccessedAt: 4, size: 10 * MB },
    ];
    const incoming: SizedCacheEntry = {
      key: "e",
      lastAccessedAt: 5,
      size: 5 * MB,
    };

    // 45 MiB total against a 25 MiB budget: evict a (10) then b (10) → 25 MiB.
    const evicted = planCacheEvictions(
      existing,
      incoming,
      MAX_ENHANCED_GAME_IMAGES,
      MAX_ENHANCED_CACHE_BYTES,
    );
    expect(evicted).toEqual(["a", "b"]);
  });

  it("evicts a single oversized entry", () => {
    const incoming: SizedCacheEntry = {
      key: "huge",
      lastAccessedAt: 1,
      size: 30 * MB,
    };
    const evicted = planCacheEvictions(
      [],
      incoming,
      MAX_ENHANCED_GAME_IMAGES,
      MAX_ENHANCED_CACHE_BYTES,
    );
    expect(evicted).toContain("huge");
  });

  it("respects the entry-count cap alongside the byte budget", () => {
    const existing: SizedCacheEntry[] = Array.from({ length: 10 }, (_, i) => ({
      key: `k${i}`,
      lastAccessedAt: i + 1,
      size: 1 * MB,
    }));
    const incoming: SizedCacheEntry = {
      key: "new",
      lastAccessedAt: 11,
      size: 1 * MB,
    };
    const evicted = planCacheEvictions(
      existing,
      incoming,
      MAX_ENHANCED_GAME_IMAGES,
      MAX_ENHANCED_CACHE_BYTES,
    );
    expect(evicted).toEqual(["k0"]);
  });
});
