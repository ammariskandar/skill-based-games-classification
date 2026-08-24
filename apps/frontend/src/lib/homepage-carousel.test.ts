/**
 * Homepage carousel layout contract tests — SBGC-189.
 */

import { describe, expect, it } from "vitest";

import {
  CAROUSEL_BREAKPOINTS,
  CAROUSEL_LOOP_BUFFER,
  CAROUSEL_MAX_VISIBLE,
  carouselCloneCount,
  carouselScrollStep,
  nextCarouselIndex,
  normalizeCarouselScroll,
  previousCarouselIndex,
  visibleCardsForViewport,
  wrapCarouselIndex,
} from "./homepage-carousel";

describe("homepage carousel visible-card contract", () => {
  it("shows five cards on a desktop viewport", () => {
    expect(visibleCardsForViewport(1280)).toBe(5);
  });

  it("shows fewer cards on a tablet viewport", () => {
    expect(visibleCardsForViewport(768)).toBe(3);
  });

  it("shows two cards on a mobile viewport", () => {
    expect(visibleCardsForViewport(375)).toBe(2);
  });

  it("keeps breakpoints ordered widest-first", () => {
    const widths = CAROUSEL_BREAKPOINTS.map((tier) => tier.minWidth);
    expect(widths).toEqual([...widths].sort((a, b) => b - a));
  });

  it("caps visible cards at five for any width", () => {
    expect(visibleCardsForViewport(4000)).toBe(5);
  });
});

describe("carouselScrollStep", () => {
  it("advances by one card plus one gap", () => {
    expect(carouselScrollStep(220, 16)).toBe(236);
  });
});

describe("homepage carousel infinite-loop helpers (SBGC-191)", () => {
  it("derives the max visible tier as five cards", () => {
    expect(CAROUSEL_MAX_VISIBLE).toBe(5);
  });

  it("wraps a forward index past the end back to the start", () => {
    expect(nextCarouselIndex(9, 10)).toBe(0);
    expect(nextCarouselIndex(8, 10)).toBe(9);
  });

  it("wraps a backward index before the start back to the end", () => {
    expect(previousCarouselIndex(0, 10)).toBe(9);
    expect(previousCarouselIndex(1, 10)).toBe(0);
  });

  it("supports repeated cycles in both directions", () => {
    expect(nextCarouselIndex(nextCarouselIndex(9, 10), 10)).toBe(1);
    expect(previousCarouselIndex(previousCarouselIndex(0, 10), 10)).toBe(8);
  });

  it("does not hardcode ten into the wrap math", () => {
    expect(nextCarouselIndex(1, 2)).toBe(0);
    expect(nextCarouselIndex(0, 2)).toBe(1);
    expect(nextCarouselIndex(2, 3)).toBe(0);
    expect(previousCarouselIndex(0, 3)).toBe(2);
  });

  it("wraps raw indices modularly (negative and positive)", () => {
    expect(wrapCarouselIndex(10, 10)).toBe(0);
    expect(wrapCarouselIndex(-1, 10)).toBe(9);
    expect(wrapCarouselIndex(5, 10)).toBe(5);
    expect(wrapCarouselIndex(0, 0)).toBe(0);
  });

  it("uses a loop buffer one step wider than the max visible tier", () => {
    expect(CAROUSEL_LOOP_BUFFER).toBe(6);
  });

  it("provides enough boundary clones for the 5/3/2 visible tiers", () => {
    expect(carouselCloneCount(10)).toBe(6);
    expect(carouselCloneCount(5)).toBe(5);
    expect(carouselCloneCount(3)).toBe(3);
    expect(carouselCloneCount(2)).toBe(2);
  });

  it("grows the buffer to cover the actual visible card count", () => {
    // At a wide viewport more than 5 cards can be visible at once, so the
    // buffer must grow beyond the fixed responsive-tier default.
    expect(carouselCloneCount(10, 8)).toBe(8);
    expect(carouselCloneCount(10, 3)).toBe(6);
  });

  it("caps the buffer at the list length", () => {
    expect(carouselCloneCount(10, 20)).toBe(10);
    expect(carouselCloneCount(4, 20)).toBe(4);
  });

  it("keeps the clone count bounded for large lists", () => {
    expect(carouselCloneCount(100)).toBe(6);
    expect(carouselCloneCount(100, 8)).toBe(8);
  });

  it("does not clone for single-card or empty lists", () => {
    expect(carouselCloneCount(0)).toBe(0);
    expect(carouselCloneCount(1)).toBe(0);
  });

  it("normalizes a head-clone offset back into the canonical region", () => {
    // 10 cards, 6 clones/side, step 236 → canonical [1416, 3776).
    expect(normalizeCarouselScroll(3776, 10, 6, 236)).toBe(1416);
    expect(normalizeCarouselScroll(4000, 10, 6, 236)).toBe(1640);
  });

  it("normalizes a tail-clone offset forward into the canonical region", () => {
    expect(normalizeCarouselScroll(0, 10, 6, 236)).toBe(2360);
    expect(normalizeCarouselScroll(500, 10, 6, 236)).toBe(2860);
  });

  it("leaves a canonical offset unchanged", () => {
    expect(normalizeCarouselScroll(1416, 10, 6, 236)).toBe(1416);
    expect(normalizeCarouselScroll(2000, 10, 6, 236)).toBe(2000);
  });

  it("tolerates browser pixel rounding at the canonical-start boundary", () => {
    // `step` is fractional, so `buffer * step` is not a whole pixel and the
    // browser rounds the stored offset down. That rounded value must stay in
    // the canonical region rather than being mistaken for a tail clone.
    const step = 236.4; // 6 * 236.4 = 1418.4 → browser reads 1418
    expect(normalizeCarouselScroll(1418, 10, 6, step)).toBe(1418);
  });

  it("still wraps the head clone when the boundary is fractional", () => {
    const step = 236.4; // 16 * 236.4 = 3782.4 → browser reads 3782
    expect(normalizeCarouselScroll(3782, 10, 6, step)).toBe(1418);
  });

  it("still wraps the tail clone when the boundary is fractional", () => {
    const step = 236.4;
    // Just inside the tail-clone region (well below canonicalStart 1418.4).
    expect(normalizeCarouselScroll(1000, 10, 6, step)).toBe(3364);
  });
});
