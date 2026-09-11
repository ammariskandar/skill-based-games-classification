/**
 * Aesthetic vocabulary tests — SBGC-228.
 *
 * Locks the canonical uppercase taxonomy (mirroring the backend
 * `AestheticCategory`), the definition copy, and the narrow/format helpers.
 */

import { describe, expect, it } from "vitest";

import {
  AESTHETIC_DEFINITIONS,
  AESTHETIC_VALUES,
  aestheticLabel,
  isAestheticValue,
  isSecondaryAestheticValid,
} from "./aesthetics";

describe("AESTHETIC_VALUES", () => {
  it("mirrors the canonical uppercase taxonomy", () => {
    expect(AESTHETIC_VALUES).toEqual([
      "SENSORY",
      "FANTASY",
      "NARRATIVE",
      "CHALLENGE",
    ]);
  });

  it("defines copy for every canonical value", () => {
    expect(AESTHETIC_DEFINITIONS).toHaveLength(AESTHETIC_VALUES.length);
    for (const value of AESTHETIC_VALUES) {
      const definition = AESTHETIC_DEFINITIONS.find(
        (item) => item.value === value,
      );
      expect(definition).toBeDefined();
      expect(definition?.label.length).toBeGreaterThan(0);
      expect(definition?.definition.length).toBeGreaterThan(0);
      expect(definition?.examples.length).toBeGreaterThan(0);
    }
  });
});

describe("isAestheticValue", () => {
  it("accepts every canonical value", () => {
    for (const value of AESTHETIC_VALUES) {
      expect(isAestheticValue(value)).toBe(true);
    }
  });

  it("rejects the empty selection and non-canonical strings", () => {
    expect(isAestheticValue("")).toBe(false);
    expect(isAestheticValue("action")).toBe(false);
    expect(isAestheticValue("sensory")).toBe(false);
    expect(isAestheticValue(null)).toBe(false);
    expect(isAestheticValue(undefined)).toBe(false);
    expect(isAestheticValue(42)).toBe(false);
  });
});

describe("aestheticLabel", () => {
  it("maps a canonical value to its short display label", () => {
    expect(aestheticLabel("SENSORY")).toBe("Sensory");
    expect(aestheticLabel("CHALLENGE")).toBe("Challenge");
  });

  it("returns null when unresolved", () => {
    expect(aestheticLabel(null)).toBeNull();
  });
});

describe("isSecondaryAestheticValid", () => {
  it("allows an empty secondary", () => {
    expect(isSecondaryAestheticValid("SENSORY", "")).toBe(true);
    expect(isSecondaryAestheticValid("SENSORY", null)).toBe(true);
    expect(isSecondaryAestheticValid("SENSORY", undefined)).toBe(true);
  });

  it("allows a distinct canonical secondary", () => {
    expect(isSecondaryAestheticValid("SENSORY", "FANTASY")).toBe(true);
  });

  it("rejects a non-canonical or repeated secondary", () => {
    expect(isSecondaryAestheticValid("SENSORY", "vibes")).toBe(false);
    expect(isSecondaryAestheticValid("SENSORY", "SENSORY")).toBe(false);
  });
});
