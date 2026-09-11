// @vitest-environment jsdom
/**
 * Draft persistence tests — SBGC-180.
 *
 * Covers the happy path plus every fail-closed guard: TTL expiry, registry
 * version drift, slug mismatch, malformed JSON, and invalid score shapes.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DRAFT_PREFIX,
  DRAFT_TTL_MS,
  clearDraft,
  draftStorageKey,
  loadDraft,
  saveDraft,
  type QuestionnaireDraftState,
} from "../draft-storage";

const SLUG = "hollow-knight";
const USER = "user123";
const KEY = draftStorageKey(SLUG, USER);

function draftState(
  overrides: Partial<QuestionnaireDraftState> = {},
): QuestionnaireDraftState {
  return {
    gameSlug: SLUG,
    phase: "challenge",
    q1OptionId: "OPT_S1",
    q2OptionId: "OPT_NONE",
    answers: { Q3: "Q3_a_lot" },
    q15Rating: 8,
    adjustedChallenge: { micro: 40, macro: 30, mystiko: 30 },
    adjustedReward: { micro: 33, macro: 33, mystiko: 34 },
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("draft-storage", () => {
  it("keys drafts by slug and user hash", () => {
    expect(draftStorageKey(SLUG)).toBe(`${DRAFT_PREFIX}_${SLUG}_anon`);
    expect(KEY).toBe(`${DRAFT_PREFIX}_${SLUG}_${USER}`);
  });

  it("persists and restores an active draft", () => {
    expect(saveDraft(SLUG, draftState(), USER)).toBe(true);

    const loaded = loadDraft(SLUG, USER);
    expect(loaded).not.toBeNull();
    expect(loaded?.answers.Q3).toBe("Q3_a_lot");
    expect(loaded?.q15Rating).toBe(8);
    expect(loaded?.adjustedChallenge.micro).toBe(40);
    expect(loaded?.gameSlug).toBe(SLUG);
  });

  it("scopes drafts per user hash", () => {
    saveDraft(SLUG, draftState(), "userA");
    expect(loadDraft(SLUG, "userB")).toBeNull();
    expect(loadDraft(SLUG, "userA")).not.toBeNull();
  });

  it("refuses to persist a blank state", () => {
    const blank = draftState({
      q1OptionId: null,
      q2OptionId: null,
      answers: {},
      phase: "aesthetics",
    });
    expect(saveDraft(SLUG, blank, USER)).toBe(false);
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it("refuses to persist a completed phase", () => {
    expect(saveDraft(SLUG, draftState({ phase: "completed" }), USER)).toBe(
      false,
    );
  });

  it("discards drafts past the 7-day TTL", () => {
    saveDraft(SLUG, draftState(), USER);
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + DRAFT_TTL_MS + 1);

    expect(loadDraft(SLUG, USER)).toBeNull();
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it("keeps drafts within the TTL window", () => {
    saveDraft(SLUG, draftState(), USER);
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + DRAFT_TTL_MS - 1);
    expect(loadDraft(SLUG, USER)).not.toBeNull();
  });

  it("purges malformed JSON", () => {
    localStorage.setItem(KEY, "{ broken json");
    expect(loadDraft(SLUG, USER)).toBeNull();
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it("ignores drafts from a different registry version", () => {
    saveDraft(SLUG, draftState(), USER);
    const raw = JSON.parse(localStorage.getItem(KEY)!);
    raw.version = "v0.9.0";
    localStorage.setItem(KEY, JSON.stringify(raw));

    expect(loadDraft(SLUG, USER)).toBeNull();
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it("ignores drafts for a different slug", () => {
    saveDraft(SLUG, draftState(), USER);
    const raw = JSON.parse(localStorage.getItem(KEY)!);
    raw.gameSlug = "some-other-game";
    localStorage.setItem(KEY, JSON.stringify(raw));

    expect(loadDraft(SLUG, USER)).toBeNull();
  });

  it("purges drafts with invalid score vectors", () => {
    saveDraft(SLUG, draftState(), USER);
    const raw = JSON.parse(localStorage.getItem(KEY)!);
    raw.adjustedChallenge = { micro: "nope", macro: 1, mystiko: 2 };
    localStorage.setItem(KEY, JSON.stringify(raw));

    expect(loadDraft(SLUG, USER)).toBeNull();
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it("clears a draft on demand", () => {
    saveDraft(SLUG, draftState(), USER);
    expect(loadDraft(SLUG, USER)).not.toBeNull();

    clearDraft(SLUG, USER);
    expect(loadDraft(SLUG, USER)).toBeNull();
  });

  it("returns false instead of throwing when storage rejects the write", () => {
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("QuotaExceededError");
      });
    expect(saveDraft(SLUG, draftState(), USER)).toBe(false);
    setItem.mockRestore();
  });
});
