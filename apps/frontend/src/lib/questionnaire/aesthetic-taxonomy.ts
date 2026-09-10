/**
 * Aesthetic taxonomy and combinatoric resolver — SBGC-172 (Epic SBGC-171).
 *
 * Mirrors `apps/backend/classifications/questionnaire/` exactly so the browser
 * can switch question sets with zero latency while the backend remains the
 * authoritative resolver at submission time.  Pure data + pure functions only.
 */

import {
  AestheticCategory,
  QuestionSetId,
  type AestheticOption,
  type AestheticResolution,
  type Part2SplitConfig,
} from "./types";

/** Option identifier → aesthetic category (Q1/Q2 shared taxonomy). */
export const OPTION_TAXONOMY: Readonly<Record<string, AestheticCategory>> = {
  OPT_S1: AestheticCategory.SENSORY,
  OPT_S2: AestheticCategory.SENSORY,
  OPT_S3: AestheticCategory.SENSORY,
  OPT_S4: AestheticCategory.SENSORY,
  OPT_S5: AestheticCategory.SENSORY,
  OPT_S6: AestheticCategory.SENSORY,
  OPT_F1: AestheticCategory.FANTASY,
  OPT_F2: AestheticCategory.FANTASY,
  OPT_F3: AestheticCategory.FANTASY,
  OPT_F4: AestheticCategory.FANTASY,
  OPT_N1: AestheticCategory.NARRATIVE,
  OPT_N2: AestheticCategory.NARRATIVE,
  OPT_C1: AestheticCategory.CHALLENGE,
  OPT_C2: AestheticCategory.CHALLENGE,
  OPT_C3: AestheticCategory.CHALLENGE,
  OPT_C4: AestheticCategory.CHALLENGE,
  OPT_COL: AestheticCategory.COLLABORATIVE,
  OPT_NONE: AestheticCategory.NONE,
};

/**
 * Question 1 — "primary reason for fun".  `OPT_NONE` is intentionally excluded:
 * it is only offered in Question 2.
 */
export const PRIMARY_OPTIONS: readonly AestheticOption[] = [
  {
    optionId: "OPT_S1",
    label: "The music is good",
    category: AestheticCategory.SENSORY,
    emphasis: { text: "music", color: "purple" },
  },
  {
    optionId: "OPT_S2",
    label: "The graphics and/or art is beautiful",
    category: AestheticCategory.SENSORY,
    emphasis: { text: "graphics and/or art", color: "reddish-pink" },
  },
  {
    optionId: "OPT_S3",
    label: "It gets my blood pumping from the action",
    category: AestheticCategory.SENSORY,
    emphasis: { text: "action", color: "reddish" },
  },
  {
    optionId: "OPT_S4",
    label: "It provides a thrilling scare",
    category: AestheticCategory.SENSORY,
    emphasis: { text: "scare", color: "white" },
  },
  {
    optionId: "OPT_S5",
    label: "It is sexually gratifying",
    category: AestheticCategory.SENSORY,
    emphasis: { text: "sexually", color: "pink" },
  },
  {
    optionId: "OPT_S6",
    label: "It is therapeutic",
    category: AestheticCategory.SENSORY,
    emphasis: { text: "therapeutic", color: "green" },
  },
  {
    optionId: "OPT_F1",
    label: "I get to build a world of my own",
    category: AestheticCategory.FANTASY,
    emphasis: { text: "build a world of my own", color: "light-blue" },
  },
  {
    optionId: "OPT_F2",
    label: "I get to live a life I normally would not be able to",
    category: AestheticCategory.FANTASY,
    emphasis: {
      text: "normally would not be able to",
      color: "purplish-light-blue",
    },
  },
  {
    optionId: "OPT_F3",
    label: "I get to experience new things or places",
    category: AestheticCategory.FANTASY,
    emphasis: { text: "new things or places", color: "golden" },
  },
  {
    optionId: "OPT_F4",
    label: "I can change history",
    category: AestheticCategory.FANTASY,
    emphasis: { text: "history", color: "blue" },
  },
  {
    optionId: "OPT_N1",
    label: "It has a very compelling story",
    category: AestheticCategory.NARRATIVE,
    emphasis: { text: "story", color: "orange" },
  },
  {
    optionId: "OPT_N2",
    label: "I get attached to the characters",
    category: AestheticCategory.NARRATIVE,
    emphasis: { text: "attached to the characters", color: "lime" },
  },
  {
    optionId: "OPT_C1",
    label: "It's difficult, and that alone makes it fun",
    category: AestheticCategory.CHALLENGE,
    emphasis: { text: "difficult", color: "blood-red" },
  },
  {
    optionId: "OPT_C2",
    label: "I am much better than everyone else in this game",
    category: AestheticCategory.CHALLENGE,
    emphasis: { text: "better than everyone else", color: "yellow" },
  },
  {
    optionId: "OPT_C3",
    label: "It is incredibly rewarding to see my strategies pay off",
    category: AestheticCategory.CHALLENGE,
    emphasis: { text: "strategies", color: "teal" },
  },
  {
    optionId: "OPT_C4",
    label: "It's fun beating my own or other people's records",
    category: AestheticCategory.CHALLENGE,
    emphasis: { text: "records", color: "light-brown" },
  },
  {
    optionId: "OPT_COL",
    label: "It's just fun playing/competing with friends",
    category: AestheticCategory.COLLABORATIVE,
    emphasis: { text: "friends", color: "pantone-green" },
  },
];

