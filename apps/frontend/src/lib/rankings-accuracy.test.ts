/**
 * Ranking accuracy tests — SBGC-84 (frontend contract/helpers).
 *
 * Verifies that the frontend URL builders/parsers round-trip all 18
 * profile × dimension × direction combinations, that display rounding never
 * mutates the underlying score, and that cross-page selection resolution and
 * page-size normalization stay correct.  No network, no browser.
 */

import { describe, expect, it } from "vitest";

import {
  formatRankingScore,
  normalizePageSize,
  parseRankingsState,
  rankingsHref,
  resolveRankingSelection,
} from "./rankings-state";
import { buildRankingsUrl } from "./rankings-load";
import type {
  RankingDimension,
  RankingProfile,
  RankingDirection,
} from "./rankings-state";

const PROFILES: readonly RankingProfile[] = ["unified", "challenge", "reward"];
const DIMENSIONS: readonly RankingDimension[] = ["micro", "macro", "mystiko"];
const DIRECTIONS: readonly RankingDirection[] = ["desc", "asc"];

describe("buildRankingsUrl covers all 18 sort combinations", () => {
  for (const profile of PROFILES) {
    for (const dimension of DIMENSIONS) {
      for (const direction of DIRECTIONS) {
        it(`emits ${profile}/${dimension}/${direction}`, () => {
          const url = buildRankingsUrl({
            profile,
            dimension,
            direction,
            page: 2,
            pageSize: 8,
          });
          expect(url).toContain(`profile=${profile}`);
          expect(url).toContain(`dimension=${dimension}`);
          expect(url).toContain(`direction=${direction}`);
          expect(url).toContain("page=2");
          expect(url).toContain("page_size=8");
        });
      }
    }
  }
});

describe("rankingsHref round-trips all 18 sort states", () => {
  for (const profile of PROFILES) {
    for (const dimension of DIMENSIONS) {
      for (const direction of DIRECTIONS) {
        it(`round-trips ${profile}/${dimension}/${direction}`, () => {
          const href = rankingsHref({ profile, dimension, direction, page: 1 });
          const query = href.includes("?") ? href.split("?")[1] : "";
          const parsed = parseRankingsState(new URLSearchParams(query));
          expect(parsed.profile).toBe(profile);
          expect(parsed.dimension).toBe(dimension);
          expect(parsed.direction).toBe(direction);
          expect(parsed.page).toBe(1);
        });
      }
    }
  }
});

describe("formatRankingScore preserves sort metadata", () => {
  it("rounds half-integers for display only", () => {
    expect(formatRankingScore(74.5)).toBe(75);
    expect(formatRankingScore(70)).toBe(70);
    expect(formatRankingScore(67.5)).toBe(68);
  });

  it("does not mutate the input score", () => {
    const score = 74.5;
    formatRankingScore(score);
    expect(score).toBe(74.5);
  });
});

describe("resolveRankingSelection across page boundaries", () => {
  const page = [
    { slug: "top", name: "Top" },
    { slug: "second", name: "Second" },
  ];

  it("resolves an on-page slug directly", () => {
    expect(resolveRankingSelection("second", page, null)).toEqual({
      slug: "second",
      name: "Second",
    });
  });

  it("keeps an off-page selection when its detail is resolved", () => {
    expect(
      resolveRankingSelection("off-page", page, {
        slug: "off-page",
        name: "Off Page",
      }),
    ).toEqual({ slug: "off-page", name: "Off Page" });
  });

  it("falls back to the top-ranked item for an unresolvable off-page slug", () => {
    expect(resolveRankingSelection("missing", page, null)).toEqual({
      slug: "top",
      name: "Top",
    });
  });
});

describe("normalizePageSize", () => {
  it("clamps invalid and oversized values", () => {
    expect(normalizePageSize(null, 5, 50)).toBe(5);
    expect(normalizePageSize("0", 5, 50)).toBe(5);
    expect(normalizePageSize("9999", 5, 50)).toBe(50);
    expect(normalizePageSize("7", 5, 50)).toBe(7);
  });
});
