import { describe, expect, it } from "vitest";

import {
  SPOKES,
  generateSplinePath,
  getSpokeAngle,
  getSpokePoints,
  polarToCartesian,
  type Point,
} from "./radar-geometry";
import type { DimensionId, SkillProfileVector } from "./skill-dimensions";

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
    { micro: 34, mystiko: 33, macro: 33 },
    { micro: 33, mystiko: 34, macro: 33 },
    { micro: 0, mystiko: 0, macro: 0 },
    { micro: 100, mystiko: 100, macro: 100 },
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

describe("polarToCartesian full boundary sweep", () => {
  const centerX = 37;
  const centerY = 61;
  const radius = 25;
  const sin60 = Math.sqrt(3) / 2;

  const boundaryCases: Array<[number, number, number]> = [
    [0, centerX, centerY - radius],
    [60, centerX + radius * sin60, centerY - radius * 0.5],
    [120, centerX + radius * sin60, centerY + radius * 0.5],
    [180, centerX, centerY + radius],
    [240, centerX - radius * sin60, centerY + radius * 0.5],
    [300, centerX - radius * sin60, centerY - radius * 0.5],
    // 360° wraps back to 12 o'clock.
    [360, centerX, centerY - radius],
  ];

  for (const [angle, expectedX, expectedY] of boundaryCases) {
    it(`maps ${angle}° around the offset center (${centerX}, ${centerY})`, () => {
      const point = polarToCartesian(centerX, centerY, radius, angle);
      expect(point.x).toBeCloseTo(expectedX, 10);
      expect(point.y).toBeCloseTo(expectedY, 10);
    });
  }

  it("preserves a zero radius at the center for every angle", () => {
    for (const angle of [0, 60, 120, 180, 240, 300]) {
      const point = polarToCartesian(centerX, centerY, 0, angle);
      expect(point.x).toBeCloseTo(centerX);
      expect(point.y).toBeCloseTo(centerY);
    }
  });
});

describe("diametrically opposite dimension invariant (180° separation)", () => {
  it.each(["micro", "mystiko", "macro"] as const)(
    "separates Challenge and Reward %s by exactly 180°",
    (dimension) => {
      const challengeAngle = getSpokeAngle("challenge", dimension);
      const rewardAngle = getSpokeAngle("reward", dimension);
      expect(Math.abs(challengeAngle - rewardAngle)).toBe(180);
    },
  );

  it("keeps the six spokes at unique 60° intervals", () => {
    const angles = SPOKES.map((spoke) => spoke.angleDegrees).sort(
      (a, b) => a - b,
    );
    expect(angles).toEqual([0, 60, 120, 180, 240, 300]);
  });
});

describe("degenerate score vectors", () => {
  const center: Point = { x: 160, y: 160 };
  const maxRadius = 136;

  it("collapses every vertex to the center for an all-zero profile", () => {
    const points = getSpokePoints(
      { micro: 0, mystiko: 0, macro: 0 },
      "challenge",
      center,
      maxRadius,
    );
    expect(points).toHaveLength(3);
    for (const point of points) {
      expect(point.x).toBeCloseTo(center.x);
      expect(point.y).toBeCloseTo(center.y);
    }
  });

  it("places every vertex on the perimeter for a maximum-scale profile", () => {
    const points = getSpokePoints(
      { micro: 100, mystiko: 100, macro: 100 },
      "challenge",
      center,
      maxRadius,
    );
    expect(points).toHaveLength(3);
    for (const point of points) {
      expect(Math.hypot(point.x - center.x, point.y - center.y)).toBeCloseTo(
        maxRadius,
      );
    }
  });
});

describe("invalid and defensive input handling", () => {
  const center: Point = { x: 160, y: 160 };
  const maxRadius = 136;

  it("returns an empty string for undefined points", () => {
    expect(generateSplinePath(undefined as unknown as Point[])).toBe("");
  });

  it("handles out-of-bound scores gracefully without NaN", () => {
    const outOfBounds: SkillProfileVector[] = [
      { micro: 150, mystiko: 0, macro: 0 },
      { micro: -20, mystiko: 50, macro: 30 },
      { micro: 0, mystiko: 120, macro: 40 },
    ];
    for (const vector of outOfBounds) {
      const path = generateSplinePath(
        getSpokePoints(vector, "challenge", center, maxRadius),
      );
      expect(path.startsWith("M")).toBe(true);
      expect(path).not.toContain("NaN");
      expect(path).not.toContain("undefined");
    }
  });

  it("treats missing dimensions in a partial vector as zero", () => {
    const partial = { micro: 50 } as unknown as SkillProfileVector;
    const points = getSpokePoints(partial, "challenge", center, maxRadius);
    expect(points).toHaveLength(3);
    for (const point of points) {
      expect(Number.isFinite(point.x)).toBe(true);
      expect(Number.isFinite(point.y)).toBe(true);
    }

    const path = generateSplinePath(points);
    expect(path.startsWith("M")).toBe(true);
    expect(path).not.toContain("NaN");
    expect(path).not.toContain("undefined");
  });

  it("rejects unknown (profile, dimension) spoke pairs", () => {
    expect(() => getSpokeAngle("challenge", "macro")).not.toThrow();
    expect(() => getSpokeAngle("challenge", "steam" as DimensionId)).toThrow(
      "No radar spoke defined",
    );
  });
});
