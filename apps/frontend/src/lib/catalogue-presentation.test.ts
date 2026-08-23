/**
 * Presentation-only catalogue helper tests — SBGC-77.
 *
 * Pure TypeScript, no fetch, no Django domain policy. These pin down the
 * page-parameter normalization, result-summary wording, pagination hrefs, and
 * the narrow classification state narrowing used by the /catalogue route.
 */

import { describe, expect, it } from "vitest";

import {
  catalogueHref,
  cataloguePageHref,
  computeResultRange,
  formatGameCount,
  formatResultSummary,
  gameHref,
  parsePageParam,
  presentCatalogueClassification,
} from "./catalogue-presentation";
import type { GameCatalogueClassification } from "./server/api/games";

describe("parsePageParam", () => {
  it("treats a missing value as page 1", () => {
    expect(parsePageParam(null)).toBe(1);
  });

  it("treats blank and whitespace-only values as page 1", () => {
    expect(parsePageParam("")).toBe(1);
    expect(parsePageParam("   ")).toBe(1);
  });

  it("treats non-numeric and negative values as page 1", () => {
    expect(parsePageParam("abc")).toBe(1);
    expect(parsePageParam("-1")).toBe(1);
    expect(parsePageParam("1.5")).toBe(1);
    expect(parsePageParam("12abc")).toBe(1);
  });

  it("treats zero as page 1", () => {
    expect(parsePageParam("0")).toBe(1);
  });

  it("accepts a valid positive integer", () => {
    expect(parsePageParam("3")).toBe(3);
    expect(parsePageParam("42")).toBe(42);
  });

  it("trims surrounding whitespace before parsing", () => {
    expect(parsePageParam("  7  ")).toBe(7);
  });

  it("rejects integers beyond the safe range as page 1", () => {
    expect(parsePageParam("999999999999999999999")).toBe(1);
  });
});

describe("formatGameCount", () => {
  it("uses the singular form for one", () => {
    expect(formatGameCount(1)).toBe("1 game");
  });

  it("uses the plural form for zero and other counts", () => {
    expect(formatGameCount(0)).toBe("0 games");
    expect(formatGameCount(42)).toBe("42 games");
  });
});

describe("computeResultRange", () => {
  it("returns null for an empty result set", () => {
    expect(computeResultRange(0, 1, 24)).toBeNull();
  });

  it("returns null for non-positive page or page size", () => {
    expect(computeResultRange(42, 0, 24)).toBeNull();
    expect(computeResultRange(42, 1, 0)).toBeNull();
  });

  it("computes a full first page", () => {
    expect(computeResultRange(42, 1, 24)).toEqual({ start: 1, end: 24 });
  });

  it("computes the final partial page", () => {
    expect(computeResultRange(42, 2, 24)).toEqual({ start: 25, end: 42 });
  });

  it("returns null for a page beyond the final page", () => {
    expect(computeResultRange(42, 3, 24)).toBeNull();
  });

  it("computes a single partial page smaller than the page size", () => {
    expect(computeResultRange(5, 1, 24)).toEqual({ start: 1, end: 5 });
  });
});

describe("formatResultSummary", () => {
  it("summarizes a full first page", () => {
    expect(formatResultSummary(42, 1, 24)).toBe("Showing 1–24 of 42 games");
  });

  it("summarizes a final partial page", () => {
    expect(formatResultSummary(42, 2, 24)).toBe("Showing 25–42 of 42 games");
  });

  it("uses the singular form for a single game", () => {
    expect(formatResultSummary(1, 1, 24)).toBe("Showing 1–1 of 1 game");
  });

  it("falls back to the plain count for a page beyond the end", () => {
    expect(formatResultSummary(42, 3, 24)).toBe("42 games");
  });

  it("falls back to the plain count for an empty catalogue", () => {
    expect(formatResultSummary(0, 1, 24)).toBe("0 games");
  });
});

describe("cataloguePageHref", () => {
  it("uses the bare route for page 1", () => {
    expect(cataloguePageHref(1)).toBe("/catalogue");
  });

  it("uses the bare route for non-positive pages", () => {
    expect(cataloguePageHref(0)).toBe("/catalogue");
    expect(cataloguePageHref(-1)).toBe("/catalogue");
  });

  it("appends the page query for later pages", () => {
    expect(cataloguePageHref(2)).toBe("/catalogue?page=2");
    expect(cataloguePageHref(42)).toBe("/catalogue?page=42");
  });
});

describe("catalogueHref", () => {
  it("builds the bare route with no params", () => {
    expect(catalogueHref()).toBe("/catalogue");
  });

  it("omits page 1 and keeps the query", () => {
    expect(catalogueHref({ q: "persona", page: 1 })).toBe(
      "/catalogue?q=persona",
    );
  });

  it("preserves q and page together", () => {
    expect(catalogueHref({ q: "persona", page: 2 })).toBe(
      "/catalogue?q=persona&page=2",
    );
  });

  it("encodes special characters in q", () => {
    expect(catalogueHref({ q: "elden ring" })).toBe("/catalogue?q=elden+ring");
  });

  it("omits an empty q", () => {
    expect(catalogueHref({ q: "", page: 2 })).toBe("/catalogue?page=2");
  });
});

describe("gameHref", () => {
  it("builds the public Game-detail href from a slug", () => {
    expect(gameHref("portal-2")).toBe("/games/portal-2");
  });

  it("preserves slugs with hyphens and underscores", () => {
    expect(gameHref("elden-ring")).toBe("/games/elden-ring");
    expect(gameHref("a_game")).toBe("/games/a_game");
  });
});

describe("presentCatalogueClassification", () => {
  it("treats a null classification as unclassified", () => {
    expect(presentCatalogueClassification(null)).toEqual({
      kind: "unclassified",
    });
  });

  it("treats a missing profile as unclassified", () => {
    const classification: GameCatalogueClassification = {
      status: "NO_SUBMISSIONS",
      challenge: null,
      reward: null,
      confidence_level: null,
      confidence_label: null,
      is_stale: false,
    };
    expect(presentCatalogueClassification(classification)).toEqual({
      kind: "unclassified",
    });
  });

  it("treats a missing reward as unclassified", () => {
    const classification: GameCatalogueClassification = {
      status: "READY",
      challenge: { micro: 51, macro: 31, mystiko: 18 },
      reward: null,
      confidence_level: 82,
      confidence_label: "High",
      is_stale: false,
    };
    expect(presentCatalogueClassification(classification)).toEqual({
      kind: "unclassified",
    });
  });

  it("returns an asymmetric classified state with the stale flag", () => {
    const classification: GameCatalogueClassification = {
      status: "READY",
      challenge: { micro: 51, macro: 31, mystiko: 18 },
      reward: { micro: 17, macro: 29, mystiko: 54 },
      confidence_level: 80,
      confidence_label: "High",
      is_stale: true,
    };

    const presentation = presentCatalogueClassification(classification);

    expect(presentation).toEqual({
      kind: "classified",
      challenge: { micro: 51, macro: 31, mystiko: 18 },
      reward: { micro: 17, macro: 29, mystiko: 54 },
      isStale: true,
    });
  });
});
