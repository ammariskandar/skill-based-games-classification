/**
 * Sign-up dropoff resume record — SBGC-218.
 *
 * When a user verifies their email but closes the tab before submitting the
 * form (a "dropoff"), the sign-up page remembers the challenge server-side
 * state is the *only* authority: this module just persists the last
 * `challenge_id` (plus the email and the device signature it was requested
 * from) so a return visit within the challenge TTL can skip sending a second
 * verification email.
 *
 * Resume is deliberately strict:
 *
 * - The stored challenge is only reused when the typed email matches AND the
 *   current device signature (OS + browser + timezone) matches the one that
 *   originally requested verification — no cross-device resume.
 * - Reuse is never assumed from local state alone: the page re-checks the
 *   server's `verification-status` endpoint and only flips to "Verified ✓"
 *   when the backend still reports the challenge as VERIFIED.
 */

import type { DeviceSignature } from "./device-signature";

export interface SignupResumeRecord {
  /** Normalised (trimmed, lower-cased) email the challenge was requested for. */
  email: string;
  challengeId: string;
  signature: DeviceSignature;
  /** Epoch milliseconds the challenge was requested (informational only). */
  requestedAt: number;
}

export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export const SIGNUP_RESUME_KEY = "mygamedna:signup-resume:v1";

function parseRecord(raw: string | null): SignupResumeRecord | null {
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const candidate = parsed as Partial<SignupResumeRecord>;
    if (
      typeof candidate.email !== "string" ||
      typeof candidate.challengeId !== "string" ||
      typeof candidate.requestedAt !== "number"
    ) {
      return null;
    }
    const signature = candidate.signature;
    if (
      typeof signature !== "object" ||
      signature === null ||
      typeof signature.os !== "string" ||
      typeof signature.browser !== "string" ||
      typeof signature.timezone !== "string"
    ) {
      return null;
    }
    return {
      email: candidate.email,
      challengeId: candidate.challengeId,
      signature: { ...signature },
      requestedAt: candidate.requestedAt,
    };
  } catch {
    return null;
  }
}

export function readSignupResume(
  storage: KeyValueStorage,
): SignupResumeRecord | null {
  try {
    return parseRecord(storage.getItem(SIGNUP_RESUME_KEY));
  } catch {
    return null;
  }
}

export function writeSignupResume(
  storage: KeyValueStorage,
  record: SignupResumeRecord,
): void {
  try {
    storage.setItem(SIGNUP_RESUME_KEY, JSON.stringify(record));
  } catch {
    /* Storage unavailable (private mode/quota) — resume simply won't apply. */
  }
}

export function clearSignupResume(storage: KeyValueStorage): void {
  try {
    storage.removeItem(SIGNUP_RESUME_KEY);
  } catch {
    /* Nothing to clear. */
  }
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function canResume(
  record: SignupResumeRecord | null,
  email: string,
  signature: DeviceSignature,
): boolean {
  if (!record) return false;
  return (
    record.email === normalizeEmail(email) &&
    record.signature.os === signature.os &&
    record.signature.browser === signature.browser &&
    record.signature.timezone === signature.timezone
  );
}
