/**
 * Scoring accumulator & ratio normalizer — SBGC-174 (Epic SBGC-171).
 *
 * Mirrors `apps/backend/classifications/questionnaire/scoring/engine.py`.
 */

import type {
  AnswerOption,
  ProfileTarget,
  QuestionNode,
} from "../registry/v1/types";
import type { DimensionScore } from "./types";

const DIMENSION_PRIORITY: readonly (keyof DimensionScore)[] = [
  "micro",
  "macro",
  "mystiko",
];

/** Accumulate answers into a raw profile with per-step zero-flooring. */
export function computeRawProfile(
  answers: Record<string, string>,
  nodes: readonly QuestionNode[],
  target: ProfileTarget,
): DimensionScore {
  let micro = 0;
  let macro = 0;
  let mystiko = 0;

  const nodeMap = new Map(
    nodes
      .filter((node) => node.target === target)
      .map((node) => [node.id, node]),
  );

  for (const [questionId, optionId] of Object.entries(answers)) {
    const node = nodeMap.get(questionId);
    if (node === undefined) continue;
    const option: AnswerOption | undefined = node.options.find(
      (candidate) => candidate.id === optionId,
    );
    if (option === undefined) continue;

    micro = Math.max(0, micro + option.modifiers.micro);
    macro = Math.max(0, macro + option.modifiers.macro);
    mystiko = Math.max(0, mystiko + option.modifiers.mystiko);
  }

  return { micro, macro, mystiko };
}

/** Normalize a raw profile to a 100-point integer distribution (Largest Remainder). */
export function normalizeProfile(raw: DimensionScore): DimensionScore {
  const total = raw.micro + raw.macro + raw.mystiko;
  if (total === 0) {
    return { micro: 33, macro: 33, mystiko: 34 };
  }

  const values: Record<keyof DimensionScore, number> = {
    micro: raw.micro,
    macro: raw.macro,
    mystiko: raw.mystiko,
  };
  const exact: Record<keyof DimensionScore, number> = {
    micro: (values.micro / total) * 100,
    macro: (values.macro / total) * 100,
    mystiko: (values.mystiko / total) * 100,
  };
  const floors: Record<keyof DimensionScore, number> = {
    micro: Math.floor(exact.micro),
    macro: Math.floor(exact.macro),
    mystiko: Math.floor(exact.mystiko),
  };

  const remainder = 100 - (floors.micro + floors.macro + floors.mystiko);

  const fractions: Array<{
    fraction: number;
    raw: number;
    priority: number;
    dimension: keyof DimensionScore;
  }> = DIMENSION_PRIORITY.map((dimension, index) => ({
    fraction: exact[dimension] - floors[dimension],
    raw: values[dimension],
    priority: -index,
    dimension,
  }));

  // Descending by fraction, then raw magnitude, then static priority.
  fractions.sort(
    (a, b) =>
      b.fraction - a.fraction || b.raw - a.raw || b.priority - a.priority,
  );

  const allocations: Record<keyof DimensionScore, number> = { ...floors };
  for (let index = 0; index < remainder; index += 1) {
    allocations[fractions[index].dimension] += 1;
  }

  return {
    micro: allocations.micro,
    macro: allocations.macro,
    mystiko: allocations.mystiko,
  };
}
