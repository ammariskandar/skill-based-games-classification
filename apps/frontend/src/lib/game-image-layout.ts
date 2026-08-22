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
  /** True only for the Steam "ideal" Hero + Capsule composition. */
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
 * Steam fallback ladder:
 *   A) Hero + Capsule  → Hero background + Capsule foreground + slot
 *   B) Hero only       → Hero background + contained header fallback
 *   C) Capsule only    → header background + Capsule foreground
 *   D) neither         → header-only full-frame
 *   E) no image        → placeholder
 *
 * Manual Games always use a single full-frame operator image.
 */
export function resolveGameImageLayout(
  input: GameImageLayoutInput,
): GameImageLayout {
  const isSteam = input.source === "steam";
  const hero = (input.libraryHeroUrl ?? "").trim();
  const capsule = (input.libraryCapsuleUrl ?? "").trim();
  const header = input.src.trim();

  let backgroundSrc = "";
  let foregroundSrc = "";
  let foregroundRole: ForegroundRole = "header";
  let foregroundContained = false;

  if (isSteam) {
    if (hero !== "") {
      backgroundSrc = hero;
      if (capsule !== "") {
        foregroundSrc = capsule;
        foregroundRole = "library-capsule";
        foregroundContained = true;
      } else if (header !== "") {
        foregroundSrc = header;
        foregroundRole = "header";
        foregroundContained = true;
      }
    } else if (capsule !== "") {
      backgroundSrc = header;
      foregroundSrc = capsule;
      foregroundRole = "library-capsule";
      foregroundContained = true;
    } else if (header !== "") {
      foregroundSrc = header;
      foregroundRole = "header";
      foregroundContained = false;
    }
  } else {
    foregroundSrc = header;
    foregroundRole = "manual-primary";
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
    showVisualizationSlot: isSteam && hero !== "" && capsule !== "",
  };
}
