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

import type { ProfileScores } from "./score-validation";

export interface StoredSubmission {
  gameSlug: string;
  submittedAt: string;
  challenge: ProfileScores;
  reward: ProfileScores;
}

const STORAGE_PREFIX = "mygamedna_submission_";

export function getCachedSubmission(gameSlug: string): StoredSubmission | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(`${STORAGE_PREFIX}${gameSlug}`);
    if (!raw) return null;
    return JSON.parse(raw) as StoredSubmission;
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
