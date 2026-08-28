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
} from "./server/api/games";
import { validateSkillProfile } from "./skill-dimensions";

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

/* ── dominant-dimension presentation (SBGC-208) ──────────────────────────── */

export type DominantDimension = "micro" | "mystiko" | "macro";

/**
 * Resolve the dominant skill dimension for a ranking profile from the
 * published classification vectors (SBGC-208).
 *
 * Mirrors the backend's strictly-highest dominance semantics (SBGC-81): a tie
 * for the top score is *no* dominant, and Unified reads the summed Challenge +
 * Reward dimensions.  Missing required vectors resolve to ``null`` (never a
 * fabricated dimension).  This is presentation-only — no score is calculated
 * or persisted.
 */
export function dominantForProfile(
  profile: "unified" | "challenge" | "reward",
  challenge: ClassificationProfile | null,
  reward: ClassificationProfile | null,
): DominantDimension | null {
  if (profile === "challenge") {
    return challenge ? strictlyHighest(challenge) : null;
  }
  if (profile === "reward") {
    return reward ? strictlyHighest(reward) : null;
  }
  if (challenge === null || reward === null) return null;
  return strictlyHighest({
    micro: challenge.micro + reward.micro,
    macro: challenge.macro + reward.macro,
    mystiko: challenge.mystiko + reward.mystiko,
  });
}

function strictlyHighest(values: {
  micro: number;
  macro: number;
  mystiko: number;
}): DominantDimension | null {
  const ordered: Array<[DominantDimension, number]> = [
    ["micro", values.micro],
    ["macro", values.macro],
    ["mystiko", values.mystiko],
  ];
  const top = Math.max(...ordered.map(([, value]) => value));
  const winners = ordered.filter(([, value]) => value === top);
  return winners.length === 1 ? winners[0][0] : null;
}

/**
 * Static badge markup shared by the SSR detail pane and the client-side
 * re-render, so the runtime DOM never drifts from the server markup.
 * Copy is fixed and vetted — never interpolates user data.
 */
export function dominantBadgeHtml(
  dominant: DominantDimension | null,
  classified: boolean,
): string {
  if (!classified) {
    return `<span class="rankings-detail__dominant-empty">Not yet classified</span>`;
  }
  if (dominant === null) {
    return `<span class="rankings-detail__dominant-empty">No dominant dimension</span>`;
  }
  return `<span class="rankings-detail__dominant-badge rankings-detail__dominant-badge--${dominant}">Dominant: ${DIMENSION_LABELS[dominant]}</span>`;
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
  raw: unknown,
  slug?: string,
): ClassificationPresentation {
  if (!isRecord(raw)) {
    return { kind: "unavailable" };
  }

  const challengeRaw = raw["challenge"];
  const rewardRaw = raw["reward"];

  // Missing profiles are the honest "not yet classified" state, not corruption
  // — fail closed without a warning.  Only non-null malformed vectors warn.
  if (challengeRaw == null || rewardRaw == null) {
    return { kind: "unavailable" };
  }

  const challenge = validateSkillProfile(challengeRaw);
  const reward = validateSkillProfile(rewardRaw);

  if (!challenge.ok) {
    warnMalformed(slug, "challenge", challenge.reason);
    return { kind: "unavailable" };
  }
  if (!reward.ok) {
    warnMalformed(slug, "reward", reward.reason);
    return { kind: "unavailable" };
  }

  return {
    kind: "ready",
    challenge: challenge.value,
    reward: reward.value,
    confidence: numberOrNull(raw["confidence_level"]),
    confidenceLabel: stringOrNull(raw["confidence_label"]),
    regime: asRegime(raw["regime"]),
    isStale: raw["is_stale"] === true,
    submissionCount: numberOrNull(raw["submission_count"]),
  };
}

function warnMalformed(
  slug: string | undefined,
  profile: string,
  reason: string,
): void {
  // Server-side diagnostic only — never leak malformed payload into markup.
  console.warn(
    `[classification] ${slug ?? "game"}: ${profile} profile invalid (${reason})`,
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asRegime(value: unknown): ClassificationRegime | null {
  return value === "provisional" || value === "unified" || value === "none"
    ? value
    : null;
}
