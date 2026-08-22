/**
 * Homepage carousel layout contract tests — SBGC-189.
 */

import { describe, expect, it } from "vitest";

import {
  assignCarouselEmphasis,
  CAROUSEL_BREAKPOINTS,
  carouselEmphasis,
  carouselScrollStep,
  visibleCardsForViewport,
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

describe("carouselEmphasis", () => {
  it("5 visible: center full, ±1 intermediate, ±2 darkest", () => {
    expect(carouselEmphasis(0, 5)).toBe("full");
    expect(carouselEmphasis(1, 5)).toBe("intermediate");
    expect(carouselEmphasis(2, 5)).toBe("darkest");
  });

  it("makes the center card the only full-brightness level", () => {
    expect(carouselEmphasis(0, 5)).toBe("full");
    expect(carouselEmphasis(1, 5)).not.toBe("full");
    expect(carouselEmphasis(2, 5)).not.toBe("full");
  });

  it("3 visible: center full, edge darkest", () => {
    expect(carouselEmphasis(0, 3)).toBe("full");
    expect(carouselEmphasis(1, 3)).toBe("darkest");
  });

  it("1 visible: always full", () => {
    expect(carouselEmphasis(0, 1)).toBe("full");
  });

  it("treats non-positive steps as the centered card", () => {
    expect(carouselEmphasis(-1, 5)).toBe("full");
  });
});

describe("assignCarouselEmphasis", () => {
  it("5-card symmetric window → darkest/intermediate/full/intermediate/darkest", () => {
    expect(assignCarouselEmphasis([200, 100, 0, 100, 200], 5)).toEqual([
      "darkest",
      "intermediate",
      "full",
      "intermediate",
      "darkest",
    ]);
  });

  it("produces exactly one full card in a 5-card window", () => {
    const levels = assignCarouselEmphasis([200, 100, 0, 100, 200], 5);
    expect(levels.filter((level) => level === "full")).toHaveLength(1);
  });

  it("3-card window → darkest/full/darkest", () => {
    expect(assignCarouselEmphasis([100, 0, 100], 3)).toEqual([
      "darkest",
      "full",
      "darkest",
    ]);
  });

  it("1-card window → full", () => {
    expect(assignCarouselEmphasis([0], 1)).toEqual(["full"]);
  });

  it("recomputes by distance after the window shifts, not by array index", () => {
    // The 4th card is now nearest the viewport center.
    expect(assignCarouselEmphasis([300, 200, 100, 0, 100], 5)).toEqual([
      "darkest",
      "darkest",
      "intermediate",
      "full",
      "intermediate",
    ]);
  });
});
