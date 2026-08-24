/**
 * Catalogue filter/sort query-state tests — SBGC-79.
 *
 * Pure TypeScript, no fetch: pins down URL-parameter normalization,
 * `catalogueHref` preservation, pagination/reset hrefs, the checked-by-default
 * cover-last checkbox, and the noindex decision.
 */

import { describe, expect, it } from "vitest";

import {
  catalogueHref,
  catalogueHrefFromState,
  catalogueNeedsNoindex,
  parseCatalogueQuery,
  type CatalogueQueryState,
} from "./catalogue-presentation";

function parse(raw: string): CatalogueQueryState {
  return parseCatalogueQuery(new URLSearchParams(raw));
}

describe("parseCatalogueQuery", () => {
  it("applies all defaults for an empty query", () => {
    expect(parse("")).toEqual({
      q: "",
      page: 1,
      source: null,
      classified: null,
      sort: "name_asc",
      profile: "challenge",
      dominant: null,
      coverlessLast: true,
    });
  });

  it("parses every recognized parameter", () => {
    expect(
      parse(
        "q=elden&page=2&source=steam&classified=true&sort=micro&profile=reward&dominant=mystiko&coverless_last=false",
      ),
    ).toEqual({
      q: "elden",
      page: 2,
      source: "steam",
      classified: true,
      sort: "micro",
      profile: "reward",
      dominant: "mystiko",
      coverlessLast: false,
    });
  });

  it("trims q whitespace", () => {
    expect(parse("q=%20%20portal%20%20").q).toBe("portal");
  });

  it("drops invalid source, classified, sort, profile, and dominant", () => {
    const state = parse(
      "source=epic&classified=yes&sort=bogus&profile=none&dominant=meso",
    );
    expect(state.source).toBeNull();
    expect(state.classified).toBeNull();
    expect(state.sort).toBe("name_asc");
    expect(state.profile).toBe("challenge");
    expect(state.dominant).toBeNull();
  });

  it("treats an invalid page as page 1", () => {
    expect(parse("page=abc").page).toBe(1);
  });

  it("defaults the cover-last checkbox to checked", () => {
    expect(parse("").coverlessLast).toBe(true);
    expect(parse("coverless_last=true").coverlessLast).toBe(true);
  });

  it("round-trips an explicit unchecked cover-last state", () => {
    expect(parse("coverless_last=false").coverlessLast).toBe(false);
  });
});

describe("catalogueHref — SBGC-79 state preservation", () => {
  it("preserves source, classified, sort, profile, and dominant", () => {
    expect(
      catalogueHref({
        q: "persona",
        source: "steam",
        classified: true,
        sort: "micro",
        profile: "reward",
        dominant: "macro",
        page: 2,
      }),
    ).toBe(
      "/catalogue?q=persona&page=2&source=steam&classified=true&sort=micro&profile=reward&dominant=macro",
    );
  });

  it("serializes classified=false truthfully", () => {
    expect(catalogueHref({ classified: false })).toBe(
      "/catalogue?classified=false",
    );
  });

  it("omits default sort and profile", () => {
    expect(catalogueHref({ sort: "name_asc", profile: "challenge" })).toBe(
      "/catalogue",
    );
  });

  it("represents an explicit unchecked cover-last state", () => {
    expect(catalogueHref({ coverlessLast: false })).toBe(
      "/catalogue?coverless_last=false",
    );
  });

  it("omits a checked cover-last state (the default)", () => {
    expect(catalogueHref({ coverlessLast: true })).toBe("/catalogue");
  });
});

describe("catalogueHrefFromState", () => {
  const filtered: CatalogueQueryState = {
    q: "portal",
    page: 3,
    source: "steam",
    classified: true,
    sort: "recent",
    profile: "challenge",
    dominant: "micro",
    coverlessLast: false,
  };

  it("preserves the full state when navigating pages", () => {
    expect(catalogueHrefFromState(filtered, 4)).toBe(
      "/catalogue?q=portal&page=4&source=steam&classified=true&sort=recent&dominant=micro&coverless_last=false",
    );
  });

  it("drops the page when returning to page 1", () => {
    expect(catalogueHrefFromState(filtered, 1)).toBe(
      "/catalogue?q=portal&source=steam&classified=true&sort=recent&dominant=micro&coverless_last=false",
    );
  });

  it("collapses to the bare route for a default state", () => {
    const defaultState: CatalogueQueryState = {
      q: "",
      page: 1,
      source: null,
      classified: null,
      sort: "name_asc",
      profile: "challenge",
      dominant: null,
      coverlessLast: true,
    };
    expect(catalogueHrefFromState(defaultState)).toBe("/catalogue");
  });
});

describe("catalogueNeedsNoindex", () => {
  const base: CatalogueQueryState = {
    q: "",
    page: 1,
    source: null,
    classified: null,
    sort: "name_asc",
    profile: "challenge",
    dominant: null,
    coverlessLast: true,
  };

  it("indexes the base catalogue", () => {
    expect(catalogueNeedsNoindex(base)).toBe(false);
  });

  it("noindexes search, filter, sort, and unchecked cover-last states", () => {
    expect(catalogueNeedsNoindex({ ...base, q: "portal" })).toBe(true);
    expect(catalogueNeedsNoindex({ ...base, source: "manual" })).toBe(true);
    expect(catalogueNeedsNoindex({ ...base, classified: true })).toBe(true);
    expect(catalogueNeedsNoindex({ ...base, sort: "recent" })).toBe(true);
    expect(catalogueNeedsNoindex({ ...base, profile: "reward" })).toBe(true);
    expect(catalogueNeedsNoindex({ ...base, dominant: "micro" })).toBe(true);
    expect(catalogueNeedsNoindex({ ...base, coverlessLast: false })).toBe(true);
  });
});
