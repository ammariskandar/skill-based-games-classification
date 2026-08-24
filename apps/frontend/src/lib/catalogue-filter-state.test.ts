/**
 * Catalogue filter-disclosure preference tests — SBGC-79.
 *
 * Pins the versioned storage key and the boolean serialization contract used
 * by the filter-card expand/collapse persistence.
 */

import { describe, expect, it } from "vitest";

import {
  CATALOGUE_FILTER_EXPANDED_STORAGE_KEY,
  parseFilterExpanded,
  serializeFilterExpanded,
} from "./catalogue-filter-state";

describe("catalogue filter disclosure state", () => {
  it("uses a versioned, project-scoped storage key", () => {
    expect(CATALOGUE_FILTER_EXPANDED_STORAGE_KEY).toBe(
      "mygamedna:catalogue-filters-expanded:v1",
    );
  });

  it("serializes a boolean to the stored string form", () => {
    expect(serializeFilterExpanded(true)).toBe("true");
    expect(serializeFilterExpanded(false)).toBe("false");
  });

  it("parses true and false back to booleans", () => {
    expect(parseFilterExpanded("true")).toBe(true);
    expect(parseFilterExpanded("false")).toBe(false);
  });

  it("treats an absent or unrecognized value as null (fall back to default)", () => {
    expect(parseFilterExpanded(null)).toBeNull();
    expect(parseFilterExpanded("")).toBeNull();
    expect(parseFilterExpanded("garbage")).toBeNull();
    expect(parseFilterExpanded("1")).toBeNull();
  });
});
