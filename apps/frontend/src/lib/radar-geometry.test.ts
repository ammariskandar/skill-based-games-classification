import { describe, expect, it } from "vitest";

import {
  SPOKES,
  generateSplinePath,
  getSpokeAngle,
  getSpokePoints,
  polarToCartesian,
  type Point,
} from "./radar-geometry";
import type { SkillProfileVector } from "./skill-dimensions";

describe("polarToCartesian", () => {
  it("maps 0° to 12 o'clock (top)", () => {
    const point = polarToCartesian(100, 100, 50, 0);
    expect(point.x).toBeCloseTo(100);
    expect(point.y).toBeCloseTo(50);
  });

  it("maps 90° to 3 o'clock (right)", () => {
    const point = polarToCartesian(100, 100, 50, 90);
    expect(point.x).toBeCloseTo(150);
    expect(point.y).toBeCloseTo(100);
  });

  it("maps 180° to 6 o'clock (bottom)", () => {
    const point = polarToCartesian(100, 100, 50, 180);
    expect(point.x).toBeCloseTo(100);
    expect(point.y).toBeCloseTo(150);
  });

  it("maps 270° to 9 o'clock (left)", () => {
    const point = polarToCartesian(100, 100, 50, 270);
    expect(point.x).toBeCloseTo(50);
    expect(point.y).toBeCloseTo(100);
  });
});

describe("opposite-spoke invariant (180° separation)", () => {
  it("maps Micro diametrically across profiles", () => {
    expect(getSpokeAngle("challenge", "micro")).toBe(0);
    expect(getSpokeAngle("reward", "micro")).toBe(180);
  });

  it("maps Mystiko diametrically across profiles", () => {
    expect(getSpokeAngle("challenge", "mystiko")).toBe(120);
    expect(getSpokeAngle("reward", "mystiko")).toBe(300);
  });

  it("maps Macro diametrically across profiles", () => {
    expect(getSpokeAngle("challenge", "macro")).toBe(240);
    expect(getSpokeAngle("reward", "macro")).toBe(60);
  });

  it("exposes exactly six spokes", () => {
    expect(SPOKES).toHaveLength(6);
  });
});

describe("getSpokePoints score normalization", () => {
  const center: Point = { x: 0, y: 0 };
  const maxRadius = 100;

  it("maps score 0 to the center (r = 0)", () => {
    const points = getSpokePoints(
      { micro: 0, mystiko: 0, macro: 0 },
      "challenge",
      center,
      maxRadius,
    );
    for (const point of points) {
      expect(point.x).toBeCloseTo(0);
      expect(point.y).toBeCloseTo(0);
    }
  });

  it("maps score 100 to the perimeter (r = maxRadius)", () => {
    const points = getSpokePoints(
      { micro: 100, mystiko: 100, macro: 100 },
      "challenge",
      center,
      maxRadius,
    );
    for (const point of points) {
      expect(Math.hypot(point.x, point.y)).toBeCloseTo(maxRadius);
    }
  });

  it("maps score 50 to half the radius", () => {
    const points = getSpokePoints(
      { micro: 50, mystiko: 50, macro: 50 },
      "challenge",
      center,
      maxRadius,
    );
    for (const point of points) {
      expect(Math.hypot(point.x, point.y)).toBeCloseTo(maxRadius / 2);
    }
  });
});

describe("generateSplinePath", () => {
  const center: Point = { x: 160, y: 160 };
  const maxRadius = 136;

  const extremeVectors: SkillProfileVector[] = [
    { micro: 100, mystiko: 0, macro: 0 },
    { micro: 0, mystiko: 100, macro: 0 },
    { micro: 0, mystiko: 0, macro: 100 },
    { micro: 33, mystiko: 33, macro: 34 },
  ];

  for (const vector of extremeVectors) {
    it(`produces a clean path for ${vector.micro}/${vector.mystiko}/${vector.macro}`, () => {
      const points = getSpokePoints(vector, "challenge", center, maxRadius);
      const path = generateSplinePath(points);
      expect(path.length).toBeGreaterThan(0);
      expect(path).not.toContain("NaN");
      expect(path).not.toContain("undefined");
      expect(path.startsWith("M")).toBe(true);
    });
  }

  it("returns an empty string for empty points", () => {
    expect(generateSplinePath([])).toBe("");
  });

  it("returns an empty string for null points", () => {
    expect(generateSplinePath(null as unknown as Point[])).toBe("");
  });
});
