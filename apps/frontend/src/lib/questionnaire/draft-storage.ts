/**
 * Questionnaire draft persistence — SBGC-180.
 *
 * Client-side durability for in-progress assessments.  Drafts are stored in
 * `localStorage` under a key scoped to the game slug and a user hash, carry a
 * 7-day sliding TTL, and are validated on read against the active registry
 * version and a strict shape.  Every failure mode (malformed JSON, schema
 * drift, expiry, quota/private-mode errors) fails closed — the draft is purged
 * and the caller simply starts fresh.
 *
 * The server stays authoritative: a draft is a progress proposal only.  The
 * state machine re-validates every answer id against the assembled registry
 * tree when it hydrates.
 */

import { REGISTRY_VERSION } from "./registry/v1/types";
import type { DimensionScore } from "./scoring/types";
import type { QuestionnairePhase } from "./state-machine";

export const DRAFT_PREFIX = "mygamedna_q_draft";
export const DRAFT_ANON_USER = "anon";
export const DRAFT_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

/** Serializable snapshot of an in-progress questionnaire. */
export interface QuestionnaireDraftState {
  gameSlug: string;
  phase: QuestionnairePhase;
  q1OptionId: string | null;
  q2OptionId: string | null;
  answers: Record<string, string>;
  q15Rating: number;
  adjustedChallenge: DimensionScore;
  adjustedReward: DimensionScore;
}

/** A persisted draft: the state snapshot plus storage metadata. */
export interface QuestionnaireDraft extends QuestionnaireDraftState {
  version: string;
  updatedAt: number;
}

/** Cross-contamination guard: drafts are scoped to slug + user hash. */
export function draftStorageKey(
  slug: string,
  userHash: string = DRAFT_ANON_USER,
): string {
  return `${DRAFT_PREFIX}_${slug}_${userHash}`;
}

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage ?? null;
  } catch {
    // Storage access can throw in sandboxed/private contexts.
    return null;
  }
}

function isDimensionScore(value: unknown): value is DimensionScore {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (["micro", "macro", "mystiko"] as const).every((dimension) =>
    Number.isFinite(Number(record[dimension])),
  );
}

function toDimensionScore(value: DimensionScore): DimensionScore {
  return {
    micro: Number(value.micro),
    macro: Number(value.macro),
    mystiko: Number(value.mystiko),
  };
}

function sanitizeAnswers(value: unknown): Record<string, string> {
  const answers: Record<string, string> = {};
  if (typeof value !== "object" || value === null) return answers;
  for (const [questionId, optionId] of Object.entries(value)) {
    if (typeof optionId === "string") answers[questionId] = optionId;
  }
  return answers;
}

/**
 * Persist a draft snapshot.  Returns `false` (never throws) when storage is
 * unavailable, the snapshot is empty, or the quota/sandbox rejects the write.
 */
export function saveDraft(
  slug: string,
  state: QuestionnaireDraftState,
  userHash: string = DRAFT_ANON_USER,
): boolean {
  const store = storage();
  if (!store) return false;
  if (state.phase === "completed") return false;

  // Never persist an untouched questionnaire.
  if (!state.q1OptionId && Object.keys(state.answers).length === 0) {
    return false;
  }

  const payload: QuestionnaireDraft = {
    ...state,
    gameSlug: slug,
    version: REGISTRY_VERSION,
    updatedAt: Date.now(),
  };

  try {
    store.setItem(draftStorageKey(slug, userHash), JSON.stringify(payload));
    return true;
  } catch {
    return false;
  }
}

/**
 * Load and validate a draft.  Purges and returns `null` on expiry, version or
 * slug mismatch, malformed shape, or unreadable storage.
 */
export function loadDraft(
  slug: string,
  userHash: string = DRAFT_ANON_USER,
  now: number = Date.now(),
): QuestionnaireDraft | null {
  const store = storage();
  if (!store) return null;

  let raw: string | null;
  try {
    raw = store.getItem(draftStorageKey(slug, userHash));
  } catch {
    return null;
  }
  if (!raw) return null;

  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) {
      throw new Error("draft is not an object");
    }
    const draft = parsed as Partial<QuestionnaireDraft>;

    const expired =
      typeof draft.updatedAt !== "number" ||
      now - draft.updatedAt > DRAFT_TTL_MS;
    const staleSchema =
      draft.gameSlug !== slug || draft.version !== REGISTRY_VERSION;
    const malformed =
      typeof draft.phase !== "string" ||
      typeof draft.q15Rating !== "number" ||
      !Number.isFinite(draft.q15Rating) ||
      typeof draft.answers !== "object" ||
      draft.answers === null ||
      Array.isArray(draft.answers) ||
      !isDimensionScore(draft.adjustedChallenge) ||
      !isDimensionScore(draft.adjustedReward);

    if (expired || staleSchema || malformed) {
      clearDraft(slug, userHash);
      return null;
    }

    // Every field is runtime-validated above; assert the concrete shape.
    const validated = draft as QuestionnaireDraft;
    return {
      version: validated.version,
      gameSlug: slug,
      updatedAt: validated.updatedAt,
      phase: validated.phase,
      q1OptionId:
        typeof validated.q1OptionId === "string" ? validated.q1OptionId : null,
      q2OptionId:
        typeof validated.q2OptionId === "string" ? validated.q2OptionId : null,
      answers: sanitizeAnswers(validated.answers),
      q15Rating: validated.q15Rating,
      adjustedChallenge: toDimensionScore(validated.adjustedChallenge),
      adjustedReward: toDimensionScore(validated.adjustedReward),
    };
  } catch {
    clearDraft(slug, userHash);
    return null;
  }
}

/** Remove a draft.  Safe to call when storage is unavailable. */
export function clearDraft(
  slug: string,
  userHash: string = DRAFT_ANON_USER,
): void {
  const store = storage();
  if (!store) return;
  try {
    store.removeItem(draftStorageKey(slug, userHash));
  } catch {
    // Ignore storage exceptions.
  }
}
