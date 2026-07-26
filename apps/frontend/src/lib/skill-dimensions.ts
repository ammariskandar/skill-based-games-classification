/** Canonical skill-dimension definitions.  Single source of truth for
 * labels, order, descriptions, tokens, and display-level validation. */

export const DIMENSION_IDS = ["micro", "mystiko", "macro"] as const;
export type DimensionId = (typeof DIMENSION_IDS)[number];

export const PROFILE_TYPES = ["challenge", "reward"] as const;
export type ProfileType = (typeof PROFILE_TYPES)[number];

export interface DimensionDef {
  id: DimensionId;
  label: string;
  description: string;
  /** Tailwind CSS 4 theme colour token (e.g. "bg-blue", "text-green") */
  token: string;
  /** Non-colour symbol for accessible identification */
  symbol: string;
}

export const DIMENSIONS: Record<DimensionId, DimensionDef> = {
  micro: {
    id: "micro",
    label: "Micro",
    description:
      "Execution, mechanics, timing, precision, and moment-to-moment control.",
    token: "micro",
    symbol: "◆",
  },
  mystiko: {
    id: "mystiko",
    label: "Mystiko",
    description:
      "Hidden information, probability, mind games, prediction, and adaptation under uncertainty.",
    token: "mystiko",
    symbol: "◈",
  },
  macro: {
    id: "macro",
    label: "Macro",
    description:
      "Systems knowledge, resource management, planning, and long-horizon strategy.",
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
