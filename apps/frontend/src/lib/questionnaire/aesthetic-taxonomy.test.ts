/**
 * Aesthetic taxonomy and resolver tests — SBGC-172 (Epic SBGC-171).
 *
 * The client-side resolution must mirror the backend resolver exactly, so the
 * expected values here are the canonical matrix from the ticket specification.
 */

import { describe, expect, it } from "vitest";

import {
  AestheticCategory,
  InvalidOptionSelectionError,
  NONE_OPTION,
  OPTION_BY_ID,
  OPTION_TAXONOMY,
  PART2_SET_MAP,
  PRIMARY_OPTIONS,
  QuestionSetId,
  SECONDARY_OPTION_POOL,
  UnknownOptionError,
  UnresolvableAestheticError,
  availableSecondaryOptions,
  mapOptionToCategory,
  resolveAesthetic,
  resolveFromOptions,
} from "./aesthetic-taxonomy";

const CANONICAL = [
  AestheticCategory.SENSORY,
  AestheticCategory.FANTASY,
  AestheticCategory.NARRATIVE,
  AestheticCategory.CHALLENGE,
];

describe("option taxonomy", () => {
  it("registers the full 18-option Q1/Q2 taxonomy", () => {
    expect(Object.keys(OPTION_TAXONOMY)).toHaveLength(18);
    expect(PRIMARY_OPTIONS).toHaveLength(17);
    expect(SECONDARY_OPTION_POOL).toHaveLength(18);
    expect(PRIMARY_OPTIONS.map((o) => o.optionId)).not.toContain("OPT_NONE");
  });

  it("maps every option to its canonical category", () => {
    expect(mapOptionToCategory("OPT_S1")).toBe(AestheticCategory.SENSORY);
    expect(mapOptionToCategory("OPT_F4")).toBe(AestheticCategory.FANTASY);
    expect(mapOptionToCategory("OPT_N2")).toBe(AestheticCategory.NARRATIVE);
    expect(mapOptionToCategory("OPT_C4")).toBe(AestheticCategory.CHALLENGE);
    expect(mapOptionToCategory("OPT_COL")).toBe(
      AestheticCategory.COLLABORATIVE,
    );
    expect(mapOptionToCategory("OPT_NONE")).toBe(AestheticCategory.NONE);
  });

  it("keeps OPTION_BY_ID consistent with the taxonomy", () => {
    for (const [optionId, category] of Object.entries(OPTION_TAXONOMY)) {
      expect(OPTION_BY_ID[optionId]?.category).toBe(category);
    }
  });

  it("throws on an unknown option", () => {
    expect(() => mapOptionToCategory("OPT_BOGUS")).toThrow(UnknownOptionError);
  });
});

describe("Q1 option copy emphasis", () => {
  it("emphasises a phrase that appears verbatim in every label", () => {
    for (const option of PRIMARY_OPTIONS) {
      const emphasis = option.emphasis;
      expect(emphasis, option.optionId).toBeDefined();
      if (!emphasis) continue;
      expect(option.label, option.optionId).toContain(emphasis.text);
    }
  });

  it("carries the revised Q1 copy and its emphasis anchors", () => {
    const byId = new Map(PRIMARY_OPTIONS.map((o) => [o.optionId, o]));
    expect(byId.get("OPT_F1")?.label).toBe("I get to build a world of my own");
    expect(byId.get("OPT_F1")?.emphasis).toEqual({
      text: "build a world of my own",
      color: "light-blue",
    });
    expect(byId.get("OPT_N2")?.label).toBe("I get attached to the characters");
    expect(byId.get("OPT_N2")?.emphasis).toEqual({
      text: "attached to the characters",
      color: "lime",
    });
    expect(byId.get("OPT_F4")?.label).toBe("I can change history");
    expect(byId.get("OPT_F4")?.emphasis).toEqual({
      text: "history",
      color: "blue",
    });
    expect(byId.get("OPT_C2")?.label).toBe(
      "I am much better than everyone else in this game",
    );
  });
});

describe("availableSecondaryOptions", () => {
  it("filters out the Q1 selection and always includes none-of-the-above", () => {
    const options = availableSecondaryOptions("OPT_S1");
    const ids = options.map((o) => o.optionId);
    expect(ids).not.toContain("OPT_S1");
    expect(ids.at(-1)).toBe(NONE_OPTION.optionId);
    expect(options).toHaveLength(17);
  });

  it("filters collaborative out of Q2 when chosen in Q1", () => {
    const ids = availableSecondaryOptions("OPT_COL").map((o) => o.optionId);
    expect(ids).not.toContain("OPT_COL");
    expect(ids).toContain("OPT_NONE");
    expect(ids).toHaveLength(17);
  });

  it("rejects none-of-the-above as a Q1 selection", () => {
    expect(() => availableSecondaryOptions("OPT_NONE")).toThrow(
      InvalidOptionSelectionError,
    );
  });
});

