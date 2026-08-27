/** Canonical skill-dimension definitions.  Single source of truth for
 * labels, order, descriptions, tokens, and display-level validation. */

export const DIMENSION_IDS = ["micro", "mystiko", "macro"] as const;
export type DimensionId = (typeof DIMENSION_IDS)[number];

export const PROFILE_TYPES = ["challenge", "reward"] as const;
export type ProfileType = (typeof PROFILE_TYPES)[number];

/** Canonical profile-axis name used by the dual-profile radar (SBGC-85). */
export type SkillProfileKind = ProfileType;

export interface DimensionDef {
  id: DimensionId;
  label: string;
  /** Tailwind CSS 4 theme colour token (e.g. "bg-blue", "text-green") */
  token: string;
  /** Non-colour symbol for accessible identification */
  symbol: string;
}

export const DIMENSIONS: Record<DimensionId, DimensionDef> = {
  micro: {
    id: "micro",
    label: "Micro",
    token: "micro",
    symbol: "◆",
  },
  mystiko: {
    id: "mystiko",
    label: "Mystiko",
    token: "mystiko",
    symbol: "◈",
  },
  macro: {
    id: "macro",
    label: "Macro",
    token: "macro",
    symbol: "⬟",
  },
};

export const DIMENSION_LIST: DimensionDef[] = DIMENSION_IDS.map(
  (id) => DIMENSIONS[id],
);

/** Static literal class names — required by Tailwind 4 source scanning.
 * Interpolated `text-${id}` strings are not statically detectable. */
export const DIMENSION_TEXT_CLASSES: Record<DimensionId, string> = {
  micro: "text-(--color-micro)",
  mystiko: "text-(--color-mystiko)",
  macro: "text-(--color-macro)",
} as const;

export const DIMENSION_BG_CLASSES: Record<DimensionId, string> = {
  micro: "bg-(--color-micro)",
  mystiko: "bg-(--color-mystiko)",
  macro: "bg-(--color-macro)",
} as const;

/* ── profile-dependent explanatory descriptions ── */

/** Authoritative explanatory copy: 3 Challenge + 3 Reward meanings.  Labels,
 * symbols, colours, and order are shared across profiles; only the semantics
 * are profile-aware (`description = f(profile, dimension)`). */
export const DIMENSION_DESCRIPTIONS: Record<
  ProfileType,
  Record<DimensionId, string>
> = {
  challenge: {
    micro:
      "Fine motor execution, reflexes, precision, timing, and mechanical dexterity.",
    mystiko:
      "Decision-making under uncertainty, hidden information, tactical adaptation, and situational awareness.",
    macro:
      "High-level strategy, resource management, long-term planning, and systemic foresight.",
  },
  reward: {
    micro:
      "Kinetic satisfaction, sensory feedback, mechanical mastery, and reflex execution payoff.",
    mystiko:
      "Discovery, tactical outplay, deduction, puzzle resolution, and out-adapting opponents.",
    macro:
      "Strategic triumph, realization of long-term planning, economic dominance, and grand victory.",
  },
};

/** Resolve the explanatory description for a profile × dimension. */
export function getDimensionDescription(
  profile: ProfileType,
  dimension: DimensionId,
): string {
  return DIMENSION_DESCRIPTIONS[profile][dimension];
}

/* ── typed presentation data ── */

export interface SkillProfile {
  type: ProfileType;
  micro: number;
  mystiko: number;
  macro: number;
  title?: string;
  description?: string;
  source?: string;
}

/* ── presentation-level validation ── */

export interface ValidationError {
  field: string;
  message: string;
}

export function validateProfile(
  profile: Partial<SkillProfile>,
): ValidationError[] {
  const errors: ValidationError[] = [];

  if (!profile.type || !PROFILE_TYPES.includes(profile.type)) {
    errors.push({
      field: "type",
      message: `type must be one of: ${PROFILE_TYPES.join(", ")}`,
    });
  }

  for (const id of DIMENSION_IDS) {
    const val = profile[id];
    if (val === undefined || val === null) {
      errors.push({ field: id, message: `${id} is required` });
    } else if (typeof val !== "number" || !Number.isFinite(val)) {
      errors.push({ field: id, message: `${id} must be a number` });
    } else if (!Number.isInteger(val)) {
      errors.push({ field: id, message: `${id} must be an integer` });
    } else if (val < 0 || val > 100) {
      errors.push({
        field: id,
        message: `${id} must be between 0 and 100 (got ${val})`,
      });
    }
  }

  if (
    typeof profile.micro === "number" &&
    typeof profile.mystiko === "number" &&
    typeof profile.macro === "number" &&
    Number.isFinite(profile.micro) &&
    Number.isFinite(profile.mystiko) &&
    Number.isFinite(profile.macro) &&
    profile.micro + profile.mystiko + profile.macro !== 100
  ) {
    errors.push({
      field: "total",
      message: `total must equal 100 (got ${profile.micro + profile.mystiko + profile.macro})`,
    });
  }

  return errors;
}

