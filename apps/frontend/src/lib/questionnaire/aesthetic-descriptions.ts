/**
 * Plain-language explanations for every aesthetic combination — SBGC-171/178.
 *
 * Display-only copy for the Review & Submit "Aesthetic" tooltip.  The resolver
 * can return four true aesthetics and twelve ordered hybrids; the prose below
 * is keyed by `dominant+secondary` (a true aesthetic repeats its category).
 * This is presentation only and is not mirrored in the Python registry, which
 * returns the resolved category pair as data.
 */

import { AestheticCategory } from "./types";

export interface AestheticDescription {
  title: string;
  body: string;
}

const S = AestheticCategory.SENSORY;
const F = AestheticCategory.FANTASY;
const N = AestheticCategory.NARRATIVE;
const C = AestheticCategory.CHALLENGE;

export const AESTHETIC_DESCRIPTIONS: Readonly<
  Record<string, AestheticDescription>
> = {
  [`${S}+${S}`]: {
    title: "True Sensory (S + S)",
    body: "A game focused purely on sights, sounds, tactile rhythm, or pure visceral adrenaline, without needing deep strategy, complex lore, or role-playing.",
  },
  [`${F}+${F}`]: {
    title: "True Fantasy (F + F)",
    body: "A game dedicated entirely to living an alternate life, exploring open sandboxes, or building worlds, where escapism and personal freedom are the whole point.",
  },
  [`${N}+${N}`]: {
    title: "True Narrative (N + N)",
    body: "A game designed like an interactive story or drama, where authored plots, branching choices, and character relationships take complete priority over complex gameplay mechanics.",
  },
  [`${C}+${C}`]: {
    title: "True Challenge (C + C)",
    body: "A game stripped down to test pure player competence—whether through punishing twitch execution, strict strategy, or competitive ladder climbing.",
  },
  [`${S}+${F}`]: {
    title: "Sensory & Fantasy / Sensory Dominant (S + F)",
    body: "A game where responsive action, striking visuals, or tactile vibes come first, supported by an imaginative or escapist world.",
  },
  [`${F}+${S}`]: {
    title: "Fantasy & Sensory / Fantasy Dominant (F + S)",
    body: "A game centered on exploring a fantasy world or building your vision, brought to life through rich visual art, sound design, or atmospheric mood.",
  },
  [`${S}+${N}`]: {
    title: "Sensory & Narrative / Sensory Dominant (S + N)",
    body: "A game driven by immediate, visceral action, horror, or tactile spectacle, anchored in the background by a compelling story.",
  },
  [`${N}+${S}`]: {
    title: "Narrative & Sensory / Narrative Dominant (N + S)",
    body: "A heavily story-focused journey that uses cinematic visuals, emotional music, and voice acting to bring its script and characters to life.",
  },
  [`${S}+${C}`]: {
    title: "Sensory & Challenge / Sensory Dominant (S + C)",
    body: "Fast, adrenaline-inducing gameplay where button timing and execution matter, but the immediate sensory thrill takes priority over raw competitive min-maxing.",
  },
  [`${C}+${S}`]: {
    title: "Challenge & Sensory / Challenge Dominant (C + S)",
    body: "A hardcore test of reflexes, rhythm, and input accuracy (high APM), where visual cues and sound feedback exist to test and reward pure mechanical skill.",
  },
  [`${F}+${N}`]: {
    title: "Fantasy & Narrative / Fantasy Dominant (F + N)",
    body: "A deep role-playing or world-building experience where player agency and immersion in an alternate world lead the way, enhanced by rich companion stories and world lore.",
  },
  [`${N}+${F}`]: {
    title: "Narrative & Fantasy / Narrative Dominant (N + F)",
    body: "A structured, story-driven adventure that uses an imaginative fantasy setting or an alternate universe as the backdrop for its plot and characters.",
  },
  [`${F}+${C}`]: {
    title: "Fantasy & Challenge / Fantasy Dominant (F + C)",
    body: "An escapist game with creative freedom, open exploration, or build-crafting, backed by tough progression gates or bosses that demand thoughtful preparation.",
  },
  [`${C}+${F}`]: {
    title: "Challenge & Fantasy / Challenge Dominant (C + F)",
    body: "A demanding game full of punishing hurdles or deep strategy, wrapped inside an imaginative, high-stakes fantasy world.",
  },
  [`${N}+${C}`]: {
    title: "Narrative & Challenge / Narrative Dominant (N + C)",
    body: "A story-heavy experience where character survival and dramatic narrative climaxes require surviving scarce resources, tactical turn planning, or tense confrontations.",
  },
  [`${C}+${N}`]: {
    title: "Challenge & Narrative / Challenge Dominant (C + N)",
    body: "A mechanically or tactically demanding game where conquering tough hurdles, bosses, or runs is what unlocks and advances the story and character lore.",
  },
};

/**
 * Return the explanation for a resolved aesthetic, or `null` when no prose
 * exists (e.g. the reserved `SPECIAL_FLOW`, or an unsolved questionnaire).
 *
 * A true aesthetic repeats its dominant category; a hybrid uses the dominant
 * (Question 1) category first and the secondary (Question 2) category second.
 */
export function describeAesthetic(
  dominant: string | null,
  secondary: string | null,
  isTrueAesthetic: boolean,
): AestheticDescription | null {
  if (!dominant) return null;
  const second = isTrueAesthetic || !secondary ? dominant : secondary;
  return AESTHETIC_DESCRIPTIONS[`${dominant}+${second}`] ?? null;
}
