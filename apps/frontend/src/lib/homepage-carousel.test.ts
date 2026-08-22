/**
 * Homepage carousel layout contract tests — SBGC-189.
 */

import { describe, expect, it } from "vitest";

import {
  CAROUSEL_BREAKPOINTS,
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
