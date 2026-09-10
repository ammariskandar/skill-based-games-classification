import { describe, expect, it } from "vitest";

import {
  AESTHETIC_DESCRIPTIONS,
  describeAesthetic,
} from "./aesthetic-descriptions";
import { AestheticCategory } from "./types";

const { SENSORY, FANTASY, NARRATIVE, CHALLENGE, SPECIAL_FLOW } =
  AestheticCategory;

describe("aesthetic descriptions", () => {
  it("covers the four true aesthetics and twelve ordered hybrids", () => {
    expect(Object.keys(AESTHETIC_DESCRIPTIONS)).toHaveLength(16);
  });

  it("gives every entry a non-empty title and body", () => {
    for (const [key, entry] of Object.entries(AESTHETIC_DESCRIPTIONS)) {
      expect(entry.title.trim(), key).not.toBe("");
      expect(entry.body.trim(), key).not.toBe("");
    }
  });

  it("resolves each true aesthetic to its repeated category", () => {
    for (const category of [SENSORY, FANTASY, NARRATIVE, CHALLENGE]) {
      const description = describeAesthetic(category, null, true);
      expect(description).not.toBeNull();
      expect(description?.title).toContain("True");
      expect(description?.title).toContain(`${category[0]} + ${category[0]}`);
    }
  });

  it("keeps hybrid explanations ordered by dominant then secondary", () => {
    const sensoryFirst = describeAesthetic(SENSORY, FANTASY, false);
    const fantasyFirst = describeAesthetic(FANTASY, SENSORY, false);
    expect(sensoryFirst?.title).toBe(
      "Sensory & Fantasy / Sensory Dominant (S + F)",
    );
    expect(fantasyFirst?.title).toBe(
      "Fantasy & Sensory / Fantasy Dominant (F + S)",
    );
    expect(sensoryFirst?.title).not.toBe(fantasyFirst?.title);
  });

  it("returns null when there is nothing to explain", () => {
    expect(describeAesthetic(null, null, false)).toBeNull();
    expect(describeAesthetic(SPECIAL_FLOW, null, false)).toBeNull();
  });
});
