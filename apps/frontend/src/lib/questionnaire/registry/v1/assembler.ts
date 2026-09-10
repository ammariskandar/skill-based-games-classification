/**
 * Hybrid question assembler (v1.0.0) — SBGC-173.
 *
 * Mirrors
 * `apps/backend/classifications/questionnaire/registry/v1/assembler.py`.
 *
 * Part 1 (Challenge) is always the dominant set's Q3–Q8 plus branches.
 * Part 2 (Reward) is the dominant set's Q9–Q14 for a true aesthetic, or a
 * 50/50 split — Q9–Q11 from the secondary set, Q12–Q14 from the dominant set
 * — for a hybrid aesthetic.
 */

import {
  AestheticCategory,
  type AestheticResolution,
} from "../../aesthetic-taxonomy";
import { SET_A } from "./set-a";
import { SET_B } from "./set-b";
import { SET_C } from "./set-c";
import { SET_D } from "./set-d";
import {
  REGISTRY_VERSION,
  QuestionRegistryError,
  type AssembledQuestionnaire,
  type QuestionNode,
  type QuestionSetDefinition,
} from "./types";

export const REGISTRY_MAP: Record<string, QuestionSetDefinition> = {
  [AestheticCategory.SENSORY]: SET_A,
  [AestheticCategory.FANTASY]: SET_B,
  [AestheticCategory.NARRATIVE]: SET_C,
  [AestheticCategory.CHALLENGE]: SET_D,
};

/** Reward roots routed from the secondary set in a hybrid split. */
export const SECONDARY_PART2_ROOTS: readonly string[] = ["Q9", "Q10", "Q11"];

/** Reward roots routed from the dominant set in a hybrid split. */
export const DOMINANT_PART2_ROOTS: readonly string[] = ["Q12", "Q13", "Q14"];

function nodesForRoots(
  nodes: QuestionNode[],
  roots: readonly string[],
): QuestionNode[] {
  const wanted = new Set(roots);
  return nodes.filter((node) => wanted.has(node.rootId));
}

/** Assemble the concrete question graph for a resolved aesthetic. */
export function assembleQuestionnaire(
  resolution: AestheticResolution,
): AssembledQuestionnaire {
  const dominantCat = resolution.dominantAesthetic;
  const secondaryCat = resolution.secondaryAesthetic;

  const dominantDef = REGISTRY_MAP[dominantCat];
  if (dominantDef === undefined) {
    throw new QuestionRegistryError(
      `Cannot assemble questionnaire for dominant aesthetic ${dominantCat}.`,
    );
  }

  const part1ChallengeNodes = dominantDef.part1Questions;

  let part2RewardNodes: QuestionNode[];
  if (resolution.isTrueAesthetic || secondaryCat === null) {
    part2RewardNodes = dominantDef.part2Questions;
  } else {
    const secondaryDef = REGISTRY_MAP[secondaryCat];
    if (secondaryDef === undefined) {
      throw new QuestionRegistryError(
        `Cannot assemble hybrid questionnaire with secondary aesthetic ${secondaryCat}.`,
      );
    }
    part2RewardNodes = [
      ...nodesForRoots(secondaryDef.part2Questions, SECONDARY_PART2_ROOTS),
      ...nodesForRoots(dominantDef.part2Questions, DOMINANT_PART2_ROOTS),
    ];
  }

  return {
    version: REGISTRY_VERSION,
    dominantAesthetic: dominantCat,
    secondaryAesthetic: secondaryCat,
    isTrueAesthetic: resolution.isTrueAesthetic,
    part1ChallengeNodes,
    part2RewardNodes,
  };
}