describe("resolveAesthetic — true aesthetics", () => {
  it.each(CANONICAL)("resolves %s + itself to a true aesthetic", (category) => {
    const result = resolveAesthetic(category, category);
    expect(result.isTrueAesthetic).toBe(true);
    expect(result.dominantAesthetic).toBe(category);
    expect(result.secondaryAesthetic).toBeNull();
    expect(result.part2RewardConfig.isSplit).toBe(false);
    expect(result.part2RewardConfig.q9ToQ11Set).toBe(
      result.part2RewardConfig.q12ToQ14Set,
    );
  });

  it("collapses collaborative Q1 + challenge Q2 to true challenge", () => {
    const result = resolveAesthetic(
      AestheticCategory.COLLABORATIVE,
      AestheticCategory.CHALLENGE,
    );
    expect(result.isTrueAesthetic).toBe(true);
    expect(result.dominantAesthetic).toBe(AestheticCategory.CHALLENGE);
    expect(result.part1ChallengeSet).toBe(QuestionSetId.SET_1D);
  });

  it("collapses narrative Q1 + collaborative Q2 to true narrative", () => {
    const result = resolveAesthetic(
      AestheticCategory.NARRATIVE,
      AestheticCategory.COLLABORATIVE,
    );
    expect(result.isTrueAesthetic).toBe(true);
    expect(result.dominantAesthetic).toBe(AestheticCategory.NARRATIVE);
    expect(result.part1ChallengeSet).toBe(QuestionSetId.SET_1C);
  });

  it("collapses fantasy Q1 + none Q2 to true fantasy", () => {
    const result = resolveAesthetic(
      AestheticCategory.FANTASY,
      AestheticCategory.NONE,
    );
    expect(result.isTrueAesthetic).toBe(true);
    expect(result.dominantAesthetic).toBe(AestheticCategory.FANTASY);
    expect(result.part1ChallengeSet).toBe(QuestionSetId.SET_1B);
  });
});

describe("resolveAesthetic — hybrid 50/50 split", () => {
  it("routes sensory + fantasy to dominant 1A with a 2B/2A split", () => {
    const result = resolveAesthetic(
      AestheticCategory.SENSORY,
      AestheticCategory.FANTASY,
    );
    expect(result.isTrueAesthetic).toBe(false);
    expect(result.dominantAesthetic).toBe(AestheticCategory.SENSORY);
    expect(result.secondaryAesthetic).toBe(AestheticCategory.FANTASY);
    expect(result.part1ChallengeSet).toBe(QuestionSetId.SET_1A);
    expect(result.part2RewardConfig).toEqual({
      isSplit: true,
      q9ToQ11Set: QuestionSetId.SET_2B,
      q12ToQ14Set: QuestionSetId.SET_2A,
    });
  });

  it("keeps Q1 dominant for every ordered canonical pair", () => {
    for (const cat1 of CANONICAL) {
      for (const cat2 of CANONICAL) {
        if (cat1 === cat2) continue;
        const result = resolveAesthetic(cat1, cat2);
        expect(result.dominantAesthetic).toBe(cat1);
        expect(result.secondaryAesthetic).toBe(cat2);
        expect(result.part2RewardConfig.isSplit).toBe(true);
        expect(result.part2RewardConfig.q12ToQ14Set).toBe(PART2_SET_MAP[cat1]);
        expect(result.part2RewardConfig.q9ToQ11Set).toBe(PART2_SET_MAP[cat2]);
      }
    }
  });
});

describe("resolveAesthetic — special flow", () => {
  it("flags collaborative + none as special flow", () => {
    const result = resolveAesthetic(
      AestheticCategory.COLLABORATIVE,
      AestheticCategory.NONE,
    );
    expect(result.isTrueAesthetic).toBe(false);
    expect(result.dominantAesthetic).toBe(AestheticCategory.SPECIAL_FLOW);
    expect(result.secondaryAesthetic).toBeNull();
    expect(result.part1ChallengeSet).toBe(QuestionSetId.SPECIAL);
    expect(result.part2RewardConfig.q9ToQ11Set).toBe(QuestionSetId.SPECIAL);
    expect(result.part2RewardConfig.q12ToQ14Set).toBe(QuestionSetId.SPECIAL);
  });

  it("rejects unrepresentable category pairs", () => {
    expect(() =>
      resolveAesthetic(
        AestheticCategory.COLLABORATIVE,
        AestheticCategory.COLLABORATIVE,
      ),
    ).toThrow(UnresolvableAestheticError);
    expect(() =>
      resolveAesthetic(AestheticCategory.NONE, AestheticCategory.SENSORY),
    ).toThrow(UnresolvableAestheticError);
  });
});

describe("resolveFromOptions", () => {
  it("matches the category resolver for raw option identifiers", () => {
    expect(resolveFromOptions("OPT_S1", "OPT_F1")).toEqual(
      resolveAesthetic(AestheticCategory.SENSORY, AestheticCategory.FANTASY),
    );
    expect(resolveFromOptions("OPT_C1", "OPT_NONE")).toEqual(
      resolveAesthetic(AestheticCategory.CHALLENGE, AestheticCategory.NONE),
    );
  });

  it("rejects none in Q1, replayed Q1 options, and unknown options", () => {
    expect(() => resolveFromOptions("OPT_NONE", "OPT_S1")).toThrow(
      InvalidOptionSelectionError,
    );
    expect(() => resolveFromOptions("OPT_S1", "OPT_S1")).toThrow(
      InvalidOptionSelectionError,
    );
    expect(() => resolveFromOptions("OPT_BOGUS", "OPT_S1")).toThrow(
      UnknownOptionError,
    );
    expect(() => resolveFromOptions("OPT_S1", "OPT_BOGUS")).toThrow(
      UnknownOptionError,
    );
  });

  it("resolves every Q2 option offered after a collaborative Q1", () => {
    for (const option of availableSecondaryOptions("OPT_COL")) {
      const result = resolveFromOptions("OPT_COL", option.optionId);
      expect([...CANONICAL, AestheticCategory.SPECIAL_FLOW]).toContain(
        result.dominantAesthetic,
      );
    }
  });
});
