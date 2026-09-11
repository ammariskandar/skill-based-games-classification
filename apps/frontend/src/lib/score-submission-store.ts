/**
 * Client-side score-submission cache + auth bridge — SBGC-215.
 *
 * Persists a submitted score locally (so the modal can show an "already
 * submitted" state without a backend round-trip) and exposes a temporary
 * authentication check that reads a session cookie or a dev override flag.
 *
 * Full backend submission/authentication lands in a subsequent ticket; this
 * module is intentionally a browser-only persistence + gate bridge.
 */

import { isAestheticValue, type AestheticValue } from "./aesthetics";
import type { ProfileScores } from "./score-validation";

/** The aesthetic-bearing payload emitted by the manual score form (SBGC-228). */
export interface ScoreSubmissionPayload {
  challenge: ProfileScores;
  reward: ProfileScores;
  aesthetic: AestheticValue;
}

export interface StoredSubmission {
  gameSlug: string;
  submittedAt: string;
  challenge: ProfileScores;
  reward: ProfileScores;
  /** Canonical aesthetic, or `null` for legacy/pre-aesthetic cache entries. */
  aesthetic: AestheticValue | null;
}

const STORAGE_PREFIX = "mygamedna_submission_";

export function getCachedSubmission(gameSlug: string): StoredSubmission | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(`${STORAGE_PREFIX}${gameSlug}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSubmission;
    // Tolerate entries cached before the aesthetic field existed.
    return {
      ...parsed,
      aesthetic: isAestheticValue(parsed.aesthetic) ? parsed.aesthetic : null,
    };
  } catch {
    return null;
  }
}

export function saveSubmissionToCache(submission: StoredSubmission): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      `${STORAGE_PREFIX}${submission.gameSlug}`,
      JSON.stringify(submission),
    );
  } catch {
    // Gracefully ignore QuotaExceededError or private browsing restrictions.
  }
}

export function isUserAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  // Temporary auth evaluation bridge:
  // Reads session cookie or the dev override flag `mock_auth_logged_in`.
  return (
    document.cookie.includes("sessionid=") ||
    window.localStorage.getItem("mock_auth_logged_in") === "true"
  );
}
