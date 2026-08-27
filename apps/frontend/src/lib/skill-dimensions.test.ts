/**
 * Runtime skill-profile validation tests — SBGC-163.
 *
 * Proves `validateSkillProfile` rejects malformed raw payloads (wrong type,
 * non-finite, non-integer, out-of-range, wrong-sum, missing keys) and accepts
 * only valid integer vectors summing to 100.  Fails closed: no coercion.
 */

import { describe, expect, it } from "vitest";

import {
  DIMENSIONS,
  DIMENSION_BG_CLASSES,
  DIMENSION_IDS,
  DIMENSION_TEXT_CLASSES,
  getDimensionDescription,
  validateSkillProfile,
  type DimensionId,
  type ProfileType,
} from "./skill-dimensions";

describe("validateSkillProfile — valid vectors", () => {
  it("accepts a standard distribution", () => {
    const result = validateSkillProfile({ micro: 50, mystiko: 30, macro: 20 });
    expect(result).toEqual({
      ok: true,
      value: { micro: 50, mystiko: 30, macro: 20 },
    });
  });

  it("accepts boundary extremes", () => {
    expect(validateSkillProfile({ micro: 100, mystiko: 0, macro: 0 }).ok).toBe(
      true,
    );
    expect(validateSkillProfile({ micro: 0, mystiko: 100, macro: 0 }).ok).toBe(
      true,
    );
    expect(validateSkillProfile({ micro: 0, mystiko: 0, macro: 100 }).ok).toBe(
      true,
    );
  });

  it("ignores extra keys", () => {
    const result = validateSkillProfile({
      micro: 50,
      mystiko: 30,
      macro: 20,
      extra: "ignored",
    });
    expect(result.ok).toBe(true);
  });
});

describe("validateSkillProfile — invalid type & finiteness", () => {
  const invalid = [
    null,
    undefined,
    "50,30,20",
    [50, 30, 20],
    true,
    123,
    { micro: Number.NaN, mystiko: 50, macro: 50 },
    { micro: Number.POSITIVE_INFINITY, mystiko: 0, macro: 100 },
    { micro: Number.NEGATIVE_INFINITY, mystiko: 50, macro: 50 },
    { micro: "50", mystiko: 30, macro: 20 },
  ];

  it.each(invalid)("rejects %j", (input) => {
    expect(validateSkillProfile(input).ok).toBe(false);
  });
});

describe("validateSkillProfile — invalid range & decimals", () => {
  it("rejects negative scores", () => {
    expect(
      validateSkillProfile({ micro: -10, mystiko: 60, macro: 50 }).ok,
    ).toBe(false);
  });

  it("rejects out-of-bounds scores", () => {
    expect(
      validateSkillProfile({ micro: 110, mystiko: 0, macro: -10 }).ok,
    ).toBe(false);
  });

  it("rejects fractional scores", () => {
    expect(
      validateSkillProfile({ micro: 33.4, mystiko: 33.3, macro: 33.3 }).ok,
    ).toBe(false);
  });
});

describe("validateSkillProfile — invalid composition sums", () => {
  it("rejects an under-sum of 99", () => {
    expect(validateSkillProfile({ micro: 33, mystiko: 33, macro: 33 }).ok).toBe(
      false,
    );
  });

  it("rejects an over-sum of 101", () => {
    expect(validateSkillProfile({ micro: 40, mystiko: 40, macro: 21 }).ok).toBe(
      false,
    );
  });

  it("rejects a zero-sum", () => {
    expect(validateSkillProfile({ micro: 0, mystiko: 0, macro: 0 }).ok).toBe(
      false,
    );
  });
});

describe("validateSkillProfile — missing keys", () => {
  it("rejects a profile missing mystiko", () => {
    expect(validateSkillProfile({ micro: 60, macro: 40 }).ok).toBe(false);
  });

  it("rejects a profile missing micro", () => {
    expect(validateSkillProfile({ mystiko: 60, macro: 40 }).ok).toBe(false);
  });
});

describe("getDimensionDescription — exhaustive mapping", () => {
  const pairs: Array<[ProfileType, DimensionId]> = [
    ["challenge", "micro"],
    ["challenge", "mystiko"],
    ["challenge", "macro"],
    ["reward", "micro"],
    ["reward", "mystiko"],
    ["reward", "macro"],
  ];

  it.each(pairs)(
    "returns a non-trivial description for %s/%s",
    (profile, dimension) => {
      const description = getDimensionDescription(profile, dimension);
      expect(typeof description).toBe("string");
      expect(description.trim().length).toBeGreaterThan(10);
      expect(description).not.toContain("undefined");
    },
  );
});

describe("getDimensionDescription — semantic divergence", () => {
  it("differs between Challenge and Reward for every dimension", () => {
    for (const dimension of DIMENSION_IDS) {
      expect(getDimensionDescription("challenge", dimension)).not.toBe(
        getDimensionDescription("reward", dimension),
      );
    }
  });
});

describe("DIMENSIONS — shared visual invariants", () => {
  it("contains exactly micro, mystiko, and macro in canonical order", () => {
    expect(DIMENSION_IDS).toEqual(["micro", "mystiko", "macro"]);
    expect(Object.keys(DIMENSIONS)).toEqual(["micro", "mystiko", "macro"]);
  });

  it("has non-empty labels, symbols, and colour tokens", () => {
    for (const id of DIMENSION_IDS) {
      const def = DIMENSIONS[id];
      expect(def.label.trim().length).toBeGreaterThan(0);
      expect(def.symbol.trim().length).toBeGreaterThan(0);
      expect(def.token).toBe(id);
      expect(DIMENSION_TEXT_CLASSES[id]).toBeTruthy();
      expect(DIMENSION_BG_CLASSES[id]).toBeTruthy();
    }
  });
});
