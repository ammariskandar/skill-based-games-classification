/**
 * Client questionnaire state machine — SBGC-178.
 *
 * DOM-free orchestrator for the questionnaire progression.  Components drive
 * this class and forward its emitted events to the live radar (SBGC-179) via
 * `window.dispatchEvent`.  Keeping the class DOM-free lets the unit suite run
 * in Node.
 */

import { resolveFromOptions } from "./aesthetic-taxonomy";
import { assembleQuestionnaire } from "./registry/v1/assembler";
import type { AssembledQuestionnaire, QuestionNode } from "./registry/v1/types";
import { applyProportionalCompensation } from "./scoring/compensation";
import { computeRawProfile, normalizeProfile } from "./scoring/engine";
import type { DimensionScore } from "./scoring/types";
import type {
  QuestionnaireDraft,
  QuestionnaireDraftState,
} from "./draft-storage";
import type { ConflictResolution, QuestionnaireSubmitRequest } from "./types";

export type QuestionnairePhase =
  | "aesthetics"
  | "challenge"
  | "reward"
  | "quality"
  | "review"
  | "submitting"
  | "completed";

export interface ProfileScores {
  raw: DimensionScore;
  norm: DimensionScore;
  adj: DimensionScore;
}

export type StateMachineEvent =
  | { type: "phase-change"; phase: QuestionnairePhase }
  | { type: "challenge-update"; challenge: ProfileScores }
  | { type: "reward-update"; reward: ProfileScores }
  | { type: "boundary-swap" };

type Listener = (event: StateMachineEvent) => void;

const ZERO: DimensionScore = { micro: 0, macro: 0, mystiko: 0 };
const DEFAULT_NORM: DimensionScore = { micro: 33, macro: 33, mystiko: 34 };

/** Default relevance rating shown before the Q15 step is touched. */
const DEFAULT_Q15_RATING = 7;

/** Phases a hydrated draft is allowed to resume into. */
const RESUMABLE_PHASES: readonly QuestionnairePhase[] = [
  "aesthetics",
  "challenge",
  "reward",
  "quality",
  "review",
];

function emptyScores(): ProfileScores {
  return {
    raw: { ...ZERO },
    norm: { ...DEFAULT_NORM },
    adj: { ...DEFAULT_NORM },
  };
}

export class QuestionnaireStateMachine {
  public phase: QuestionnairePhase = "aesthetics";
  public q15Rating = DEFAULT_Q15_RATING;

  public challenge: ProfileScores = emptyScores();
  public reward: ProfileScores = emptyScores();

  private q1OptionId: string | null = null;
  private q2OptionId: string | null = null;
  private tree: AssembledQuestionnaire | null = null;
  private answers: Record<string, string> = {};
  private flatSequence: QuestionNode[] = [];
  private lastEmittedPart: "challenge" | "reward" | null = null;
  private listeners = new Set<Listener>();

  get isAssembled(): boolean {
    return this.tree !== null;
  }

  get dominantAesthetic(): string | null {
    return this.tree?.dominantAesthetic ?? null;
  }

  get secondaryAesthetic(): string | null {
    return this.tree?.secondaryAesthetic ?? null;
  }

