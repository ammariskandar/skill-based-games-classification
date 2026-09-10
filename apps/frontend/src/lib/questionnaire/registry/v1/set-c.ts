/**
 * Question set C — Narrative aesthetic (v1.0.0) — SBGC-173.
 *
 * Mirrors `apps/backend/classifications/questionnaire/registry/v1/set_c.py`.
 * Weights use the registry notation: μ = micro, M = macro, κ = mystiko.
 */

import {
  buildSet,
  opt,
  question,
  type ProfileTarget,
  type QuestionNode,
  type QuestionSetDefinition,
} from "./types";

const CHALLENGE: ProfileTarget = "CHALLENGE";
const REWARD: ProfileTarget = "REWARD";

const PART1: QuestionNode[] = [
  question(
    "Q3",
    "How much does real-time precision matter?",
    [
      opt("Gunplay/reflexes", { micro: 75 }),
      opt("QTEs", { micro: 10, mystiko: 40 }),
      opt("Turn-based", { micro: -40, macro: 30 }),
      opt("Passive narrative", { micro: -50 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q4",
    "Do scarcity and scheduling drive your decisions?",
    [opt("Yes", { next: "Q4A" }), opt("No", { next: "Q4B" })],
    { target: CHALLENGE },
  ),
  question(
    "Q4A",
    "Which resource pressure shapes your play?",
    [
      opt("Survival crafting", { macro: 85, micro: 25 }),
      opt("Calendar allocation", { macro: 85 }),
      opt("Standard consumables", { macro: 25 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q4B",
    "How do you bypass a roadblock?",
    [
      opt("Crime scene reconstruction", { mystiko: 85 }),
      opt("Emotional dilemmas", { mystiko: 45 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q5",
    "How do you solve the antagonist's mental puzzle?",
    [
      opt("Human deceit", { mystiko: 85 }),
      opt("Turn rotations", { mystiko: 55, macro: 35 }),
      opt("Patrol AI", { micro: 45, macro: 25, mystiko: 15 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q6",
    "What does failure cost you?",
    [
      opt("Permanent tragedy", { next: "Q6A" }),
      opt("Game Over", { next: "Q6B" }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q6A",
    "How do you prevent the tragedy?",
    [
      opt("Subtext/empathy", { mystiko: 90 }),
      opt("QTE execution", { micro: 30, mystiko: 60 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q6B",
    "Why did you hit Game Over?",
    [
      opt("Exhausted supplies", { macro: 50, micro: 40 }),
      opt("Unoptimized party", { macro: 75, mystiko: 15 }),
      opt("Missed reflex", { micro: 70 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q7",
    "How do you gain a pre-conflict advantage?",
    [
      opt("Stealth/acoustics", { macro: 45, micro: 45 }),
      opt("Ambush priority", { macro: 30, mystiko: 30 }),
      opt("Investigative reconstruction", { mystiko: 90 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q8",
    "Where does the deepest complexity live for you?",
    [
      opt("Flowchart", { mystiko: 95 }),
      opt("Fusion/stat min-max", { macro: 90 }),
      opt("Workbench", { macro: 55, micro: 35 }),
    ],
    { target: CHALLENGE },
  ),
];

const PART2: QuestionNode[] = [
  question(
    "Q9",
    "Do you chase galleries and archives?",
    [opt("Yes", { next: "Q9A" }), opt("No", { next: "Q9B" })],
    { target: REWARD },
  ),
  question(
    "Q9A",
    "Which unlock category matters most?",
    [
      opt("In-game museum/Den", { micro: 85, macro: 15 }),
      opt("World artifacts/letters", { mystiko: 85 }),
      opt("Flowchart nodes", { mystiko: 60, macro: 30 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q9B",
    "What drives your progression?",
    [
      opt("Visual gear upgrades", { micro: 50, macro: 30 }),
      opt("Companion reactions", { mystiko: 65 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q10",
    "What is the deepest payoff?",
    [
      opt("Moral ambiguity", { mystiko: 110 }),
      opt("Golden Ending", { mystiko: 80, macro: 30 }),
      opt("Hard survival", { micro: 60, macro: 50 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q11",
    "Do you seek out secret encounters?",
    [opt("Yes", { next: "Q11A" }), opt("No", { next: "Q11B" })],
    { target: REWARD },
  ),
  question(
    "Q11A",
    "What form do those secrets take?",
    [
      opt("Superbosses", { macro: 75, mystiko: 35 }),
      opt("Hidden epilogues", { mystiko: 90 }),
      opt("Locked supply safes", { mystiko: 45, macro: 45 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q11B",
    "What rewards you without secrets?",
    [opt("Cinematic acting", { mystiko: 60, micro: 40 })],
    { target: REWARD },
  ),
  question(
    "Q12",
    "What gives you achievement pride?",
    [
      opt("Completionist compendium", { macro: 85 }),
      opt("Natural story trophies", { macro: 30, mystiko: 45 }),
      opt("Irrelevant", { mystiko: 75 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q13",
    "How does fatigue show up in a session?",
    [
      opt("Loss of mechanics", { micro: 80 }),
      opt("Loss of immersion", { mystiko: 85 }),
      opt("Systemic exhaustion", { macro: 85 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q14",
    "What memory endures after you stop playing?",
    [
      opt("Style/music/UI", { micro: 80, mystiko: 20 }),
      opt("Moral dilemmas", { mystiko: 100 }),
      opt("Survival tension", { macro: 60, micro: 30 }),
    ],
    { target: REWARD },
  ),
];

export const SET_C: QuestionSetDefinition = buildSet(
  "C",
  "Narrative",
  PART1,
  PART2,
);
