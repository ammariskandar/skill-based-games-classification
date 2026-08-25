import { describe, expect, it } from "vitest";

import {
  calculatePageSize,
  DEFAULT_RANKINGS_STATE,
  formatRankingScore,
  parseRankingsState,
  rankingsHref,
  rankingsNeedsNoindex,
  SORT_OPTIONS,
  sortKeyFor,
} from "./rankings-state";

describe("parseRankingsState", () => {
  it("returns the default state for an empty query", () => {
    expect(parseRankingsState(new URLSearchParams())).toEqual(
      DEFAULT_RANKINGS_STATE,
    );
  });

  it("parses a full state", () => {
    const state = parseRankingsState(
      new URLSearchParams(
        "profile=reward&dimension=mystiko&direction=asc&page=3&game=hades",
      ),
    );
    expect(state).toEqual({
      profile: "reward",
      dimension: "mystiko",
      direction: "asc",
      page: 3,
      game: "hades",
    });
  });

  it("normalizes invalid values to defaults", () => {
    const state = parseRankingsState(
      new URLSearchParams(
        "profile=bogus&dimension=nope&direction=sideways&page=0&game=  ",
      ),
    );
    expect(state).toEqual(DEFAULT_RANKINGS_STATE);
  });

  it("normalizes a non-numeric or zero page to 1", () => {
    expect(parseRankingsState(new URLSearchParams("page=abc")).page).toBe(1);
    expect(parseRankingsState(new URLSearchParams("page=0")).page).toBe(1);
    expect(parseRankingsState(new URLSearchParams("page=-3")).page).toBe(1);
    expect(parseRankingsState(new URLSearchParams("page=7")).page).toBe(7);
  });
});

describe("rankingsHref", () => {
  it("renders the bare route for the default state", () => {
    expect(rankingsHref(DEFAULT_RANKINGS_STATE)).toBe("/rankings");
  });

  it("omits default values and includes non-default ones", () => {
    expect(
      rankingsHref({
        profile: "challenge",
        dimension: "macro",
        direction: "asc",
        page: 2,
        game: "hades",
      }),
    ).toBe(
      "/rankings?profile=challenge&dimension=macro&direction=asc&page=2&game=hades",
    );
  });

  it("keeps game selection independent of page", () => {
    expect(rankingsHref({ page: 4, game: "portal-2" })).toBe(
      "/rankings?page=4&game=portal-2",
    );
  });
});

describe("rankingsNeedsNoindex", () => {
  it("is false for the default state", () => {
    expect(rankingsNeedsNoindex(DEFAULT_RANKINGS_STATE)).toBe(false);
  });

  it("is true for any non-default state", () => {
    expect(
      rankingsNeedsNoindex({ ...DEFAULT_RANKINGS_STATE, profile: "reward" }),
    ).toBe(true);
    expect(rankingsNeedsNoindex({ ...DEFAULT_RANKINGS_STATE, page: 2 })).toBe(
      true,
    );
    expect(
      rankingsNeedsNoindex({ ...DEFAULT_RANKINGS_STATE, game: "hades" }),
    ).toBe(true);
  });
});

describe("sort choices", () => {
  it("exposes six choices in display order", () => {
    expect(SORT_OPTIONS.map(sortKeyForOption)).toEqual([
      "micro-desc",
      "micro-asc",
      "macro-desc",
      "macro-asc",
      "mystiko-desc",
      "mystiko-asc",
    ]);
  });

  it("builds a stable sort key", () => {
    expect(sortKeyFor("micro", "desc")).toBe("micro-desc");
    expect(sortKeyFor("mystiko", "asc")).toBe("mystiko-asc");
  });
});

function sortKeyForOption(option: (typeof SORT_OPTIONS)[number]): string {
  return sortKeyFor(option.dimension, option.direction);
}

describe("formatRankingScore", () => {
  it("rounds .5 and .4 correctly for display", () => {
    expect(formatRankingScore(67.4)).toBe(67);
    expect(formatRankingScore(67.5)).toBe(68);
    expect(formatRankingScore(67.6)).toBe(68);
  });

  it("leaves integers unchanged", () => {
    expect(formatRankingScore(51)).toBe(51);
    expect(formatRankingScore(70)).toBe(70);
  });
});

describe("calculatePageSize", () => {
  it("fits whole rows only", () => {
    expect(calculatePageSize(500, 100, 10)).toBe(4); // floor(500 / 110)
  });

  it("never returns below 1", () => {
    expect(calculatePageSize(0, 100, 10)).toBe(1);
    expect(calculatePageSize(50, 100, 10)).toBe(1);
    expect(calculatePageSize(100, 0, 10)).toBe(1);
    expect(calculatePageSize(Number.NaN, 100, 10)).toBe(1);
  });

  it("targets approximately five rows at the reference geometry", () => {
    // ~5 rows when a row + gap is ~110px and the list is ~560px tall.
    expect(calculatePageSize(560, 100, 10)).toBe(5);
  });
});
