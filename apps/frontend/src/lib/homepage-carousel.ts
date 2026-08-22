/**
 * Homepage carousel layout contract — SBGC-189.
 *
 * Pure, testable viewport→visible-card mapping plus the scroll-step math the
 * client-side controller uses. The carousel component's CSS mirrors these
 * breakpoints; the values live here so the "5 on desktop / fewer on smaller
 * screens" contract is asserted once instead of being left implicit in a
 * stylesheet.
 */

/** Gap between adjacent cards, kept in sync with the component CSS. */
export const CAROUSEL_GAP_PX = 16;

export interface CarouselBreakpoint {
  /** Minimum viewport width (px) at which this tier applies. */
  minWidth: number;
  /** Number of Capsules visible at once in this tier. */
  visibleCards: number;
}

/**
 * Ordered from widest to narrowest so the first matching tier wins.
 * Mirrors the project's `sm` (40rem) and `lg` (64rem) breakpoints.
 */
export const CAROUSEL_BREAKPOINTS: readonly CarouselBreakpoint[] = [
  { minWidth: 1024, visibleCards: 5 }, // desktop
  { minWidth: 640, visibleCards: 3 }, // tablet
  { minWidth: 0, visibleCards: 2 }, // mobile
];

/** Number of Capsules shown at once for a given viewport width (px). */
export function visibleCardsForViewport(viewportWidth: number): number {
  for (const tier of CAROUSEL_BREAKPOINTS) {
    if (viewportWidth >= tier.minWidth) return tier.visibleCards;
  }
  return 1;
}

/** Scroll distance for one card step (one card plus one gap). */
export function carouselScrollStep(cardWidth: number, gap: number): number {
  return cardWidth + gap;
}

/** Positional emphasis level for a carousel card (SBGC-189 correction). */
export type CarouselEmphasis = "full" | "intermediate" | "darkest";

/**
 * Map a card's distance-from-center rank to its emphasis level.
 *
 * `stepsFromCenter` is the number of distinct distance bands between a card
 * and the viewport-center card (0 = the centered card). `visibleCount` selects
 * the band structure for the current responsive tier:
 * - 5 visible → full / intermediate / darkest
 * - 3 visible → full / darkest
 * - 2 visible → full / darkest (nearest center is full)
 * - 1 visible → full
 */
export function carouselEmphasis(
  stepsFromCenter: number,
  visibleCount: number,
): CarouselEmphasis {
  if (stepsFromCenter <= 0) return "full";
  if (visibleCount >= 5 && stepsFromCenter === 1) return "intermediate";
  return "darkest";
}

/**
 * Assign emphasis to each card from its rounded pixel distance to the viewport
 * center. Cards are ranked by distinct distance so symmetric cards share a
 * level. This is positional (recomputed on every scroll/resize), never
 * coupled to the card's permanent array index.
 */
export function assignCarouselEmphasis(
  distances: number[],
  visibleCount: number,
): CarouselEmphasis[] {
  const ladder = Array.from(new Set(distances)).sort((a, b) => a - b);
  return distances.map((d) =>
    carouselEmphasis(ladder.indexOf(d), visibleCount),
  );
}
