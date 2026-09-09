/**
 * Shared profanity gate — SBGC-222.
 *
 * `allprofanity` is a pure string filter (no DOM, no fetch), so this helper is
 * safe to import on both the server (BFF validation) and the client (signup).
 *
 * No profanity filter is exhaustive, so extra banned terms are registered here
 * in code — add any newly-discovered evasion or slur to EXTRA_BANNED_WORDS.
 */

import allProfanity from "allprofanity";

/** Extra banned terms appended to the built-in dictionaries at import time. */
const EXTRA_BANNED_WORDS = [
  "n1gg3rs",
  "japs",
  "nigg4s",
  "n1ggas",
  "n1ggers",
  "nigg3rs",
  "blackslave",
  "slaveblack",
  "chingchong",
  "keling",
  "k3ling",
  "kelings",
  "k3lings",
  "f4ggots",
  "f4gg0ts",
  "fagg0ts",
];

// Register once at module load (runs once per process).
allProfanity.add(EXTRA_BANNED_WORDS);

/** True when *text* contains profanity across the supported languages. */
export function containsProfanity(text: string): boolean {
  if (!text) return false;
  return allProfanity.check(text);
}
