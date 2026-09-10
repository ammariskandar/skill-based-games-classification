/**
 * Scoring data contracts — SBGC-174 (Epic SBGC-171).
 *
 * Mirrors `apps/backend/classifications/questionnaire/scoring/types.py`.
 * Pure value types only.
 */

export type QualityTier = "LOW" | "MODERATE" | "HIGH" | "VERY_HIGH" | "PERFECT";

export interface DimensionScore {
  micro: number;
  macro: number;
  mystiko: number;
}

export interface QualitySpec {
  tier: QualityTier;
  permittedDelta: number;
}

export interface CalculatedProfilePair {
  raw: DimensionScore;
  normalized: DimensionScore;
  adjusted: DimensionScore;
}

export interface FullScoringResult {
  challenge: CalculatedProfilePair;
  reward: CalculatedProfilePair;
  q15Rating: number;
  qualitySpec: QualitySpec;
}

export function scoreTotal(score: DimensionScore): number {
  return score.micro + score.macro + score.mystiko;
}

export function dimensionScore(
  micro: number,
  macro: number,
  mystiko: number,
): DimensionScore {
  return { micro, macro, mystiko };
}
