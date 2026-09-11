/**
 * Score-validation tests — SBGC-215.
 *
 * Locks the dimension range, sum-to-100 invariant, and payload-level gating.
 */

import { describe, expect, it } from "vitest";

import {
  calculateProfileSum,
  isManualSubmissionReady,
  isProfileValid,
  isSubmissionPayloadValid,
  validateDimensionValue,
} from "./score-validation";

describe("validateDimensionValue", () => {
  it("accepts whole numbers in [0, 100]", () => {
    expect(validateDimensionValue(0)).toBe(true);
    expect(validateDimensionValue(50)).toBe(true);
    expect(validateDimensionValue(100)).toBe(true);
  });

  it("rejects out-of-range, fractional, and non-numeric values", () => {
    expect(validateDimensionValue(-1)).toBe(false);
    expect(validateDimensionValue(101)).toBe(false);
    expect(validateDimensionValue(0.5)).toBe(false);
    expect(validateDimensionValue(Number.NaN)).toBe(false);
  });
});

describe("calculateProfileSum", () => {
  it("sums the three dimensions", () => {
    expect(calculateProfileSum({ micro: 40, mystiko: 30, macro: 30 })).toBe(
      100,
    );
    expect(calculateProfileSum({ micro: 0, mystiko: 0, macro: 0 })).toBe(0);
  });
});

describe("isProfileValid", () => {
  it("accepts a profile that totals exactly 100", () => {
    expect(isProfileValid({ micro: 34, mystiko: 33, macro: 33 })).toBe(true);
    expect(isProfileValid({ micro: 100, mystiko: 0, macro: 0 })).toBe(true);
  });

  it("rejects profiles totalling 99, 101, or 0", () => {
    expect(isProfileValid({ micro: 33, mystiko: 33, macro: 33 })).toBe(false);
    expect(isProfileValid({ micro: 34, mystiko: 33, macro: 34 })).toBe(false);
    expect(isProfileValid({ micro: 0, mystiko: 0, macro: 0 })).toBe(false);
  });
});

describe("isSubmissionPayloadValid", () => {
  it("requires both Challenge and Reward to be valid simultaneously", () => {
    const valid = { micro: 40, mystiko: 30, macro: 30 };

    expect(
      isSubmissionPayloadValid({
        gameSlug: "hades",
        challenge: valid,
        reward: valid,
      }),
    ).toBe(true);

    expect(
      isSubmissionPayloadValid({
        gameSlug: "hades",
        challenge: valid,
        reward: { micro: 40, mystiko: 30, macro: 29 }, // totals 99
      }),
    ).toBe(false);
  });
});

describe("isManualSubmissionReady", () => {
  const valid = { micro: 40, mystiko: 30, macro: 30 };

  it("requires a canonical aesthetic alongside valid profiles", () => {
    expect(isManualSubmissionReady(valid, valid, "SENSORY")).toBe(true);
    expect(isManualSubmissionReady(valid, valid, "CHALLENGE")).toBe(true);
  });

  it("rejects an unselected or non-canonical aesthetic", () => {
    expect(isManualSubmissionReady(valid, valid, "")).toBe(false);
    expect(isManualSubmissionReady(valid, valid, "action")).toBe(false);
    expect(isManualSubmissionReady(valid, valid, null)).toBe(false);
    expect(isManualSubmissionReady(valid, valid, undefined)).toBe(false);
  });

  it("still requires both profiles to total 100", () => {
    expect(
      isManualSubmissionReady(
        valid,
        { micro: 40, mystiko: 30, macro: 29 },
        "SENSORY",
      ),
    ).toBe(false);
  });
});
