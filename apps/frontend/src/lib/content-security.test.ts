/**
 * Bio content-security sweep tests — SBGC-222.
 */

import { describe, expect, it } from "vitest";

import { validateContentSecurity } from "./content-security";

describe("validateContentSecurity", () => {
  it("rejects explicit HTML tags", () => {
    const result = validateContentSecurity(
      "<script>alert(1)</script>",
      "PLAIN",
    );
    expect(result.isValid).toBe(false);
    expect(result.error).toContain("HTML tags are not permitted");
  });

  it("rejects a bare <div>", () => {
    expect(validateContentSecurity("<div>hi</div>", "PLAIN").isValid).toBe(
      false,
    );
  });

  it("rejects active SQL injection syntax", () => {
    expect(
      validateContentSecurity("'; DROP TABLE users;--", "PLAIN").isValid,
    ).toBe(false);
    expect(validateContentSecurity("' OR '1'='1", "PLAIN").isValid).toBe(false);
  });

  it("passes innocent colloquial uses", () => {
    const result = validateContentSecurity("don't drop table tennis", "PLAIN");
    expect(result.isValid).toBe(true);
  });

  it("rejects profanity on the visible text", () => {
    expect(
      validateContentSecurity("this bio has fuck in it", "PLAIN").isValid,
    ).toBe(false);
  });

  it("strips BBCode before the profanity sweep", () => {
    expect(validateContentSecurity("[b]fuck[/b]", "BBCODE").isValid).toBe(
      false,
    );
  });

  it("rejects XSS script protocols", () => {
    expect(
      validateContentSecurity("javascript:alert(1)", "PLAIN").isValid,
    ).toBe(false);
  });

  it("rejects Python execution vectors", () => {
    expect(validateContentSecurity("eval(1)", "PLAIN").isValid).toBe(false);
  });

  it("returns sanitized bio on a clean payload", () => {
    const result = validateContentSecurity("Just a normal bio.", "PLAIN");
    expect(result.isValid).toBe(true);
    expect(result.sanitizedBio).toBe("Just a normal bio.");
  });
});
