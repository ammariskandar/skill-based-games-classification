/**
 * Query-safety & resilience tests — SBGC-102.
 *
 * Pins the defensive SSR query helpers (`getSafeQueryString` /
 * `getSafeQueryInt` / `getSafeQueryBool`) and their integration into the
 * catalogue/rankings URL-state parsers: multi-value scalar resolution
 * (first value wins), integer overflow clamping, the cover-last "true
 * wins" contract, and control-character sanitization.  Pure TypeScript,
 * no network.
 */

import { describe, expect, it } from "vitest";

import { parseCatalogueQuery } from "../../../catalogue-presentation";
import { parseRankingsState } from "../../../rankings-state";
import {
  getSafeQueryBool,
  getSafeQueryInt,
  getSafeQueryString,
} from "../query";

describe("getSafeQueryString", () => {
  it("returns undefined when the key is absent", () => {
    expect(getSafeQueryString(new URLSearchParams(), "q")).toBeUndefined();
  });

  it("resolves duplicated keys to the primary (first) scalar", () => {
    const params = new URLSearchParams("q=portal&q=hades");
    expect(getSafeQueryString(params, "q")).toBe("portal");
  });

  it("trims and strips control characters", () => {
    const params = new URLSearchParams();
    params.set("q", "  Portal\u0000\u001f\u007f ");
    expect(getSafeQueryString(params, "q")).toBe("Portal");
  });

  it("decodes percent-encoded control characters", () => {
    expect(getSafeQueryString(new URLSearchParams("q=Portal%00%1f"), "q")).toBe(
      "Portal",
    );
  });

  it("normalizes an empty or whitespace-only value to undefined", () => {
    expect(getSafeQueryString(new URLSearchParams("q="), "q")).toBeUndefined();
    expect(
      getSafeQueryString(new URLSearchParams("q=%20%20"), "q"),
    ).toBeUndefined();
  });

  it("caps the length at maxLength", () => {
    const params = new URLSearchParams(`q=${"a".repeat(150)}`);
    expect(getSafeQueryString(params, "q", 100)?.length).toBe(100);
  });
});

describe("getSafeQueryInt", () => {
  it("returns the default when the key is absent", () => {
    expect(getSafeQueryInt(new URLSearchParams(), "page", 1)).toBe(1);
  });

  it("resolves duplicated keys to the primary (first) scalar", () => {
    const params = new URLSearchParams("page=3&page=10");
    expect(getSafeQueryInt(params, "page", 1)).toBe(3);
  });

  it("parses a valid integer", () => {
    expect(getSafeQueryInt(new URLSearchParams("page=42"), "page", 1)).toBe(42);
  });

  it("falls back to the default for non-numeric, negative, and float values", () => {
    expect(getSafeQueryInt(new URLSearchParams("page=abc"), "page", 1)).toBe(1);
    expect(getSafeQueryInt(new URLSearchParams("page=-5"), "page", 1)).toBe(1);
    expect(getSafeQueryInt(new URLSearchParams("page=2.5"), "page", 1)).toBe(1);
    expect(getSafeQueryInt(new URLSearchParams("page=0"), "page", 1)).toBe(1);
  });

  it("clamps oversized integers to max", () => {
    expect(
      getSafeQueryInt(new URLSearchParams("page=99999999999999999"), "page", 1),
    ).toBe(100);
    expect(getSafeQueryInt(new URLSearchParams("page=500"), "page", 1)).toBe(
      100,
    );
  });

  it("respects a custom max", () => {
    expect(
      getSafeQueryInt(new URLSearchParams("page=500"), "page", 1, 1, 24),
    ).toBe(24);
  });
});

describe("getSafeQueryBool", () => {
  it("returns the default when the key is absent", () => {
    expect(
      getSafeQueryBool(new URLSearchParams(), "coverless_last", true),
    ).toBe(true);
  });

  it("true wins across duplicated values", () => {
    const params = new URLSearchParams(
      "coverless_last=false&coverless_last=true",
    );
    expect(getSafeQueryBool(params, "coverless_last", true)).toBe(true);
  });

  it("false wins when no true is present", () => {
    const params = new URLSearchParams(
      "coverless_last=false&coverless_last=false",
    );
    expect(getSafeQueryBool(params, "coverless_last", true)).toBe(false);
  });

  it("accepts 1/0 and is case-insensitive", () => {
    expect(
      getSafeQueryBool(
        new URLSearchParams("coverless_last=1"),
        "coverless_last",
        false,
      ),
    ).toBe(true);
    expect(
      getSafeQueryBool(
        new URLSearchParams("coverless_last=TRUE"),
        "coverless_last",
        false,
      ),
    ).toBe(true);
    expect(
      getSafeQueryBool(
        new URLSearchParams("coverless_last=0"),
        "coverless_last",
        true,
      ),
    ).toBe(false);
  });

  it("falls back to the default for junk values", () => {
    expect(
      getSafeQueryBool(
        new URLSearchParams("coverless_last=maybe"),
        "coverless_last",
        true,
      ),
    ).toBe(true);
  });
});

describe("parser integration — adversarial URL input", () => {
  it("resolves duplicate page params to the primary scalar", () => {
    const state = parseCatalogueQuery(new URLSearchParams("page=3&page=10"));
    expect(state.page).toBe(3);
  });

  it("strips control characters from q", () => {
    const state = parseCatalogueQuery(new URLSearchParams("q=Portal%00%1f"));
    expect(state.q).toBe("Portal");
  });

  it("caps an over-length q at 100 characters", () => {
    const state = parseCatalogueQuery(
      new URLSearchParams(`q=${"a".repeat(120)}`),
    );
    expect(state.q.length).toBe(100);
  });

  it("keeps the cover-last true-wins contract for duplicated values", () => {
    const state = parseCatalogueQuery(
      new URLSearchParams("coverless_last=false&coverless_last=true"),
    );
    expect(state.coverlessLast).toBe(true);
  });

  it("rankings resolves duplicate profile params to the primary scalar", () => {
    const state = parseRankingsState(
      new URLSearchParams("profile=reward&profile=challenge"),
    );
    expect(state.profile).toBe("reward");
  });
});
