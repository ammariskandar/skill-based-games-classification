/**
 * Presentation-only helpers for the classification display (SBGC-73).
 *
 * Pure TypeScript — no fetch, no calculation, no Django domain policy.
 * The Django SBGC-71 DTO is authoritative; this module only shapes it for
 * rendering.
 */

import type {
  ClassificationProfile,
  ClassificationRegime,
  GameFinalClassification,
} from "./server/api/games";

/** Locked canonical display order. Never Micro/Mystiko/Macro, never sorted. */
export const CLASSIFICATION_DIMENSION_ORDER = [
  "micro",
  "macro",
  "mystiko",
] as const;

export type ClassificationDimension =
  (typeof CLASSIFICATION_DIMENSION_ORDER)[number];

const DIMENSION_LABELS: Record<ClassificationDimension, string> = {
  micro: "Micro",
  macro: "Macro",
  mystiko: "Mystiko",
};

export interface DimensionValue {
  key: ClassificationDimension;
  label: string;
  value: number;
}

/** Map a profile to labelled values in the locked display order. */
export function profileDimensions(
  profile: ClassificationProfile,
): DimensionValue[] {
  return CLASSIFICATION_DIMENSION_ORDER.map((key) => ({
    key,
    label: DIMENSION_LABELS[key],
    value: profile[key],
  }));
}

export type ClassificationPresentation =
  | { kind: "unavailable" }
  | {
      kind: "ready";
      challenge: ClassificationProfile;
      reward: ClassificationProfile;
      confidence: number | null;
      confidenceLabel: string | null;
      regime: ClassificationRegime | null;
      isStale: boolean;
      submissionCount: number | null;
    };

/** Narrow a nullable classification into an unavailable or ready state. */
export function presentClassification(
  classification: GameFinalClassification | null,
): ClassificationPresentation {
  if (
    classification === null ||
    classification.challenge === null ||
    classification.reward === null
  ) {
    return { kind: "unavailable" };
  }
  return {
    kind: "ready",
    challenge: classification.challenge,
    reward: classification.reward,
    confidence: classification.confidence_level,
    confidenceLabel: classification.confidence_label,
    regime: classification.regime,
    isStale: classification.is_stale,
    submissionCount: classification.submission_count,
  };
}
