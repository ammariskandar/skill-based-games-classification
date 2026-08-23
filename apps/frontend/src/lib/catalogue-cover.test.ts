/**
 * Catalogue cover-state model tests — SBGC-77 density/cover correction.
 *
 * Pure logic only: initial state from Capsule URL presence, settled-image
 * resolution (load/error/cached), stable coverless partitioning, and
 * requestAnimationFrame batching. No real image requests; no jsdom required.
 */

import { describe, expect, it, vi } from "vitest";

import {
  createReorderScheduler,
  initialCoverState,
  isCoverless,
  partitionCoverless,
  resolveCoverStateFromImage,
  type CoverCard,
  type CoverState,
} from "./catalogue-cover";

function card(index: number, state: CoverState): CoverCard<number> {
  return { index, state, value: index };
}

describe("initialCoverState", () => {
  it("marks a card with no Capsule URL as coverless immediately", () => {
    expect(initialCoverState(false)).toBe("no-cover");
  });

  it("marks a card with a Capsule URL as unknown", () => {
    expect(initialCoverState(true)).toBe("unknown");
  });
});

describe("resolveCoverStateFromImage", () => {
  it("returns null while an image is still loading", () => {
    expect(
      resolveCoverStateFromImage({ complete: false, naturalWidth: 0 }),
    ).toBeNull();
  });

  it("resolves a loaded image to has-cover", () => {
    expect(
      resolveCoverStateFromImage({ complete: true, naturalWidth: 600 }),
    ).toBe("has-cover");
  });

  it("resolves a failed image to no-cover", () => {
    expect(
      resolveCoverStateFromImage({ complete: true, naturalWidth: 0 }),
    ).toBe("no-cover");
  });

  it("treats a cached successful image (complete + width) as has-cover", () => {
    expect(
      resolveCoverStateFromImage({ complete: true, naturalWidth: 900 }),
    ).toBe("has-cover");
  });

  it("treats a cached failed image (complete + zero width) as no-cover", () => {
    expect(
      resolveCoverStateFromImage({ complete: true, naturalWidth: 0 }),
    ).toBe("no-cover");
  });
});

describe("isCoverless", () => {
  it("is true only for no-cover", () => {
    expect(isCoverless("no-cover")).toBe(true);
    expect(isCoverless("unknown")).toBe(false);
    expect(isCoverless("has-cover")).toBe(false);
  });
});

describe("partitionCoverless", () => {
  it("keeps working/unknown cards in API order and moves confirmed coverless to the end", () => {
    // API order: A B C D E
    // A has-cover, B no-cover, C unknown, D no-cover, E has-cover
    const cards = [
      card(0, "has-cover"),
      card(1, "no-cover"),
      card(2, "unknown"),
      card(3, "no-cover"),
      card(4, "has-cover"),
    ];

    const result = partitionCoverless(cards).map((c) => c.index);

    // Working/unknown (A C E) first, coverless (B D) last, each in API order.
    expect(result).toEqual([0, 2, 4, 1, 3]);
  });

  it("re-partitions when a previously-unknown card later becomes coverless", () => {
    // A has-cover, B no-cover, C no-cover, D no-cover, E has-cover
    const cards = [
      card(0, "has-cover"),
      card(1, "no-cover"),
      card(2, "no-cover"),
      card(3, "no-cover"),
      card(4, "has-cover"),
    ];

    const result = partitionCoverless(cards).map((c) => c.index);

    expect(result).toEqual([0, 4, 1, 2, 3]);
  });

  it("does not treat unknown cards as broken", () => {
    const cards = [
      card(0, "unknown"),
      card(1, "unknown"),
      card(2, "has-cover"),
    ];
    expect(partitionCoverless(cards).map((c) => c.index)).toEqual([0, 1, 2]);
  });

  it("keeps API order stable within each group even when input order is scrambled", () => {
    const cards = [
      card(4, "has-cover"),
      card(1, "no-cover"),
      card(0, "has-cover"),
      card(3, "no-cover"),
    ];
    expect(partitionCoverless(cards).map((c) => c.index)).toEqual([0, 4, 1, 3]);
  });

  it("returns an empty array for no cards", () => {
    expect(partitionCoverless([])).toEqual([]);
  });
});

describe("createReorderScheduler", () => {
  it("coalesces multiple schedules in one frame into a single reorder", () => {
    const onReorder = vi.fn();
    const pending: Array<() => void> = [];
    const raf = vi.fn((cb: () => void) => {
      pending.push(cb);
      return pending.length;
    });

    const scheduler = createReorderScheduler(onReorder, raf);

    scheduler.schedule();
    scheduler.schedule();
    scheduler.schedule();

    // Nothing runs until the frame callback fires.
    expect(onReorder).not.toHaveBeenCalled();
    expect(pending).toHaveLength(1);

    pending[0]();
    expect(onReorder).toHaveBeenCalledTimes(1);
  });

  it("allows a new schedule after the previous frame has fired", () => {
    const onReorder = vi.fn();
    const pending: Array<() => void> = [];
    const raf = vi.fn((cb: () => void) => {
      pending.push(cb);
      return pending.length;
    });

    const scheduler = createReorderScheduler(onReorder, raf);

    scheduler.schedule();
    pending[0]();
    expect(onReorder).toHaveBeenCalledTimes(1);

    scheduler.schedule();
    expect(pending).toHaveLength(2);
    pending[1]();
    expect(onReorder).toHaveBeenCalledTimes(2);
  });
});