  get isTrueAesthetic(): boolean {
    return this.tree?.isTrueAesthetic ?? false;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  answerFor(questionId: string): string | undefined {
    return this.answers[questionId];
  }

  getActiveSequence(): readonly QuestionNode[] {
    return this.flatSequence;
  }

  setAestheticAnswers(q1OptionId: string, q2OptionId: string): void {
    this.q1OptionId = q1OptionId;
    this.q2OptionId = q2OptionId;
    this.tree = assembleQuestionnaire(
      resolveFromOptions(q1OptionId, q2OptionId),
    );
    this.answers = {};
    this.lastEmittedPart = "challenge";
    this.rebuildSequence();
    this.recalculateScores();
    this.transition("challenge");
    this.emit({ type: "challenge-update", challenge: this.challenge });
  }

  recordAnswer(questionId: string, optionId: string): void {
    this.answers[questionId] = optionId;
    this.rebuildSequence();
    this.pruneInactiveAnswers();
    this.recalculateScores();
    this.emitPartUpdate(questionId);
  }

  /** Undo one answer and any downstream branch answers it made reachable. */
  removeAnswer(questionId: string): void {
    if (!(questionId in this.answers)) return;
    delete this.answers[questionId];
    this.rebuildSequence();
    this.pruneInactiveAnswers();
    this.recalculateScores();
    this.emitPartUpdate(questionId);
  }

  adjustScore(
    target: "CHALLENGE" | "REWARD",
    dimension: keyof DimensionScore,
    targetValue: number,
  ): void {
    if (target === "CHALLENGE") {
      this.challenge.adj = applyProportionalCompensation(
        this.challenge.norm,
        dimension,
        targetValue,
        this.q15Rating,
      );
      this.emit({ type: "challenge-update", challenge: this.challenge });
    } else {
      this.reward.adj = applyProportionalCompensation(
        this.reward.norm,
        dimension,
        targetValue,
        this.q15Rating,
      );
      this.emit({ type: "reward-update", reward: this.reward });
    }
  }

  resetQ15Adjustments(): void {
    this.challenge.adj = { ...this.challenge.norm };
    this.reward.adj = { ...this.reward.norm };
  }

  /** True once the player has made any choice worth persisting. */
  isDirty(): boolean {
    return (
      this.q1OptionId !== null ||
      Object.keys(this.answers).length > 0 ||
      this.q15Rating !== DEFAULT_Q15_RATING
    );
  }

  /** Serializable snapshot for draft storage. */
  toDraft(gameSlug: string): QuestionnaireDraftState {
    return {
      gameSlug,
      phase: this.phase,
      q1OptionId: this.q1OptionId,
      q2OptionId: this.q2OptionId,
      answers: { ...this.answers },
      q15Rating: this.q15Rating,
      adjustedChallenge: { ...this.challenge.adj },
      adjustedReward: { ...this.reward.adj },
    };
  }

  /**
   * Restore a persisted draft, re-validating every answer against the active
   * registry tree.  Returns `false` (and resets) when the draft cannot be
   * applied; unknown answer ids are dropped rather than rejecting the draft.
   */
  hydrateFromDraft(draft: QuestionnaireDraft): boolean {
    try {
      this.q1OptionId = draft.q1OptionId;
      this.q2OptionId = draft.q2OptionId;
      this.answers = { ...draft.answers };
      this.q15Rating = draft.q15Rating;

      this.tree = null;
      if (draft.q1OptionId && draft.q2OptionId) {
        this.tree = assembleQuestionnaire(
          resolveFromOptions(draft.q1OptionId, draft.q2OptionId),
        );
      }

      this.rebuildSequence();
      this.pruneInactiveAnswers();
      this.recalculateScores();

      this.challenge.adj = { ...draft.adjustedChallenge };
      this.reward.adj = { ...draft.adjustedReward };

      const hasTree = this.tree !== null;
      let phase: QuestionnairePhase = draft.phase;
      if (phase === "submitting" || phase === "completed") phase = "review";
      if (!hasTree) phase = "aesthetics";
      this.phase = RESUMABLE_PHASES.includes(phase) ? phase : "review";
      this.lastEmittedPart = null;

      this.emit({ type: "phase-change", phase: this.phase });
      this.emit({ type: "challenge-update", challenge: this.challenge });
      this.emit({ type: "reward-update", reward: this.reward });
      return true;
    } catch {
      this.reset();
      return false;
    }
  }

  /** Return to a pristine aesthetics state and broadcast the cleared scores. */
  reset(): void {
    this.phase = "aesthetics";
    this.q1OptionId = null;
    this.q2OptionId = null;
    this.tree = null;
    this.answers = {};
    this.flatSequence = [];
    this.lastEmittedPart = null;
    this.q15Rating = DEFAULT_Q15_RATING;
    this.challenge = emptyScores();
    this.reward = emptyScores();

    this.emit({ type: "phase-change", phase: this.phase });
    this.emit({ type: "challenge-update", challenge: this.challenge });
    this.emit({ type: "reward-update", reward: this.reward });
  }

  getPayload(
    conflictResolution?: ConflictResolution,
  ): QuestionnaireSubmitRequest {
    if (!this.q1OptionId || !this.q2OptionId) {
      throw new Error("Cannot generate payload without aesthetic selections.");
    }
    return {
      version: "v1.0.0",
      q1_option_id: this.q1OptionId,
      q2_option_id: this.q2OptionId,
      answers: { ...this.answers },
      q15_rating: this.q15Rating,
      adjusted_challenge: { ...this.challenge.adj },
      adjusted_reward: { ...this.reward.adj },
      conflict_resolution: conflictResolution ?? null,
    };
  }

  transition(phase: QuestionnairePhase): void {
    this.phase = phase;
    this.emit({ type: "phase-change", phase });
  }

  private recalculateScores(): void {
    if (!this.tree) return;
    this.challenge.raw = computeRawProfile(
      this.answers,
      this.tree.part1ChallengeNodes,
      "CHALLENGE",
    );
    this.challenge.norm = normalizeProfile(this.challenge.raw);
    this.challenge.adj = { ...this.challenge.norm };

    this.reward.raw = computeRawProfile(
      this.answers,
      this.tree.part2RewardNodes,
      "REWARD",
    );
    this.reward.norm = normalizeProfile(this.reward.raw);
    this.reward.adj = { ...this.reward.norm };
  }

  private rebuildSequence(): void {
    if (!this.tree) {
      this.flatSequence = [];
      return;
    }
    const sequence: QuestionNode[] = [];
    const walk = (nodes: readonly QuestionNode[]): void => {
      const byId = new Map(nodes.map((node) => [node.id, node]));
      for (const root of nodes.filter((node) => !node.isBranch)) {
        let current: QuestionNode | undefined = byId.get(root.id);
        const seen = new Set<string>();
        while (current && !seen.has(current.id)) {
          seen.add(current.id);
          sequence.push(current);
          const optionId = this.answers[current.id];
          const option = optionId
            ? current.options.find((candidate) => candidate.id === optionId)
            : undefined;
          current = option?.nextQuestionId
            ? byId.get(option.nextQuestionId)
            : undefined;
        }
      }
    };
    walk(this.tree.part1ChallengeNodes);
    walk(this.tree.part2RewardNodes);
    this.flatSequence = sequence;
  }

  private pruneInactiveAnswers(): void {
    const active = new Set(this.flatSequence.map((node) => node.id));
    for (const questionId of Object.keys(this.answers)) {
      if (!active.has(questionId)) {
        delete this.answers[questionId];
      }
    }
  }

  private emitPartUpdate(questionId: string): void {
    const part = this.partOf(questionId);
    if (part === "reward" && this.lastEmittedPart === "challenge") {
      this.emit({ type: "boundary-swap" });
    }
    if (part === "challenge") {
      this.emit({ type: "challenge-update", challenge: this.challenge });
    } else if (part === "reward") {
      this.emit({ type: "reward-update", reward: this.reward });
    }
    this.lastEmittedPart = part;
  }

  private partOf(questionId: string): "challenge" | "reward" {
    const inPart1 = this.tree?.part1ChallengeNodes.some(
      (node) => node.id === questionId,
    );
    return inPart1 ? "challenge" : "reward";
  }

  private emit(event: StateMachineEvent): void {
    for (const listener of this.listeners) {
      listener(event);
    }
  }
}