/** The Q2-only sentinel option. */
export const NONE_OPTION: AestheticOption = {
  optionId: "OPT_NONE",
  label: "None of the above.",
  category: AestheticCategory.NONE,
};

/** Question 2 offers every Q1 option except the Q1 selection, plus `OPT_NONE`. */
export const SECONDARY_OPTION_POOL: readonly AestheticOption[] = [
  ...PRIMARY_OPTIONS,
  NONE_OPTION,
];

/** Option identifier → full option record. */
export const OPTION_BY_ID: Readonly<Record<string, AestheticOption>> =
  Object.fromEntries(
    SECONDARY_OPTION_POOL.map((option) => [option.optionId, option]),
  );

// ═══ domain errors ═══

export class QuestionnaireDomainError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "QuestionnaireDomainError";
  }
}

export class UnknownOptionError extends QuestionnaireDomainError {
  constructor(readonly optionId: string) {
    super(`Unknown questionnaire option '${optionId}'.`);
    this.name = "UnknownOptionError";
  }
}

export class InvalidOptionSelectionError extends QuestionnaireDomainError {
  constructor(
    readonly optionId: string,
    readonly question: string,
  ) {
    super(`Option '${optionId}' cannot be selected for ${question}.`);
    this.name = "InvalidOptionSelectionError";
  }
}

export class UnresolvableAestheticError extends QuestionnaireDomainError {
  constructor(
    readonly cat1: AestheticCategory,
    readonly cat2: AestheticCategory,
  ) {
    super(`No aesthetic resolution exists for '${cat1}' + '${cat2}'.`);
    this.name = "UnresolvableAestheticError";
  }
}

// ═══ resolution maps ═══

/** Part 1 (Challenge, Q3–Q8) — one set per canonical aesthetic. */
export const PART1_SET_MAP: Readonly<Record<string, QuestionSetId>> = {
  [AestheticCategory.SENSORY]: QuestionSetId.SET_1A,
  [AestheticCategory.FANTASY]: QuestionSetId.SET_1B,
  [AestheticCategory.NARRATIVE]: QuestionSetId.SET_1C,
  [AestheticCategory.CHALLENGE]: QuestionSetId.SET_1D,
};

/** Part 2 (Reward, Q9–Q14) — one set per canonical aesthetic. */
export const PART2_SET_MAP: Readonly<Record<string, QuestionSetId>> = {
  [AestheticCategory.SENSORY]: QuestionSetId.SET_2A,
  [AestheticCategory.FANTASY]: QuestionSetId.SET_2B,
  [AestheticCategory.NARRATIVE]: QuestionSetId.SET_2C,
  [AestheticCategory.CHALLENGE]: QuestionSetId.SET_2D,
};

const CANONICAL_AESTHETICS: readonly AestheticCategory[] = [
  AestheticCategory.SENSORY,
  AestheticCategory.FANTASY,
  AestheticCategory.NARRATIVE,
  AestheticCategory.CHALLENGE,
];

function isCanonicalAesthetic(
  category: AestheticCategory,
): category is
  | AestheticCategory.SENSORY
  | AestheticCategory.FANTASY
  | AestheticCategory.NARRATIVE
  | AestheticCategory.CHALLENGE {
  return CANONICAL_AESTHETICS.includes(category);
}

// ═══ public helpers ═══

/** Return the aesthetic category for `optionId`. */
export function mapOptionToCategory(optionId: string): AestheticCategory {
  const category = OPTION_TAXONOMY[optionId];
  if (category === undefined) {
    throw new UnknownOptionError(optionId);
  }
  return category;
}

/**
 * Return the Question 2 option set for a given Question 1 selection.
 *
 * Q2 excludes the exact option selected in Q1 and always appends `OPT_NONE`.
 * `OPT_NONE` itself is not a valid Q1 selection.
 */