export function isValidProfile(
  profile: Partial<SkillProfile>,
): profile is SkillProfile {
  return validateProfile(profile).length === 0;
}

/** A validated three-component skill vector (micro, mystiko, macro). */
export interface SkillProfileVector {
  micro: number;
  mystiko: number;
  macro: number;
}

/** Discriminated result of strict runtime skill-profile validation. */
export type SkillProfileValidation =
  { ok: true; value: SkillProfileVector } | { ok: false; reason: string };

/**
 * Strictly validate a raw untrusted value as a skill-profile vector (SBGC-163).
 *
 * Accepts only a plain, non-array object whose ``micro``, ``mystiko``, and
 * ``macro`` fields are finite integers in ``[0, 100]`` summing to exactly 100.
 * Extra keys are ignored.  This fails closed — it never coerces, scales, or
 * repairs malformed data.
 */
export function validateSkillProfile(input: unknown): SkillProfileValidation {
  if (typeof input !== "object" || input === null || Array.isArray(input)) {
    return { ok: false, reason: "must be a profile object" };
  }

  const record = input as Record<string, unknown>;
  for (const key of DIMENSION_IDS) {
    const value = record[key];
    if (
      typeof value !== "number" ||
      !Number.isFinite(value) ||
      !Number.isInteger(value) ||
      value < 0 ||
      value > 100
    ) {
      return {
        ok: false,
        reason: `${key} must be an integer between 0 and 100`,
      };
    }
  }

  const total =
    (record.micro as number) +
    (record.mystiko as number) +
    (record.macro as number);
  if (total !== 100) {
    return { ok: false, reason: `scores must sum to 100 (got ${total})` };
  }

  return {
    ok: true,
    value: {
      micro: record.micro as number,
      mystiko: record.mystiko as number,
      macro: record.macro as number,
    },
  };
}

/* ── radar accessibility helpers (SBGC-86) ── */

export interface RadarSummaryRow {
  profile: SkillProfileKind;
  label: string;
  micro: number;
  mystiko: number;
  macro: number;
}

/** Human-readable radar vertex/tooltip label, e.g. "Challenge Micro". */
export function buildVertexLabel(
  kind: SkillProfileKind,
  dimension: DimensionId,
): string {
  const profile = kind.charAt(0).toUpperCase() + kind.slice(1);
  return `${profile} ${DIMENSIONS[dimension].label}`;
}

/** Screen-reader label for a focusable radar vertex, e.g. "Challenge Micro: 45". */
export function buildVertexAriaLabel(
  kind: SkillProfileKind,
  dimension: DimensionId,
  score: number,
): string {
  return `${buildVertexLabel(kind, dimension)}: ${score}`;
}

/** Accessible `<title>` text for the radar SVG. */
export function buildRadarTitle(gameTitle?: string): string {
  return gameTitle
    ? `${gameTitle} Skill Classification Radar`
    : "Skill Classification Radar Chart";
}

/** Accessible `<desc>` text summarising the available profiles and scores. */
export function buildRadarDescription(
  challenge: SkillProfileVector | null,
  reward: SkillProfileVector | null,
): string {
  const parts: string[] = [];
  if (challenge) {
    parts.push(
      `Challenge profile (Micro: ${challenge.micro}, Mystiko: ${challenge.mystiko}, Macro: ${challenge.macro})`,
    );
  }
  if (reward) {
    parts.push(
      `Reward profile (Micro: ${reward.micro}, Mystiko: ${reward.mystiko}, Macro: ${reward.macro})`,
    );
  }
  if (parts.length === 0) {
    return "Radar chart with no available skill classification profiles.";
  }
  return `Radar chart depicting ${parts.join(" and ")}.`;
}

/** Structured rows for the visually-hidden screen-reader data table. */
export function buildRadarSummaryRows(
  challenge: SkillProfileVector | null,
  reward: SkillProfileVector | null,
): RadarSummaryRow[] {
  const rows: RadarSummaryRow[] = [];
  if (challenge) {
    rows.push({ profile: "challenge", label: "Challenge", ...challenge });
  }
  if (reward) {
    rows.push({ profile: "reward", label: "Reward", ...reward });
  }
  return rows;
}
