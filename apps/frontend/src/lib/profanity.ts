/**
 * Shared profanity gate — SBGC-222.
 *
 * `allprofanity` is a pure string filter (no DOM, no fetch), so this helper is
 * safe to import on both the server (BFF validation) and the client (signup).
 */

import allProfanity from "allprofanity";

/** True when *text* contains profanity across the supported languages. */
export function containsProfanity(text: string): boolean {
  if (!text) return false;
  return allProfanity.check(text);
}
