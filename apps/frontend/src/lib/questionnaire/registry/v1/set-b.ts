/**
 * Question set B — Fantasy aesthetic (v1.0.0) — SBGC-173.
 *
 * Mirrors `apps/backend/classifications/questionnaire/registry/v1/set_b.py`.
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
    "How do animation timing and invincibility frames shape the challenge?",
    [
      opt("Frame-perfect", { micro: 85 }),
      opt("Paced/forgiving", { micro: 35, macro: 45 }),
      opt("Turn-based", { micro: -40, macro: 50 }),
      opt("Static hacking", { micro: 15, macro: 65 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q4",
    "How do you get past a boss that walls you?",
    [
      opt("Build/buffs", { next: "Q4A" }),
      opt("Attack telegraphs", { next: "Q4B" }),
      opt("Creative/dialogue", { next: "Q4C" }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q4A",
    "How decisive is your preparation?",
    [
      opt("Stat-check", { macro: 85 }),
      opt("Helpful", { macro: 50, micro: 35 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q4B",
    "What is the primary execution skill?",
    [
      opt("Muscle memory", { micro: 80, mystiko: 20 }),
      opt("Pattern recognition", { micro: 50, mystiko: 50 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q4C",
    "How do you bypass combat entirely?",
    [
      opt("Creative systems", { mystiko: 60, macro: 40 }),
      opt("Dialogue", { mystiko: 80 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q5",
    "How do you decipher enemy attacks?",
    [
      opt("Deceptive telegraphs", { mystiko: 75, micro: 25 }),
      opt("Elemental weaknesses", { mystiko: 65, macro: 35 }),
      opt("Predictable AI", { mystiko: -30, macro: 40 }),
      opt("Turn economy", { mystiko: 45, macro: 55 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q6",
    "Is party synergy and build-crafting central to your play?",
    [opt("Core spine", { next: "Q6A" }), opt("Solo/loadout", { next: "Q6B" })],
    { target: CHALLENGE },
  ),
  question(
    "Q6A",
    "Which system complexity do you enjoy most?",
    [
      opt("Party turns", { macro: 85, mystiko: 15 }),
      opt("Skill trees/crafting", { macro: 85 }),
      opt("Elemental rotations", { macro: 60, micro: 30 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q6B",
    "What matters most when playing solo?",
    [
      opt("Moveset feel", { micro: 80 }),
      opt("Fashion", { mystiko: 50, micro: 20 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q7",
    "How much does arena and terrain impact a fight?",
    [
      opt("Surfaces/Verticality", { macro: 70, mystiko: 35 }),
      opt("Hazardous bounds", { micro: 70, mystiko: 20 }),
      opt("Open fields", { macro: -20, micro: 20 }),
    ],
    { target: CHALLENGE },
  ),
  question(
    "Q8",
    "How do you engage with lore and dialogue?",
    [
      opt("Extensive dialogue", { mystiko: 80, macro: 20 }),
      opt("Cryptic storytelling", { mystiko: 90 }),
      opt("Waypoints", { mystiko: -30, macro: 30 }),
    ],
    { target: CHALLENGE },
  ),
];

const PART2: QuestionNode[] = [
  question(
    "Q9",
    "Do you chase character or cosmetic rewards?",
    [opt("Yes", { next: "Q9A" }), opt("No", { next: "Q9B" })],
    { target: REWARD },
  ),
  question(
    "Q9A",
    "How do you prefer to acquire them?",
    [
      opt("Gacha", { micro: 70, macro: 30 }),
      opt("Boss drop drip", { micro: 60, mystiko: 30 }),
      opt("Crafted/modded", { macro: 45, mystiko: 35 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q9B",
    "What drives your progression?",
    [
      opt("Raw stats", { macro: 80 }),
      opt("Gameplay utility", { mystiko: 70, macro: 20 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q10",
    "What gives you wonder and immersion?",
    [
      opt("Vistas/Score", { mystiko: 120 }),
      opt("Emergent discovery", { mystiko: 110, macro: 20 }),
      opt("Power fantasy", { macro: 60, micro: 50 }),
      opt("Companion intimacy", { mystiko: 90 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q11",
    "What investment would you regret losing most?",
    [
      opt("Curated build", { macro: 85 }),
      opt("Emotional journey", { mystiko: 90 }),
      opt("Character roster", { next: "Q11A" }),
    ],
    { target: REWARD },
  ),
  question(
    "Q11A",
    "How is your roster assembled?",
    [
      opt("Money/gacha", { micro: 75, macro: 30 }),
      opt("Solo clears", { micro: 80 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q12",
    "How do you flex your long-term progress?",
    [
      opt("Raid leaderboards", { macro: 90 }),
      opt("PvP duels", { micro: 80, macro: 15 }),
      opt("Whaling dominance", { macro: 80, micro: 25 }),
      opt("Solo self-contained", { mystiko: 80 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q13",
    "How does fatigue show up for you?",
    [
      opt("Mechanical disaster", { micro: 80 }),
      opt("Cognitive overload", { next: "Q13A" }),
      opt("Zero fatigue", { mystiko: 90 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q13A",
    "What breaks down first when tired?",
    [
      opt("Dialogue/puzzles", { mystiko: 75 }),
      opt("Inventory/perks", { macro: 85 }),
    ],
    { target: REWARD },
  ),
  question(
    "Q14",
    "What is the most exhilarating high?",
    [
      opt("Finally Defeated", { micro: 90 }),
      opt("Galaxy Brain build", { macro: 85 }),
      opt("Legendary secret", { mystiko: 100 }),
      opt("Golden Gacha", { micro: 65, macro: 25 }),
    ],
    { target: REWARD },
  ),
];

export const SET_B: QuestionSetDefinition = buildSet(
  "B",
  "Fantasy",
  PART1,
  PART2,
);
