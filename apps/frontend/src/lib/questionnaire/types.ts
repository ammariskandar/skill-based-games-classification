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
