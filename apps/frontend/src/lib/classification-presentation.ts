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

/* ── dominant explainer copy (SBGC-208) ──────────────────────────────────── */

export type DominantProfileKey = "unified" | "challenge" | "reward";

/** One labelled supporting section under the lead line. */
export interface DominantCopySection {
  label: string;
  text: string;
}

/**
 * The full explainer for one (profile, dominant dimension) state.
 * ``lead`` is the headline takeaway rendered a step larger than ``sections``
 * ("Summary" / "Skill Focus" / "Reward Type"); ``sections`` carry the
 * nuance: what the game demands, and why it feels rewarding.
 */
export interface DominantCopy {
  leadLabel: string;
  lead: string;
  sections: DominantCopySection[];
}

/**
 * Hard-coded explainer copy for all 9 dominant states (SBGC-208).
 *
 * Vetted static content — gamers who like a game but can't say why get a
 * fast, nuanced answer: what the game tests, and how it pays that effort off.
 * Never interpolates user data; safe to inject as markup.
 */
export const DOMINANT_COPY: Record<
  DominantProfileKey,
  Record<DominantDimension, DominantCopy>
> = {
  unified: {
    micro: {
      leadLabel: "Summary",
      lead: "Reflex and reaction games — the fun is in split-second execution.",
      sections: [
        {
          label: "The Skill Tested (Challenge)",
          text: "Reading the moment and acting instantly: flicks, frame-perfect parries, rhythm timing, drift control.",
        },
        {
          label: "The Fulfillment (Reward)",
          text: "Instant payoff — hitmarkers, killstreak popups, MVP badges, Play of the Game highlights.",
        },
      ],
    },
    macro: {
      leadLabel: "Summary",
      lead: "Strategy and planning games — the fun is in out-managing your opponent.",
      sections: [
        {
          label: "The Skill Tested (Challenge)",
          text: "Seeing the whole board: economy, builds, cooldowns, map-wide positioning.",
        },
        {
          label: "The Fulfillment (Reward)",
          text: "Lasting payoff — climbing ranks, rare skins, achievements, finishing a long progression.",
        },
      ],
    },
    mystiko: {
      leadLabel: "Summary",
      lead: "Mind-game games — the fun is in figuring out what you can't see.",
      sections: [
        {
          label: "The Skill Tested (Challenge)",
          text: "Reading intent: predicting rotations through fog-of-war, seeing bluffs, deducing threats.",
        },
        {
          label: "The Fulfillment (Reward)",
          text: "The rush of being right — a correct blind read, a trap that springs, hidden lore, secrets.",
        },
      ],
    },
  },
  challenge: {
    micro: {
      leadLabel: "Skill Focus",
      lead: "Hands — speed, precision, reflexes.",
      sections: [
        {
          label: "What It Tests",
          text: "How fast and accurate your inputs are when it matters.",
        },
        {
          label: "Examples in Action",
          text: "Sniper flicks, i-frame dodges, fighting-game combos, keeping the beat in rhythm games.",
        },
      ],
    },
    macro: {
      leadLabel: "Skill Focus",
      lead: "Mind — systems, resources, long-term plans.",
      sections: [
        {
          label: "What It Tests",
          text: "How well you see the path to victory and manage trade-offs.",
        },
        {
          label: "Examples in Action",
          text: "RTS economy vs. army, MOBA lane control, build crafting, factory logistics.",
        },
      ],
    },
    mystiko: {
      leadLabel: "Skill Focus",
      lead: "Reads — deduction and game sense under uncertainty.",
      sections: [
        {
          label: "What It Tests",
          text: "How well you predict what you can't see — play the player, not just the game.",
        },
        {
          label: "Examples in Action",
          text: "Skillshots into unwarded brush, calling bluffs, finding the culprit, counter-building blind.",
        },
      ],
    },
  },
  reward: {
    micro: {
      leadLabel: "Reward Type",
      lead: "Instant, tactile recognition.",
      sections: [
        {
          label: "How It Satisfies",
          text: "Every action gets a satisfying pop — you feel good the moment you do it.",
        },
        {
          label: "Examples in Action",
          text: "Headshot pings, combo multipliers, multi-kill banners, match MVP.",
        },
      ],
    },
    macro: {
      leadLabel: "Reward Type",
      lead: "Long-term, outward prestige.",
      sections: [
        {
          label: "How It Satisfies",
          text: "You can show off what you've built — proof of dedication.",
        },
        {
          label: "Examples in Action",
          text: "Rank borders, rare cosmetics, 100% achievements, battle-pass levels.",
        },
      ],
    },
    mystiko: {
      leadLabel: "Reward Type",
      lead: "Subtle, cerebral fulfillment.",
      sections: [
        {
          label: "How It Satisfies",
          text: "The quiet high of outsmarting someone — an idea that worked.",
        },
        {
          label: "Examples in Action",
          text: "Winning a mind game, a trap closing, finding secrets, unique endings.",
        },
      ],
    },
  },
};

/**
 * Full dominant-region markup: the badge (or truthful empty state) plus the
 * per-(profile, dimension) explainer copy.  Shared by the SSR pane and the
 * client-side re-render so both stay in lockstep.  Copy is static and vetted.
 */
export function dominantRegionHtml(
  profile: DominantProfileKey,
  dominant: DominantDimension | null,
  classified: boolean,
): string {
  const badge = dominantBadgeHtml(dominant, classified);
  if (dominant === null) return badge;
  const copy = DOMINANT_COPY[profile][dominant];
  const sections = copy.sections
    .map(
      (section) =>
        `<div class="rankings-detail__dominant-section"><span class="rankings-detail__dominant-section-label">${section.label}</span><p class="rankings-detail__dominant-section-text">${section.text}</p></div>`,
    )
    .join("");
  return `${badge}<div class="rankings-detail__dominant-copy"><span class="rankings-detail__dominant-section-label">${copy.leadLabel}</span><p class="rankings-detail__dominant-lead">${copy.lead}</p>${sections}</div>`;
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
