/**
 * Pure game-image layout decision — SBGC-184 correction.
 *
 * Owns the Steam fallback ladder and the "reserve a classification-
 * visualization slot" decision so `GameImage.astro` stays a thin renderer and
 * the layout is unit-testable without a DOM. No browser APIs here.
 */

export type GameImageSource = "steam" | "manual";

export type ForegroundRole = "library-capsule" | "header" | "manual-primary";

/**
 * Library Capsule is portrait (2:3). The reserved classification-
 * visualization slot is square (1:1). Both children share one flex-group
 * height, so the slot's displayed height tracks the Capsule's height and the
 * square slot is therefore wider than the portrait Capsule.
 */
export const CAPSULE_ASPECT_RATIO = 2 / 3;
export const VISUALIZATION_SLOT_ASPECT_RATIO = 1;

export interface GameImageLayout {
  kind: "image" | "placeholder";
  backgroundSrc: string;
  foregroundSrc: string;
  foregroundRole: ForegroundRole;
  foregroundContained: boolean;
  /** True only for the "ideal" Hero + Capsule composition (any source). */
  showVisualizationSlot: boolean;
}

export interface GameImageLayoutInput {
  src: string;
  source: GameImageSource;
  libraryHeroUrl?: string | null;
  libraryCapsuleUrl?: string | null;
}

/**
 * Resolve the presentation layout for one Game image.
 *
 * Source-agnostic fallback ladder (SBGC-190): Steam and Manual Games share the
 * same effective Hero + Capsule + Image composition.
 *
 *   A) Hero + Capsule  → Hero background + Capsule foreground + slot
 *   B) Hero only       → Hero background + contained image foreground
 *   C) Capsule only    → image background + Capsule foreground
 *   D) neither         → image-only full-frame
 *   E) no image        → placeholder
 */
export function resolveGameImageLayout(
  input: GameImageLayoutInput,
): GameImageLayout {
  const hero = (input.libraryHeroUrl ?? "").trim();
  const capsule = (input.libraryCapsuleUrl ?? "").trim();
  const image = input.src.trim();
  const generalRole: ForegroundRole =
    input.source === "steam" ? "header" : "manual-primary";

  let backgroundSrc = "";
  let foregroundSrc = "";
  let foregroundRole: ForegroundRole = generalRole;
  let foregroundContained = false;

  if (hero !== "") {
    backgroundSrc = hero;
    if (capsule !== "") {
      foregroundSrc = capsule;
      foregroundRole = "library-capsule";
      foregroundContained = true;
    } else if (image !== "") {
      foregroundSrc = image;
      foregroundRole = generalRole;
      foregroundContained = true;
    }
  } else if (capsule !== "") {
    backgroundSrc = image;
    foregroundSrc = capsule;
    foregroundRole = "library-capsule";
    foregroundContained = true;
  } else if (image !== "") {
    foregroundSrc = image;
    foregroundRole = generalRole;
    foregroundContained = false;
  }

  const hasBackground = backgroundSrc !== "";
  const hasForeground = foregroundSrc !== "";
  const hasImage = hasBackground || hasForeground;

  return {
    kind: hasImage ? "image" : "placeholder",
    backgroundSrc,
    foregroundSrc,
    foregroundRole,
    foregroundContained,
    showVisualizationSlot: hero !== "" && capsule !== "",
  };
}
