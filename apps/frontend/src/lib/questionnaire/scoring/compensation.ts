/**
 * Q15 coupled proportional compensation — SBGC-174 (Epic SBGC-171).
 *
 * Mirrors `apps/backend/classifications/questionnaire/scoring/compensation.py`.
 */

import type { DimensionScore, QualitySpec } from "./types";

export const QUALITY_TIER_MAP: Record<string, QualitySpec> = {
  "1-3": { tier: "LOW", permittedDelta: 90 },
  "4-5": { tier: "MODERATE", permittedDelta: 30 },
  "6-7": { tier: "HIGH", permittedDelta: 10 },
  "8-9": { tier: "VERY_HIGH", permittedDelta: 5 },
  "10-10": { tier: "PERFECT", permittedDelta: 1 },
};

const DIMENSIONS: readonly (keyof DimensionScore)[] = [
  "micro",
  "macro",
  "mystiko",
];

/** Return the quality spec for a Q15 rating in [1, 10]. */
export function resolveQualitySpec(rating: number): QualitySpec {
  if (rating < 1 || rating > 10) {
    throw new Error(`Q15 rating must be between 1 and 10, got ${rating}`);
  }
  for (const [band, spec] of Object.entries(QUALITY_TIER_MAP)) {
    const [low, high] = band.split("-").map(Number);
    if (rating >= low && rating <= high) {
      return spec;
    }
  }
  throw new Error(`Unhandled rating: ${rating}`);
}

/** Apply a coupled, quality-bounded slider adjustment to one dimension. */
export function applyProportionalCompensation(
  normalized: DimensionScore,
  activeDimension: keyof DimensionScore,
  targetValue: number,
  rating: number,
): DimensionScore {
  if (!DIMENSIONS.includes(activeDimension)) {
    throw new Error(`Unknown dimension '${activeDimension}'.`);
  }

  const spec = resolveQualitySpec(rating);
  const currentValue = normalized[activeDimension];

  // 1. Clamp the target into the permitted quality window.
  const minAllowed = Math.max(0, currentValue - spec.permittedDelta);
  const maxAllowed = Math.min(100, currentValue + spec.permittedDelta);
  const xNew = Math.max(minAllowed, Math.min(maxAllowed, targetValue));

  const deltaX = xNew - currentValue;
  if (deltaX === 0) return normalized;

  const companionKeys = DIMENSIONS.filter(
    (dimension) => dimension !== activeDimension,
  );
  const yKey = companionKeys[0];
  const zKey = companionKeys[1];
  const yBase = normalized[yKey];
  const zBase = normalized[zKey];

  const deltaBudget = -deltaX;

  // 2. Pass 1 — unconstrained proportional allocation.
  const yzSum = yBase + zBase;
  let deltaY: number;
  let deltaZ: number;
  if (yzSum === 0) {
    deltaY = deltaBudget / 2;
    deltaZ = deltaBudget / 2;
  } else {
    deltaY = deltaBudget * (yBase / yzSum);
    deltaZ = deltaBudget * (zBase / yzSum);
  }

  let yCandidate = yBase + deltaY;
  let zCandidate = zBase + deltaZ;

  // 3. Pass 2 — boundary overflow absorption.
  if (yCandidate < 0) {
    const excess = 0 - yCandidate;
    yCandidate = 0;
    zCandidate -= excess;
  } else if (yCandidate > 100) {
    const excess = yCandidate - 100;
    yCandidate = 100;
    zCandidate += excess;
  }

  if (zCandidate < 0) {
    const excess = 0 - zCandidate;
    zCandidate = 0;
    yCandidate -= excess;
  } else if (zCandidate > 100) {
    const excess = zCandidate - 100;
    zCandidate = 100;
    yCandidate += excess;
  }

  // 4. Pass 3 — integer discretization & remainder absorption.
  let yFloor = Math.floor(yCandidate);
  let zFloor = Math.floor(zCandidate);
  const residual = 100 - (xNew + yFloor + zFloor);

  const yRemainder = yCandidate - yFloor;
  const zRemainder = zCandidate - zFloor;

  if (residual > 0) {
    if ((yRemainder >= zRemainder && yFloor + 1 <= 100) || zFloor + 1 > 100) {
      yFloor += residual;
    } else {
      zFloor += residual;
    }
  } else if (residual < 0) {
    if ((yRemainder <= zRemainder && yFloor - 1 >= 0) || zFloor - 1 < 0) {
      yFloor += residual;
    } else {
      zFloor += residual;
    }
  }

  const result = {
    ...normalized,
    [activeDimension]: xNew,
    [yKey]: yFloor,
    [zKey]: zFloor,
  };
  return result;
}
