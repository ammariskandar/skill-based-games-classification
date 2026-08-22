/**
 * Game-image layout decision tests — SBGC-184 correction.
 */

import { describe, expect, it } from "vitest";

import {
  CAPSULE_ASPECT_RATIO,
  resolveGameImageLayout,
  VISUALIZATION_SLOT_ASPECT_RATIO,
  type GameImageLayoutInput,
} from "./game-image-layout";

const STEAM: GameImageLayoutInput = {
  src: "https://cdn.example.com/header.jpg",
  source: "steam",
  libraryHeroUrl: "https://cdn.example.com/library_hero.jpg",
  libraryCapsuleUrl: "https://cdn.example.com/library_600x900.jpg",
};

describe("resolveGameImageLayout — Steam ideal (Hero + Capsule)", () => {
  it("exposes the classification-visualization slot structure", () => {
    const layout = resolveGameImageLayout(STEAM);
    expect(layout.showVisualizationSlot).toBe(true);
    expect(layout.foregroundRole).toBe("library-capsule");
    expect(layout.foregroundContained).toBe(true);
    expect(layout.backgroundSrc).toBe(STEAM.libraryHeroUrl);
  });

  it("keeps the Capsule as the portrait foreground", () => {
    const layout = resolveGameImageLayout(STEAM);
    expect(layout.foregroundSrc).toBe(STEAM.libraryCapsuleUrl);
    expect(CAPSULE_ASPECT_RATIO).toBeLessThan(1);
  });
});

describe("visualization slot geometry contract", () => {
  it("reserves a square (1/1) slot", () => {
    expect(VISUALIZATION_SLOT_ASPECT_RATIO).toBe(1);
  });

  it("makes the slot wider than the Capsule at equal displayed height", () => {
    // Both children share the flex group's height; the square slot's width
    // equals that height while the portrait Capsule's width is 2/3 of it.
    expect(VISUALIZATION_SLOT_ASPECT_RATIO).toBeGreaterThan(
      CAPSULE_ASPECT_RATIO,
    );
  });
});

describe("resolveGameImageLayout — Manual Games", () => {
  it("renders a single full-frame operator image without a slot", () => {
    const layout = resolveGameImageLayout({
      src: "https://example.com/manual.png",
      source: "manual",
    });

    expect(layout.kind).toBe("image");
    expect(layout.foregroundRole).toBe("manual-primary");
    expect(layout.foregroundContained).toBe(false);
    expect(layout.showVisualizationSlot).toBe(false);
    expect(layout.backgroundSrc).toBe("");
  });

  it("ignores any Library asset fields on a Manual game", () => {
    const layout = resolveGameImageLayout({
      src: "https://example.com/manual.png",
      source: "manual",
      libraryHeroUrl: "https://example.com/hero.jpg",
      libraryCapsuleUrl: "https://example.com/capsule.jpg",
    });

    expect(layout.showVisualizationSlot).toBe(false);
    expect(layout.foregroundRole).toBe("manual-primary");
  });
});

describe("resolveGameImageLayout — Steam fallback ladder", () => {
  it("Hero only → Hero background + contained header foreground, no slot", () => {
    const layout = resolveGameImageLayout({
      src: "https://cdn.example.com/header.jpg",
      source: "steam",
      libraryHeroUrl: "https://cdn.example.com/hero.jpg",
      libraryCapsuleUrl: null,
    });

    expect(layout.backgroundSrc).toBe("https://cdn.example.com/hero.jpg");
    expect(layout.foregroundRole).toBe("header");
    expect(layout.foregroundContained).toBe(true);
    expect(layout.showVisualizationSlot).toBe(false);
  });

  it("Capsule only → header background + Capsule foreground, no slot", () => {
    const layout = resolveGameImageLayout({
      src: "https://cdn.example.com/header.jpg",
      source: "steam",
      libraryHeroUrl: null,
      libraryCapsuleUrl: "https://cdn.example.com/capsule.jpg",
    });

    expect(layout.backgroundSrc).toBe("https://cdn.example.com/header.jpg");
    expect(layout.foregroundRole).toBe("library-capsule");
    expect(layout.foregroundContained).toBe(true);
    expect(layout.showVisualizationSlot).toBe(false);
  });

  it("neither Hero nor Capsule → header-only full-frame, no slot", () => {
    const layout = resolveGameImageLayout({
      src: "https://cdn.example.com/header.jpg",
      source: "steam",
      libraryHeroUrl: null,
      libraryCapsuleUrl: null,
    });

    expect(layout.backgroundSrc).toBe("");
    expect(layout.foregroundRole).toBe("header");
    expect(layout.foregroundContained).toBe(false);
    expect(layout.showVisualizationSlot).toBe(false);
  });

  it("no image at all → placeholder", () => {
    const layout = resolveGameImageLayout({
      src: "",
      source: "steam",
      libraryHeroUrl: null,
      libraryCapsuleUrl: null,
    });

    expect(layout.kind).toBe("placeholder");
    expect(layout.foregroundSrc).toBe("");
    expect(layout.showVisualizationSlot).toBe(false);
  });
});
