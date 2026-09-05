/**
 * Sign-up dropoff-resume record tests — SBGC-218.
 *
 * Locks the localStorage record contract: round-trip persistence, malformed
 * payload rejection, email normalisation, and the strict same-system gate
 * (email + device signature must all match before a challenge is reusable).
 */

import { describe, expect, it } from "vitest";
import type { DeviceSignature } from "./device-signature";
import {
  SIGNUP_RESUME_KEY,
  canResume,
  clearSignupResume,
  normalizeEmail,
  readSignupResume,
  writeSignupResume,
  type KeyValueStorage,
  type SignupResumeRecord,
} from "./signup-resume";

function memoryStorage(): KeyValueStorage & { store: Map<string, string> } {
  const store = new Map<string, string>();
  return {
    store,
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  };
}

const SIGNATURE: DeviceSignature = {
  os: "windows",
  browser: "chrome",
  timezone: "Asia/Kuala_Lumpur",
};

function record(
  overrides: Partial<SignupResumeRecord> = {},
): SignupResumeRecord {
  return {
    email: "user@example.com",
    challengeId: "challenge-abc",
    signature: SIGNATURE,
    requestedAt: 1_700_000_000_000,
    ...overrides,
  };
}

describe("normalizeEmail", () => {
  it("trims and lower-cases", () => {
    expect(normalizeEmail("  User@Example.COM ")).toBe("user@example.com");
  });
});

describe("resume record round-trip", () => {
  it("persists and restores a record", () => {
    const storage = memoryStorage();
    const input = record();
    writeSignupResume(storage, input);
    expect(storage.store.has(SIGNUP_RESUME_KEY)).toBe(true);
    expect(readSignupResume(storage)).toEqual(input);
  });

  it("returns null when nothing is stored", () => {
    expect(readSignupResume(memoryStorage())).toBeNull();
  });

  it("clears the record", () => {
    const storage = memoryStorage();
    writeSignupResume(storage, record());
    clearSignupResume(storage);
    expect(readSignupResume(storage)).toBeNull();
  });

  it("rejects malformed JSON", () => {
    const storage = memoryStorage();
    storage.setItem(SIGNUP_RESUME_KEY, "not-json");
    expect(readSignupResume(storage)).toBeNull();
  });

  it("rejects structurally invalid payloads", () => {
    const storage = memoryStorage();
    storage.setItem(SIGNUP_RESUME_KEY, JSON.stringify({ email: 42 }));
    expect(readSignupResume(storage)).toBeNull();
  });

  it("swallows storage exceptions", () => {
    const storage: KeyValueStorage = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => undefined,
      removeItem: () => undefined,
    };
    expect(readSignupResume(storage)).toBeNull();
  });
});

describe("canResume", () => {
  it("is true when email and device signature match", () => {
    expect(canResume(record(), "  USER@example.com ", SIGNATURE)).toBe(true);
  });

  it("is false when no record exists", () => {
    expect(canResume(null, "user@example.com", SIGNATURE)).toBe(false);
  });

  it("is false when the email differs", () => {
    expect(canResume(record(), "other@example.com", SIGNATURE)).toBe(false);
  });

  it("is false when any signature field differs", () => {
    expect(
      canResume(record(), "user@example.com", { ...SIGNATURE, os: "macos" }),
    ).toBe(false);
    expect(
      canResume(record(), "user@example.com", {
        ...SIGNATURE,
        browser: "firefox",
      }),
    ).toBe(false);
    expect(
      canResume(record(), "user@example.com", {
        ...SIGNATURE,
        timezone: "Europe/London",
      }),
    ).toBe(false);
  });
});
