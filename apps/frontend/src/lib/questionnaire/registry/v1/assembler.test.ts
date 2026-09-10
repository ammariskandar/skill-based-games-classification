/**
 * Versioned questionnaire registry & hybrid assembler tests — SBGC-173.
 *
 * Mirrors the backend suite
 * (`apps/backend/classifications/tests/test_questionnaire_registry.py`): graph
 * invariants, the 16-aesthetic permutation matrix, scoring-modifier fidelity
 * anchors, and the hybrid branch-preservation contract.
 */

import { describe, expect, it } from "vitest";

import { AestheticCategory, resolveAesthetic } from "../../aesthetic-taxonomy";
import {
  DOMINANT_PART2_ROOTS,
  REGISTRY_MAP,
  SECONDARY_PART2_ROOTS,
  assembleQuestionnaire,
} from "./assembler";
import { SET_A } from "./set-a";
import { SET_B } from "./set-b";
import { SET_C } from "./set-c";
import { SET_D } from "./set-d";
import {
  REGISTRY_VERSION,
  QuestionRegistryError,
  buildSet,
  opt,
  question,
  validateQuestionSet,
  type QuestionNode,
  type QuestionSetDefinition,
  type ScoreModifier,
} from "./types";

const ALL_SETS = [SET_A, SET_B, SET_C, SET_D];
const CANONICAL = [
  AestheticCategory.SENSORY,
  AestheticCategory.FANTASY,
  AestheticCategory.NARRATIVE,
  AestheticCategory.CHALLENGE,
];
const PART1_ROOT_IDS = ["Q3", "Q4", "Q5", "Q6", "Q7", "Q8"];
const PART2_ROOT_IDS = ["Q9", "Q10", "Q11", "Q12", "Q13", "Q14"];

function distinctRootIds(nodes: readonly QuestionNode[]): string[] {
  const seen: string[] = [];
  for (const node of nodes) {
    if (!seen.includes(node.rootId)) seen.push(node.rootId);
  }
  return seen;
}

function nodeById(nodes: readonly QuestionNode[], id: string): QuestionNode {
  const found = nodes.find((node) => node.id === id);
  if (found === undefined) throw new Error(`node '${id}' not found`);
  return found;
}

function optionModifier(
  definition: QuestionSetDefinition,
  nodeId: string,
  suffix: string,
): ScoreModifier {
  const node = nodeById(
    [...definition.part1Questions, ...definition.part2Questions],
    nodeId,
  );
  const option = node.options.find((candidate) =>
    candidate.id.endsWith(suffix),
  );
  if (option === undefined)
    throw new Error(`option ${suffix} not found on ${nodeId}`);
  return option.modifiers;
}

