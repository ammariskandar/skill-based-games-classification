import { describe, expect, it } from "vitest";

import {
  NEUTRAL_PROFILE,
  previewConfidence,
  softenProfile,
} from "./soft-normalize";

describe("previewConfidence", () => {
  it("is 0 with no progress and 1 when the part is complete", () => {
    expect(previewConfidence(0, 6)).toBe(0);
    expect(previewConfidence(6, 6)).toBe(1);
  });

  it("clamps out-of-range inputs", () => {
    expect(previewConfidence(-3, 6)).toBe(0);
    expect(previewConfidence(9, 6)).toBe(1);
    expect(previewConfidence(3, 0)).toBe(0);
  });
});

describe("softenProfile", () => {
  const accurate = { micro: 100, macro: 0, mystiko: 0 };

  it("returns the neutral centre at zero confidence", () => {
    expect(softenProfile(accurate, 0)).toEqual(NEUTRAL_PROFILE);
  });

  it("returns the accurate profile unchanged at full confidence", () => {
    expect(softenProfile(accurate, 1)).toEqual(accurate);
  });

  it("pulls an early extreme answer toward neutral", () => {
    const early = softenProfile(accurate, 1 / 6);
    expect(early.micro).toBeLessThan(accurate.micro);
    expect(early.micro).toBeGreaterThan(NEUTRAL_PROFILE.micro);
    expect(early.macro).toBeGreaterThan(accurate.macro);
  });

  it("converges monotonically toward the accurate profile", () => {
    const one = softenProfile(accurate, 1 / 6).micro;
    const half = softenProfile(accurate, 0.5).micro;
    const full = softenProfile(accurate, 1).micro;
    expect(one).toBeLessThan(half);
    expect(half).toBeLessThan(full);
  });
});
