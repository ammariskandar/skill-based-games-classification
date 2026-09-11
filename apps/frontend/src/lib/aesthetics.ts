/**
 * Canonical aesthetic vocabulary — SBGC-228.
 *
 * The four true aesthetics mirror the backend single source of truth
 * (`classifications/questionnaire/domain.py::AestheticCategory` and the
 * TypeScript taxonomy in `lib/questionnaire/types.ts`).  Values are the stored
 * canonical uppercase strings; labels and definitions are presentation copy for
 * the manual-submission picker and its accessible definition tooltip.
 */

export const AESTHETIC_VALUES = [
  "SENSORY",
  "FANTASY",
  "NARRATIVE",
  "CHALLENGE",
] as const;

export type AestheticValue = (typeof AESTHETIC_VALUES)[number];

export interface AestheticDefinition {
  value: AestheticValue;
  label: string;
  definition: string;
  examples: string;
}

export const AESTHETIC_DEFINITIONS: readonly AestheticDefinition[] = [
  {
    value: "SENSORY",
    label: "Sensory Pleasure",
    definition:
      "Immersion driven by audiovisual beauty, music, adrenaline-pumping action thrills, visceral horror, or relaxing therapeutic sensations.",
    examples: "Music, visual art, kinetics, terror, relaxation.",
  },
  {
    value: "FANTASY",
    label: "Fantasy Pleasure",
    definition:
      "Escapism through world exploration, role-playing, living an impossible life, building creations, or commanding empires.",
    examples: "RPGs, simulations, sandbox builders, exploration.",
  },
  {
    value: "NARRATIVE",
    label: "Narrative Pleasure",
    definition:
      "Deep player engagement driven by storytelling, character development, emotional arcs, drama, and world lore.",
    examples: "Story-rich adventures, visual novels, interactive fiction.",
  },
  {
    value: "CHALLENGE",
    label: "Challenge Pleasure",
    definition:
      "Fun derived strictly from overcoming difficulty, mechanical mastery, executing complex strategies, or setting competitive records.",
    examples: "High-skill action, competitive multiplayer, puzzle/tactics.",
  },
];

/** Narrow an untrusted value to the canonical four-aesthetic taxonomy. */
export function isAestheticValue(value: unknown): value is AestheticValue {
  return (
    typeof value === "string" &&
    (AESTHETIC_VALUES as readonly string[]).includes(value)
  );
}

/** Display label for a canonical value, or `null` when unresolved. */
export function aestheticLabel(value: AestheticValue | null): string | null {
  if (value === null) return null;
  return (
    AESTHETIC_DEFINITIONS.find((item) => item.value === value)?.label ?? null
  );
}
