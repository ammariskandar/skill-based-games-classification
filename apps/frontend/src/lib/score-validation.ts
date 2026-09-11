/**
 * Sum-to-100 score validation — SBGC-215.
 *
 * Pure functions with zero framework dependencies. They own the only domain
 * invariant that matters for manual score submission: every dimension must be
 * an integer in [0, 100] and each profile must total exactly 100.
 */

import { isAestheticValue, isSecondaryAestheticValid } from "./aesthetics";

export interface ProfileScores {
  micro: number;
  mystiko: number;
  macro: number;
}

export interface SubmissionPayload {
  gameSlug: string;
  challenge: ProfileScores;
  reward: ProfileScores;
}

/** A single dimension value must be a whole number in the closed [0, 100]. */
export function validateDimensionValue(value: number): boolean {
  return Number.isInteger(value) && value >= 0 && value <= 100;
}

export function calculateProfileSum(scores: ProfileScores): number {
  return scores.micro + scores.mystiko + scores.macro;
}

export function isProfileValid(scores: ProfileScores): boolean {
  return (
    validateDimensionValue(scores.micro) &&
    validateDimensionValue(scores.mystiko) &&
    validateDimensionValue(scores.macro) &&
    calculateProfileSum(scores) === 100
  );
}

export function isSubmissionPayloadValid(payload: SubmissionPayload): boolean {
  return isProfileValid(payload.challenge) && isProfileValid(payload.reward);
}

/**
 * Manual-submission readiness: both profiles valid AND a canonical primary
 * aesthetic selected (SBGC-228).  The secondary aesthetic is optional but, when
 * set, must be canonical and differ from the primary.
 */
export function isManualSubmissionReady(
  challenge: ProfileScores,
  reward: ProfileScores,
  aesthetic: unknown,
  secondaryAesthetic: unknown = null,
): boolean {
  return (
    isProfileValid(challenge) &&
    isProfileValid(reward) &&
    isAestheticValue(aesthetic) &&
    isSecondaryAestheticValid(aesthetic, secondaryAesthetic)
  );
}
