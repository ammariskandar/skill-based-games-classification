/**
 * Scoring engine & Q15 compensation parity tests — SBGC-174.
 *
 * Mirrors the backend suite
 * (`apps/backend/classifications/tests/test_questionnaire_scoring.py`) so the
 * client live runtime and the authoritative server engine stay identical.
 */

import { describe, expect, it } from "vitest";

import {
  opt,
  question,
  type ProfileTarget,
  type QuestionNode,
} from "../registry/v1/types";
import { SET_A } from "../registry/v1/set-a";
import {
  applyProportionalCompensation,
  resolveQualitySpec,
} from "./compensation";
import { computeRawProfile, normalizeProfile } from "./engine";
import type { DimensionScore } from "./types";

const CHALLENGE: ProfileTarget = "CHALLENGE";
const REWARD: ProfileTarget = "REWARD";

function node(
  id: string,
  label: string,
  target: ProfileTarget,
  mods: { micro?: number; macro?: number; mystiko?: number },
): QuestionNode {
  return question(id, `${id} question`, [opt(label, mods)], { target });
}

function score(micro: number, macro: number, mystiko: number): DimensionScore {
  return { micro, macro, mystiko };
}

function optionId(node: QuestionNode, suffix: string): string {
  const option = node.options.find((candidate) =>
    candidate.id.endsWith(suffix),
  );
  if (option === undefined)
    throw new Error(`option ${suffix} not found on ${node.id}`);
  return option.id;
}

describe("computeRawProfile", () => {
  it("floors intermediate negative balances per step", () => {
    const nodes = [
      node("Q3", "plus", CHALLENGE, { micro: 10 }),
      node("Q4", "minus", CHALLENGE, { micro: -30 }),
      node("Q5", "plus", CHALLENGE, { micro: 20 }),
    ];
    const answers = Object.fromEntries(
      nodes.map((n) => [n.id, n.options[0].id]),
    );
    expect(computeRawProfile(answers, nodes, CHALLENGE)).toEqual(
      score(20, 0, 0),
    );
  });

  it("isolates challenge from reward", () => {
    const nodes = [...SET_A.part1Questions, ...SET_A.part2Questions];
    const q3 = SET_A.part1Questions.find((n) => n.id === "Q3") as QuestionNode;
    const q10 = SET_A.part2Questions.find(
      (n) => n.id === "Q10",
    ) as QuestionNode;
    const answers = {
      Q3: optionId(q3, "huge"),
      Q10: optionId(q10, "great_gameplay"),
    };
    expect(computeRawProfile(answers, nodes, CHALLENGE)).toEqual(
      score(20, 0, 0),
    );
    expect(computeRawProfile(answers, nodes, REWARD)).toEqual(score(90, 0, 0));
  });

  it("ignores unknown questions and options", () => {
    const nodes = [node("Q3", "plus", CHALLENGE, { micro: 10 })];
    const answers = { Q3: "Q3_bogus", Q99: "Q99_whatever" };
    expect(computeRawProfile(answers, nodes, CHALLENGE)).toEqual(
      score(0, 0, 0),
    );
  });
});

describe("normalizeProfile", () => {
  it("uses the zero-total fallback", () => {
    expect(normalizeProfile(score(0, 0, 0))).toEqual(score(33, 33, 34));
  });

  it("normalizes exact ratios without remainder", () => {
    expect(normalizeProfile(score(50, 25, 25))).toEqual(score(50, 25, 25));
  });

  it("breaks tied fractions in static Micro ≻ Macro ≻ Mystiko order", () => {
    expect(normalizeProfile(score(1, 1, 1))).toEqual(score(34, 33, 33));
  });

  it("gives the remainder to the largest fraction", () => {
    expect(normalizeProfile(score(10, 7, 3))).toEqual(score(50, 35, 15));
    expect(normalizeProfile(score(1, 2, 3))).toEqual(score(17, 33, 50));
  });

  it("always sums to 100", () => {
    for (const raw of [
      score(0, 1, 0),
      score(99, 1, 0),
      score(7, 7, 7),
      score(1, 1, 1),
      score(500, 1, 1),
    ]) {
      const normalized = normalizeProfile(raw);
      expect(normalized.micro + normalized.macro + normalized.mystiko).toBe(
        100,
      );
    }
  });
});

describe("resolveQualitySpec", () => {
  it("maps rating bands to permitted deltas", () => {
    expect(resolveQualitySpec(1).permittedDelta).toBe(90);
    expect(resolveQualitySpec(3).permittedDelta).toBe(90);
    expect(resolveQualitySpec(4).permittedDelta).toBe(30);
    expect(resolveQualitySpec(5).permittedDelta).toBe(30);
    expect(resolveQualitySpec(6).permittedDelta).toBe(10);
    expect(resolveQualitySpec(7).permittedDelta).toBe(10);
    expect(resolveQualitySpec(8).permittedDelta).toBe(5);
    expect(resolveQualitySpec(9).permittedDelta).toBe(5);
    expect(resolveQualitySpec(10).permittedDelta).toBe(1);
  });

  it("rejects out-of-range ratings", () => {
    for (const rating of [0, 11, -1]) {
      expect(() => resolveQualitySpec(rating)).toThrow();
    }
  });
});

describe("applyProportionalCompensation", () => {
  it("reduces companions proportionally", () => {
    expect(
      applyProportionalCompensation(score(60, 20, 20), "micro", 70, 7),
    ).toEqual(score(70, 15, 15));
  });

  it("splits a zero companion base evenly", () => {
    expect(
      applyProportionalCompensation(score(100, 0, 0), "micro", 90, 7),
    ).toEqual(score(90, 5, 5));
  });

  it("contains boundaries and preserves the 100-point total", () => {
    const result = applyProportionalCompensation(
      score(50, 48, 2),
      "micro",
      70,
      1,
    );
    expect(result).toEqual(score(70, 29, 1));
    expect(result.micro + result.macro + result.mystiko).toBe(100);
  });

  it("returns the baseline on a zero delta", () => {
    const baseline = score(40, 30, 30);
    expect(applyProportionalCompensation(baseline, "micro", 40, 10)).toBe(
      baseline,
    );
  });

  it("clamps the target into the quality window", () => {
    expect(
      applyProportionalCompensation(score(50, 25, 25), "micro", 100, 10).micro,
    ).toBe(51);
  });

  it("always sums to 100 and stays bounded", () => {
    const cases: Array<[DimensionScore, keyof DimensionScore, number, number]> =
      [
        [score(60, 20, 20), "micro", 70, 7],
        [score(60, 20, 20), "micro", 10, 7],
        [score(0, 0, 100), "mystiko", 10, 1],
        [score(33, 33, 34), "macro", 100, 1],
        [score(90, 5, 5), "micro", 0, 1],
        [score(1, 1, 98), "mystiko", 98, 10],
      ];
    for (const [base, dimension, target, rating] of cases) {
      const result = applyProportionalCompensation(
        base,
        dimension,
        target,
        rating,
      );
      expect(result.micro + result.macro + result.mystiko).toBe(100);
      for (const value of [result.micro, result.macro, result.mystiko]) {
        expect(value).toBeGreaterThanOrEqual(0);
        expect(value).toBeLessThanOrEqual(100);
      }
    }
  });

  it("rejects unknown dimensions", () => {
    expect(() =>
      applyProportionalCompensation(
        score(60, 20, 20),
        "unknown" as never,
        70,
        7,
      ),
    ).toThrow();
  });
});
