/**
 * Questionnaire domain types — SBGC-172 (Epic SBGC-171).
 *
 * Pure TypeScript vocabulary mirrored one-to-one by the Python domain module
 * (`apps/backend/classifications/questionnaire/domain.py`).  Client-side
 * question-set switching must produce exactly the same resolution as the
 * backend, so the enums and identifiers are intentionally duplicated.
 *
 * No runtime imports: this module is safe to import from anywhere (SSR,
 * client script, unit test).
 */

/** Reason-for-fun taxonomy produced by Questions 1 and 2. */
export enum AestheticCategory {
  SENSORY = "SENSORY",
  FANTASY = "FANTASY",
  NARRATIVE = "NARRATIVE",
  CHALLENGE = "CHALLENGE",
  COLLABORATIVE = "COLLABORATIVE",
  NONE = "NONE",
  SPECIAL_FLOW = "SPECIAL_FLOW",
}

/** Immutable questionnaire set identifiers (Part 1 Challenge / Part 2 Reward). */
export enum QuestionSetId {
  SET_1A = "1A",
  SET_1B = "1B",
  SET_1C = "1C",
  SET_1D = "1D",
  SET_2A = "2A",
  SET_2B = "2B",
  SET_2C = "2C",
  SET_2D = "2D",
  SPECIAL = "SPECIAL",
}

/** One Q1/Q2 answer option and its deterministic aesthetic category. */
export interface AestheticOption {
  optionId: string;
  label: string;
  category: AestheticCategory;
}

/** Reward (Part 2) question-set routing for Q9–Q14. */
export interface Part2SplitConfig {
  isSplit: boolean;
  q9ToQ11Set: QuestionSetId;
  q12ToQ14Set: QuestionSetId;
}

/** Resolved aesthetic plus the Part 1/Part 2 dispatch contract. */
export interface AestheticResolution {
  dominantAesthetic: AestheticCategory;
  secondaryAesthetic: AestheticCategory | null;
  isTrueAesthetic: boolean;
  part1ChallengeSet: QuestionSetId;
  part2RewardConfig: Part2SplitConfig;
}

/** How a community submission was generated — SBGC-175. */
export type SubmissionSource = "MANUAL" | "QUESTIONNAIRE";

/** Precedence ledger state for a (user, game) questionnaire — SBGC-175. */
export type PrecedenceStatus =
  | "ACTIVE_IN_CALCULATION"
  | "SUPERSEDED_BY_MANUAL"
  | "ARCHIVED_KEPT_MANUAL"
  | "STAFF_EDITORIAL_ROUTED";

/** User's resolution for a recent-manual conflict — SBGC-175. */
export type ConflictResolution = "OVERWRITE" | "KEEP_MANUAL";

/** One three-dimensional profile (micro / macro / mystiko). */
export interface QuestionnaireProfile {
  micro: number;
  macro: number;
  mystiko: number;
}

/**
 * The validated questionnaire scoring payload sent to the persistence engine
 * (SBGC-175 / SBGC-176).
 */
export interface QuestionnaireSubmissionPayload {
  version: string;
  dominantAesthetic: AestheticCategory;
  secondaryAesthetic: AestheticCategory | null;
  isTrueAesthetic: boolean;
  answers: Record<string, string>;
  q15Rating: number;
  raw: { challenge: QuestionnaireProfile; reward: QuestionnaireProfile };
  normalized: {
    challenge: QuestionnaireProfile;
    reward: QuestionnaireProfile;
  };
  adjusted: {
    challenge: QuestionnaireProfile;
    reward: QuestionnaireProfile;
  };
}

/** Conflict evaluation returned before a recent-manual submission — SBGC-175. */
export interface PrecedenceEvaluation {
  hasConflict: boolean;
  requiresUserChoice: boolean;
  manualSubmissionId: number | null;
  manualCreatedAt: string | null;
  ageDays: number | null;
}

// ── API wire contracts (SBGC-176) ──
// Field names mirror the Django Ninja JSON exactly; no client-side mapping is
// performed by the server API boundary.

/** Conflict metadata as serialized by `GET /questionnaire/{slug}/session`. */
export interface QuestionnairePrecedenceDto {
  has_conflict: boolean;
  requires_user_choice: boolean;
  manual_submission_id: number | null;
  manual_created_at: string | null;
  age_days: number | null;
}

/** Summary of the viewer's most recent questionnaire result. */
export interface QuestionnairePreviousResultDto {
  result_id: number;
  version: string;
  dominant_aesthetic: string;
  secondary_aesthetic: string | null;
  is_true_aesthetic: boolean;
  q15_rating: number;
  adjusted_challenge: QuestionnaireProfile;
  adjusted_reward: QuestionnaireProfile;
  status: PrecedenceStatus;
  created_at: string;
}

/** `GET /api/v1/questionnaire/{slug}/session` response body. */
export interface QuestionnaireSessionResponse {
  game_slug: string;
  game_name: string;
  canonical_aesthetic: string | null;
  precedence: QuestionnairePrecedenceDto;
  previous_result: QuestionnairePreviousResultDto | null;
}

/** `POST /api/v1/questionnaire/{slug}/submit` request body. */
export interface QuestionnaireSubmitRequest {
  version: string;
  q1_option_id: string;
  q2_option_id: string;
  answers: Record<string, string>;
  q15_rating: number;
  adjusted_challenge: QuestionnaireProfile;
  adjusted_reward: QuestionnaireProfile;
  conflict_resolution?: ConflictResolution | null;
}

/** `POST /api/v1/questionnaire/{slug}/submit` success body. */
export interface QuestionnaireSubmitResponse {
  success: boolean;
  questionnaire_result_id: number;
  classification_status: PrecedenceStatus;
  is_active_in_calculation: boolean;
  routed_to_editorial: boolean;
  message: string;
  challenge: QuestionnaireProfile;
  reward: QuestionnaireProfile;
}

/** HTTP 409 body when a recent manual submission needs a user decision. */
export interface ConflictRequiredResponse {
  error: "conflict_resolution_required";
  message: string;
  precedence: QuestionnairePrecedenceDto;
}
