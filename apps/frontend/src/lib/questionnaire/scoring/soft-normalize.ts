/**
 * Live-preview "soft" normalization — SBGC-179.
 *
 * The accurate ratio normalizer (`normalizeProfile`) is exact but reads as
 * extreme while only a handful of answers have accumulated: a single +20-micro
 * answer normalizes to 100/0/0 and spikes the polygon straight to the outer
 * ring.  The live radar is a feedback aid, not the final result, so it blends
 * the accurate profile toward the neutral centre by how complete the part is.
 *
 * Convergence is exact at the end: confidence `1` returns the accurate profile
 * unchanged, and Q15 always plots the accurate normalized/adjusted vectors.
 */

import type { DimensionScore } from "./types";

/** The neutral centre the live preview starts from. */
export const NEUTRAL_PROFILE: DimensionScore = {
  micro: 33,
  macro: 33,
  mystiko: 34,
};

/** Progress-based confidence in `[0, 1]`; zero answers → fully neutral. */
export function previewConfidence(answered: number, total: number): number {
  if (total <= 0) return 0;
  return Math.max(0, Math.min(1, answered / total));
}

/** Blend an accurate profile toward neutral by `confidence` (0..1). */
export function softenProfile(
  profile: DimensionScore,
  confidence: number,
): DimensionScore {
  const t = Math.max(0, Math.min(1, confidence));
  const blend = (dimension: keyof DimensionScore): number =>
    Math.round(profile[dimension] * t + NEUTRAL_PROFILE[dimension] * (1 - t));
  return {
    micro: blend("micro"),
    macro: blend("macro"),
    mystiko: blend("mystiko"),
  };
}
