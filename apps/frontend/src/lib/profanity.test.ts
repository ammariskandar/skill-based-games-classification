/**
 * Profanity helper tests — SBGC-222.
 */

import { describe, expect, it } from "vitest";

import { containsProfanity } from "./profanity";

describe("containsProfanity", () => {
  it("detects profanity", () => {
    expect(containsProfanity("fuck")).toBe(true);
    expect(containsProfanity("this is shit")).toBe(true);
  });

  it("returns false for clean text", () => {
    expect(containsProfanity("hello world")).toBe(false);
  });

  it("returns false for an empty string", () => {
    expect(containsProfanity("")).toBe(false);
  });
});