describe("registry structure", () => {
  it("gives every set six Part 1 and six Part 2 roots", () => {
    for (const definition of ALL_SETS) {
      expect(
        distinctRootIds(definition.part1Questions),
        definition.setId,
      ).toEqual(PART1_ROOT_IDS);
      expect(
        distinctRootIds(definition.part2Questions),
        definition.setId,
      ).toEqual(PART2_ROOT_IDS);
    }
  });

  it("keeps target integrity across both parts", () => {
    for (const definition of ALL_SETS) {
      for (const node of definition.part1Questions) {
        expect(node.target, node.id).toBe("CHALLENGE");
      }
      for (const node of definition.part2Questions) {
        expect(node.target, node.id).toBe("REWARD");
      }
    }
  });

  it("uses unique option ids within a set", () => {
    for (const definition of ALL_SETS) {
      const ids: string[] = [];
      for (const node of [
        ...definition.part1Questions,
        ...definition.part2Questions,
      ]) {
        expect(node.options.length, node.id).toBeGreaterThan(0);
        ids.push(...node.options.map((option) => option.id));
      }
      expect(new Set(ids).size).toBe(ids.length);
    }
  });

  it("has no dangling targets and no profile crossings", () => {
    for (const definition of ALL_SETS) {
      for (const part of [
        definition.part1Questions,
        definition.part2Questions,
      ]) {
        const byId = new Map(part.map((node) => [node.id, node]));
        for (const node of part) {
          for (const option of node.options) {
            if (option.nextQuestionId === null) continue;
            const target = byId.get(option.nextQuestionId);
            expect(
              target,
              `${node.id} -> ${option.nextQuestionId}`,
            ).toBeDefined();
            expect(target?.target).toBe(node.target);
          }
        }
      }
    }
  });

  it("never terminates on a branch cycle", () => {
    for (const definition of ALL_SETS) {
      for (const part of [
        definition.part1Questions,
        definition.part2Questions,
      ]) {
        const byId = new Map(part.map((node) => [node.id, node]));
        const roots = part
          .filter((node) => !node.isBranch)
          .map((node) => node.id);
        const seen = new Set<string>();
        const frontier = [...roots];
        let steps = 0;
        const limit = part.length * part.length + 1;
        while (frontier.length > 0) {
          steps += 1;
          expect(steps).toBeLessThan(limit);
          const current = frontier.pop() as string;
          if (seen.has(current)) continue;
          seen.add(current);
          for (const option of byId.get(current)?.options ?? []) {
            if (option.nextQuestionId !== null)
              frontier.push(option.nextQuestionId);
          }
        }
      }
    }
  });

  it("keeps branch nodes with their root", () => {
    for (const definition of ALL_SETS) {
      for (const node of [
        ...definition.part1Questions,
        ...definition.part2Questions,
      ]) {
        if (node.isBranch) {
          expect(node.id).not.toBe(node.rootId);
          expect(node.id.startsWith(node.rootId)).toBe(true);
        }
      }
    }
  });

  it("rejects a dangling branch target", () => {
    const q3 = nodeById(SET_A.part1Questions, "Q3");
    const brokenQ3: QuestionNode = {
      ...q3,
      options: [
        { ...q3.options[0], nextQuestionId: "Q99" },
        ...q3.options.slice(1),
      ],
    };
    // Bypass buildSet so the already-invalid definition reaches validation.
    const broken: QuestionSetDefinition = {
      version: REGISTRY_VERSION,
      setId: "A",
      name: "Sensory",
      part1Questions: [
        brokenQ3,
        ...SET_A.part1Questions.filter((node) => node.id !== "Q3"),
      ],
      part2Questions: SET_A.part2Questions,
    };
    expect(() => validateQuestionSet(broken)).toThrow(QuestionRegistryError);
  });

  it("throws when constructing an invalid set", () => {
    expect(() =>
      buildSet(
        "B",
        "Fantasy",
        [
          question("Q3", "Broken", [opt("Only", { next: "Q99" })], {
            target: "CHALLENGE",
          }),
        ],
        [],
      ),
    ).toThrow(QuestionRegistryError);
  });
});

describe("scoring modifier fidelity", () => {
  it("matches the backend anchors", () => {
    expect(optionModifier(SET_A, "Q3", "huge")).toEqual({
      micro: 20,
      macro: 0,
      mystiko: 0,
    });
    expect(optionModifier(SET_A, "Q7", "no_opponents")).toEqual({
      micro: 0,
      macro: 0,
      mystiko: -100,
    });
    expect(optionModifier(SET_A, "Q11A", "yes")).toEqual({
      micro: 0,
      macro: 0,
      mystiko: 200,
    });
    expect(optionModifier(SET_A, "Q14", "cheaters")).toEqual({
      micro: 30,
      macro: 60,
      mystiko: 0,
    });
    expect(optionModifier(SET_B, "Q3", "frame_perfect")).toEqual({
      micro: 85,
      macro: 0,
      mystiko: 0,
    });
    expect(optionModifier(SET_B, "Q10", "vistas_score")).toEqual({
      micro: 0,
      macro: 0,
      mystiko: 120,
    });
    expect(optionModifier(SET_C, "Q3", "gunplay_reflexes")).toEqual({
      micro: 75,
      macro: 0,
      mystiko: 0,
    });
    expect(optionModifier(SET_C, "Q6B", "unoptimized_party")).toEqual({
      micro: 0,
      macro: 75,
      mystiko: 15,
    });
    expect(optionModifier(SET_D, "Q4B", "static_maps")).toEqual({
      micro: 70,
      macro: -40,
      mystiko: 15,
    });
    expect(optionModifier(SET_D, "Q7", "three_way_synergy")).toEqual({
      micro: 35,
      macro: 35,
      mystiko: 35,
    });
  });

  it("pins the registry version", () => {
    for (const definition of ALL_SETS) {
      expect(definition.version).toBe(REGISTRY_VERSION);
    }
    expect(REGISTRY_VERSION).toBe("v1.0.0");
  });
});

