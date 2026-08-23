/**
 * Catalogue cover-state model — SBGC-77 density/cover correction.
 *
 * Pure, server-safe TypeScript (no `requestAnimationFrame` at module scope, no
 * DOM globals): the browser's native `<img>` load/error events are the only
 * remote-health signal. A card's effective Capsule URL presence is known at
 * render time; the image's actual load/error (or cached `complete` state)
 * resolves "has-cover" vs "no-cover" at runtime.
 */

/** Frontend cover state for one catalogue card. */
export type CoverState = "unknown" | "has-cover" | "no-cover";

/**
 * Initial cover state from Capsule URL presence alone.
 *
 * A card with no effective Capsule URL is coverless immediately (no remote
 * request is attempted). A card with a Capsule URL starts "unknown" until the
 * native image load settles.
 */
export function initialCoverState(hasCapsuleUrl: boolean): CoverState {
  return hasCapsuleUrl ? "unknown" : "no-cover";
}

/** The subset of `HTMLImageElement` state needed to settle a cached image. */
export interface ImageLoadState {
  complete: boolean;
  naturalWidth: number;
}

/**
 * Resolve a cover state from an image's settled state.
 *
 * Returns `null` when the image has not finished loading yet (listeners are
 * still required). A `complete` image with `naturalWidth > 0` is a cover; a
 * `complete` image with `naturalWidth === 0` failed.
 */
export function resolveCoverStateFromImage(
  image: ImageLoadState,
): CoverState | null {
  if (!image.complete) return null;
  return image.naturalWidth > 0 ? "has-cover" : "no-cover";
}

/** Whether a cover state counts as coverless for partitioning. */
export function isCoverless(state: CoverState): boolean {
  return state === "no-cover";
}

/** A card reference paired with its original API index and cover state. */
export interface CoverCard<T = unknown> {
  /** Original SBGC-76 API position (stable tie-breaker). */
  index: number;
  state: CoverState;
  value: T;
}

/**
 * Stable partition: working/unknown cards first, confirmed coverless cards
 * last, each group ordered by original API index.
 *
 * Unknown cards must stay in their normal position (they are not broken); only
 * confirmed `no-cover` cards are moved. Sorting each group by `index` keeps the
 * partition stable even if the input order has already shifted.
 */
export function partitionCoverless<T>(
  cards: readonly CoverCard<T>[],
): CoverCard<T>[] {
  const working: CoverCard<T>[] = [];
  const coverless: CoverCard<T>[] = [];
  for (const card of cards) {
    (card.state === "no-cover" ? coverless : working).push(card);
  }
  const byIndex = (a: CoverCard<T>, b: CoverCard<T>) => a.index - b.index;
  working.sort(byIndex);
  coverless.sort(byIndex);
  return [...working, ...coverless];
}

/** A minimal requestAnimationFrame-compatible frame scheduler. */
export type FrameScheduler = (callback: () => void) => number;

export interface ReorderScheduler {
  /** Schedule at most one reorder per frame; repeated calls coalesce. */
  schedule(): void;
}

/**
 * Create a reorder scheduler that coalesces multiple requests into one
 * callback per animation frame. No polling, no interval, no permanent loop.
 */
export function createReorderScheduler(
  onReorder: () => void,
  raf: FrameScheduler,
): ReorderScheduler {
  let scheduled = false;
  return {
    schedule() {
      if (scheduled) return;
      scheduled = true;
      raf(() => {
        scheduled = false;
        onReorder();
      });
    },
  };
}
