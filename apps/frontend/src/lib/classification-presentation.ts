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
      lead: "Games where fast reflexes and immediate tactile feedback take center stage.",
      sections: [
        {
          label: "The Skill Tested (Challenge)",
          text: "Demands sensorimotor execution—rapidly processing sensory cues (visual flashes, audio cues, controller vibrations) to execute precise physical inputs (flick shots, frame-perfect parries, rhythm timing, drift control, or combo chaining).",
        },
        {
          label: "The Fulfillment (Reward)",
          text: "Delivers instant, localized feedback that validates moment-to-moment mechanical mastery (crisp hitmarker sounds, killstreak announcements, lobby MVP badges, Play of the Game highlights, or round victories).",
        },
      ],
    },
    macro: {
      leadLabel: "Summary",
      lead: "Games where long-term planning, resource management, and systemic strategy determine success.",
      sections: [
        {
          label: "The Skill Tested (Challenge)",
          text: "Demands high-level oversight—managing economies, allocating talent points, optimizing build synergies, tracking team cooldowns, and adapting map-wide positioning.",
        },
        {
          label: "The Fulfillment (Reward)",
          text: "Delivers persistent, outward prestige and milestone accomplishments (climbing competitive ELO tiers, unlocking exclusive season skins, earning rare achievements, expanding an empire, or completing endgame progression trees).",
        },
      ],
    },
    mystiko: {
      leadLabel: "Summary",
      lead: "Games driven by hidden information, deduction, and outthinking opponents under uncertainty.",
      sections: [
        {
          label: "The Skill Tested (Challenge)",
          text: "Demands game sense and psychological reads—predicting enemy rotations through fog-of-war, seeing through bluffs, adapting to unpredictable card draws, and deducing invisible threats.",
        },
        {
          label: "The Fulfillment (Reward)",
          text: 'Delivers intrinsic, "invisible" satisfaction and creative validation (the dopamine rush of a correct blind read, executing an unorthodox counter-strategy, uncovering hidden lore, or discovering branching story consequences).',
        },
      ],
    },
  },
  challenge: {
    micro: {
      leadLabel: "Skill Focus",
      lead: "Fine motor execution, physical dexterity, and reaction time.",
      sections: [
        {
          label: "What It Tests",
          text: "How quickly and accurately your hands respond to what your eyes and ears perceive. Success relies on muscle memory, input precision, and millisecond decision-making.",
        },
        {
          label: "Examples in Action",
          text: "Snapping a sniper crosshair onto a target, timing a dodge through invulnerability frames, executing complex fighting game inputs, or staying on-beat in a rhythm game.",
        },
      ],
    },
    macro: {
      leadLabel: "Skill Focus",
      lead: "System management, tactical foresight, and economic efficiency.",
      sections: [
        {
          label: "What It Tests",
          text: "How effectively you manage systems, resources, and long-term plans. Success relies on identifying the optimal route to victory, spotting structural weaknesses in setups, and managing trade-offs.",
        },
        {
          label: "Examples in Action",
          text: "Balancing gold income versus military production in an RTS, managing team lane control and objective timers in a MOBA, crafting optimized gear builds, or setting up automated logistics in a simulation.",
        },
      ],
    },
    mystiko: {
      leadLabel: "Skill Focus",
      lead: "Deduction, pattern recognition, and game sense under uncertainty.",
      sections: [
        {
          label: "What It Tests",
          text: "How well you operate with incomplete information. Success relies on predicting what you cannot see, reading opponent habits, bluffing, and forecasting future game states.",
        },
        {
          label: "Examples in Action",
          text: "Throwing a skillshot into an unwarded brush based on intuition, calling an opponent's poker-style bluff in a card game, deducing the culprit in an investigative game, or preparing a counter-build before the enemy reveals their strategy.",
        },
      ],
    },
  },
  reward: {
    micro: {
      leadLabel: "Reward Type",
      lead: "Instant, tactile, and localized recognition.",
      sections: [
        {
          label: "How It Satisfies",
          text: "Rewards you immediately after an action with punchy audiovisual feedback and short-term match accolades that celebrate your mechanical execution.",
        },
        {
          label: "Examples in Action",
          text: "The ping of a headshot, high-combo multipliers, multi-kill banners, mid-match bounty claims, and earning match MVP in a lobby.",
        },
      ],
    },
    macro: {
      leadLabel: "Reward Type",
      lead: "Long-term, outward, and permanent prestige.",
      sections: [
        {
          label: "How It Satisfies",
          text: "Rewards you with tangible status symbols and macro-progression markers that demonstrate dedication and mastery over entire game systems.",
        },
        {
          label: "Examples in Action",
          text: "Displaying a Grandmaster/Diamond rank border, equipping rare cosmetics/mounts, unlocking 100% completion achievements, and leveling up an account or battle pass.",
        },
      ],
    },
    mystiko: {
      leadLabel: "Reward Type",
      lead: "Subtle, cerebral, and intrinsic fulfillment.",
      sections: [
        {
          label: "How It Satisfies",
          text: 'Rewards you with the internal gratification of outsmarting the game or your opponent—the quiet "feel-good factor" of executing a clever idea.',
        },
        {
          label: "Examples in Action",
          text: "The psychological high of winning purely on a mind game, watching an unorthodox trap spring shut, finding obscure secrets/easter eggs, or reaching a unique ending shaped by subtle earlier choices.",
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
