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

// ── SBGC-191 infinite-loop helpers ─────────────────────────────────────────

/** Widest responsive tier — the maximum number of cards visible at once. */
export const CAROUSEL_MAX_VISIBLE: number = Math.max(
  ...CAROUSEL_BREAKPOINTS.map((tier) => tier.visibleCards),
);

/**
 * Boundary clones per side = widest tier + 1.  The extra clone guarantees the
 * scroll can always advance one full step into a clone region before the
 * track's hard end, which gives the scroll normalization a rounding-safety
 * margin (otherwise the exact end could sit a sub-pixel short of the wrap
 * boundary and stall the loop on desktop).
 */
export const CAROUSEL_LOOP_BUFFER: number = CAROUSEL_MAX_VISIBLE + 1;

/**
 * Modular wrap of an index into `[0, length)`.  Handles negative indices so
 * backward stepping past `0` wraps to `length - 1`.
 */
export function wrapCarouselIndex(index: number, length: number): number {
  if (length <= 0) return 0;
  return ((index % length) + length) % length;
}

/** Next logical card index (forward loop). */
export function nextCarouselIndex(index: number, length: number): number {
  return wrapCarouselIndex(index + 1, length);
}

/** Previous logical card index (backward loop). */
export function previousCarouselIndex(index: number, length: number): number {
  return wrapCarouselIndex(index - 1, length);
}

/**
 * Number of boundary clones per side for a list of `length` cards.
 *
 * `0` for single-card (or empty) lists — no fake infinite movement.  Bounded
 * by `CAROUSEL_LOOP_BUFFER` so small lists never explode into dozens of
 * duplicates.
 */
export function carouselCloneCount(length: number): number {
  if (length <= 1) return 0;
  return Math.min(CAROUSEL_LOOP_BUFFER, length);
}

/**
 * Normalize a raw scroll offset back into the canonical region.
 *
 * With `buffer` clones on each side of `length` canonical cards and a uniform
 * `step` (one card + one gap), the canonical region spans
 * `[buffer*step, (buffer+length)*step)`.  Offsets in the head-clone region
 * wrap back by `length*step`; offsets in the tail-clone region wrap forward by
 * the same amount.  The result is the equivalent canonical offset that shows
 * the same cards, so the reposition is visually seamless.
 */
export function normalizeCarouselScroll(
  scrollLeft: number,
  length: number,
  buffer: number,
  step: number,
): number {
  const canonicalStart = buffer * step;
  const canonicalEnd = (buffer + length) * step;
  // `scrollLeft` comes back from the browser as whole CSS pixels (nearest
  // pixel), while the canonical-region boundaries are fractional because the
  // card pitch is a sub-pixel value (e.g. `calc((100% - 4rem) / 5)`).  Without
  // this tolerance, the initial `buffer * step` offset — which the browser
  // rounds down by a fraction of a pixel — reads as strictly less than
  // `canonicalStart` and is misclassified as a tail clone, snapping the track
  // to the far end and making the arrows appear dead.  One pixel is well below
  // the card pitch (~hundreds of px), so it never wraps a genuine boundary
  // early by any visible amount, and the wrap itself stays visually seamless.
  const epsilon = 1;
  if (scrollLeft >= canonicalEnd - epsilon) return scrollLeft - length * step;
  if (scrollLeft < canonicalStart - epsilon) return scrollLeft + length * step;
  return scrollLeft;
}