describe("hybrid assembler", () => {
  it("registers all four canonical aesthetics", () => {
    expect(Object.keys(REGISTRY_MAP).sort()).toEqual([...CANONICAL].sort());
  });

  it("uses the dominant set for both parts of a true aesthetic", () => {
    for (const category of CANONICAL) {
      const definition = REGISTRY_MAP[category];
      const assembled = assembleQuestionnaire(
        resolveAesthetic(category, category),
      );
      expect(assembled.version).toBe(REGISTRY_VERSION);
      expect(assembled.isTrueAesthetic).toBe(true);
      expect(assembled.dominantAesthetic).toBe(category);
      expect(assembled.secondaryAesthetic).toBeNull();
      expect(assembled.part1ChallengeNodes.map((n) => n.id)).toEqual(
        definition.part1Questions.map((n) => n.id),
      );
      expect(assembled.part2RewardNodes.map((n) => n.id)).toEqual(
        definition.part2Questions.map((n) => n.id),
      );
    }
  });

  it("covers all sixteen aesthetics with the 50/50 split", () => {
    let tested = 0;
    for (const cat1 of CANONICAL) {
      for (const cat2 of CANONICAL) {
        tested += 1;
        const dominantDef = REGISTRY_MAP[cat1];
        const assembled = assembleQuestionnaire(resolveAesthetic(cat1, cat2));

        expect(distinctRootIds(assembled.part1ChallengeNodes)).toEqual(
          PART1_ROOT_IDS,
        );
        expect(assembled.part1ChallengeNodes.map((n) => n.id)).toEqual(
          dominantDef.part1Questions.map((n) => n.id),
        );

        if (cat1 === cat2) {
          expect(assembled.isTrueAesthetic).toBe(true);
          continue;
        }

        const secondaryDef = REGISTRY_MAP[cat2];
        expect(assembled.isTrueAesthetic).toBe(false);
        expect(distinctRootIds(assembled.part2RewardNodes)).toEqual(
          PART2_ROOT_IDS,
        );
        expect(distinctRootIds(assembled.part2RewardNodes).slice(0, 3)).toEqual(
          [...SECONDARY_PART2_ROOTS],
        );
        expect(distinctRootIds(assembled.part2RewardNodes).slice(3)).toEqual([
          ...DOMINANT_PART2_ROOTS,
        ]);
        const expectedIds = [
          ...secondaryDef.part2Questions
            .filter((n) => SECONDARY_PART2_ROOTS.includes(n.rootId))
            .map((n) => n.id),
          ...dominantDef.part2Questions
            .filter((n) => DOMINANT_PART2_ROOTS.includes(n.rootId))
            .map((n) => n.id),
        ];
        expect(assembled.part2RewardNodes.map((n) => n.id)).toEqual(
          expectedIds,
        );
      }
    }
    expect(tested).toBe(16);
  });

  it("keeps child branches with their roots in a hybrid", () => {
    const assembled = assembleQuestionnaire(
      resolveAesthetic(AestheticCategory.SENSORY, AestheticCategory.FANTASY),
    );
    const ids = assembled.part2RewardNodes.map((n) => n.id);
    // Q9A comes from Fantasy (SET_B); Q13A/Q13B from Sensory (SET_A).
    expect(nodeById(assembled.part2RewardNodes, "Q9A").text).toBe(
      "How do you prefer to acquire them?",
    );
    expect(ids).toContain("Q13A");
    expect(ids).toContain("Q13B");
    expect(ids).not.toContain("Q11B");
  });

  it("cannot assemble the special-flow outcome", () => {
    const resolution = resolveAesthetic(
      AestheticCategory.COLLABORATIVE,
      AestheticCategory.NONE,
    );
    expect(() => assembleQuestionnaire(resolution)).toThrow(
      QuestionRegistryError,
    );
  });
});