export function availableSecondaryOptions(
  q1OptionId: string,
): readonly AestheticOption[] {
  const primary = OPTION_BY_ID[q1OptionId];
  if (primary === undefined) {
    throw new UnknownOptionError(q1OptionId);
  }
  if (primary.category === AestheticCategory.NONE) {
    throw new InvalidOptionSelectionError(q1OptionId, "Question 1");
  }
  return [
    ...PRIMARY_OPTIONS.filter((option) => option.optionId !== q1OptionId),
    NONE_OPTION,
  ];
}

/**
 * Resolve the Q1/Q2 category pair into its dispatch contract.
 *
 * Throws {@link UnresolvableAestheticError} for pairs the matrix cannot
 * represent (e.g. `COLLABORATIVE` in both questions, or `NONE` in Q1).
 */
export function resolveAesthetic(
  cat1: AestheticCategory,
  cat2: AestheticCategory,
): AestheticResolution {
  // 1. Collaborative + None → reserved special flow.
  if (cat1 === AestheticCategory.COLLABORATIVE) {
    if (cat2 === AestheticCategory.NONE) {
      return specialFlowResult();
    }
    // 2. Collaborative Q1 + standard Q2 → true aesthetic of Q2.
    if (isCanonicalAesthetic(cat2)) {
      return buildTrueAestheticResult(cat2);
    }
    throw new UnresolvableAestheticError(cat1, cat2);
  }

  if (!isCanonicalAesthetic(cat1)) {
    throw new UnresolvableAestheticError(cat1, cat2);
  }

  // 3. Standard Q1 + Collaborative / None / identical Q2 → true aesthetic of Q1.
  if (
    cat2 === AestheticCategory.COLLABORATIVE ||
    cat2 === AestheticCategory.NONE ||
    cat2 === cat1
  ) {
    return buildTrueAestheticResult(cat1);
  }

  // 4. Two different standard aesthetics → hybrid 50/50 split.
  if (isCanonicalAesthetic(cat2)) {
    return {
      dominantAesthetic: cat1,
      secondaryAesthetic: cat2,
      isTrueAesthetic: false,
      part1ChallengeSet: PART1_SET_MAP[cat1],
      part2RewardConfig: {
        isSplit: true,
        q9ToQ11Set: PART2_SET_MAP[cat2],
        q12ToQ14Set: PART2_SET_MAP[cat1],
      },
    };
  }

  throw new UnresolvableAestheticError(cat1, cat2);
}

/**
 * Resolve raw Q1/Q2 option identifiers into their dispatch contract.
 *
 * Validates both options against the registry and enforces that the Q2
 * selection is available for the given Q1 selection (unknown options,
 * `OPT_NONE` in Q1, and replaying the Q1 option in Q2 are all rejected).
 */
export function resolveFromOptions(
  q1OptionId: string,
  q2OptionId: string,
): AestheticResolution {
  const cat1 = mapOptionToCategory(q1OptionId);
  if (cat1 === AestheticCategory.NONE) {
    throw new InvalidOptionSelectionError(q1OptionId, "Question 1");
  }
  if (OPTION_TAXONOMY[q2OptionId] === undefined) {
    throw new UnknownOptionError(q2OptionId);
  }
  if (q2OptionId === q1OptionId) {
    throw new InvalidOptionSelectionError(q2OptionId, "Question 2");
  }

  const cat2 = mapOptionToCategory(q2OptionId);
  return resolveAesthetic(cat1, cat2);
}

// ═══ internal builders ═══

function buildTrueAestheticResult(
  dominant: AestheticCategory,
): AestheticResolution {
  const part2Set = PART2_SET_MAP[dominant];
  return {
    dominantAesthetic: dominant,
    secondaryAesthetic: null,
    isTrueAesthetic: true,
    part1ChallengeSet: PART1_SET_MAP[dominant],
    part2RewardConfig: {
      isSplit: false,
      q9ToQ11Set: part2Set,
      q12ToQ14Set: part2Set,
    },
  };
}

function specialFlowResult(): AestheticResolution {
  const part2Config: Part2SplitConfig = {
    isSplit: false,
    q9ToQ11Set: QuestionSetId.SPECIAL,
    q12ToQ14Set: QuestionSetId.SPECIAL,
  };
  return {
    dominantAesthetic: AestheticCategory.SPECIAL_FLOW,
    secondaryAesthetic: null,
    isTrueAesthetic: false,
    part1ChallengeSet: QuestionSetId.SPECIAL,
    part2RewardConfig: part2Config,
  };
}

export { AestheticCategory, QuestionSetId };
export type { AestheticOption, AestheticResolution, Part2SplitConfig };
