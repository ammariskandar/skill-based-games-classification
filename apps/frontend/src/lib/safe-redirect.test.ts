import { describe, expect, it } from "vitest";

import { safeRedirectTarget } from "./safe-redirect";

describe("safeRedirectTarget", () => {
  it("accepts absolute same-origin paths, including query strings", () => {
    expect(safeRedirectTarget("/about?action=suggest")).toBe(
      "/about?action=suggest",
    );
    expect(safeRedirectTarget("/profile/james.bond")).toBe(
      "/profile/james.bond",
    );
    expect(safeRedirectTarget("/rankings?page=3&profile=challenge")).toBe(
      "/rankings?page=3&profile=challenge",
    );
  });

  it("trims surrounding whitespace", () => {
    expect(safeRedirectTarget("  /about  ")).toBe("/about");
  });

  it.each([
    ["absolute URL", "https://evil.test/steal"],
    ["protocol-relative URL", "//evil.test/steal"],
    ["backslash-normalised URL", "/\\evil.test/steal"],
    ["scheme-bearing payload", "javascript:alert(1)"],
    ["relative path without a leading slash", "about"],
    ["empty string", ""],
    ["whitespace only", "   "],
  ])("rejects %s", (_label, candidate) => {
    expect(safeRedirectTarget(candidate)).toBe("/");
  });

  it("rejects a missing candidate", () => {
    expect(safeRedirectTarget(null)).toBe("/");
    expect(safeRedirectTarget(undefined)).toBe("/");
  });

  it("honours a custom fallback", () => {
    expect(safeRedirectTarget("https://evil.test", "/rankings")).toBe(
      "/rankings",
    );
  });
});
