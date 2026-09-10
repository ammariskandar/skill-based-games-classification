/**
 * Question set D — Challenge aesthetic (v1.0.0) — SBGC-173.
 *
 * Mirrors `apps/backend/classifications/questionnaire/registry/v1/set_d.py`.
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
    "When the player makes a mistake, how much does it hurt?",
    [
      opt(
        "Very heavily: One mistake can immediately lose a life, round, run, or fight.",
        { micro: 90 },
      ),
      opt(
        "Heavily but recoverably: Mistakes hurt, but good positioning, defence, or resources can save the situation.",
        { micro: 35, macro: 45 },
      ),
      opt(
        "Mostly absorbed by strategy: A strong build, team, deck, or setup can compensate for mistakes.",
        { micro: 10, macro: 70 },
      ),
      opt(
        "Physical execution barely matters: The challenge mainly comes from decisions.",
        { micro: -30 },
      ),
    ],
    { target: CHALLENGE, keyPhrase: "how much does it hurt" },
  ),
  question(
    "Q4",
    "Does the player need preparation before acting?",
    [opt("Yes", { next: "Q4A" }), opt("No", { next: "Q4B" })],
    { target: CHALLENGE, keyPhrase: "need preparation before acting" },
  ),
  question(
    "Q4A",
    "How important is that preparation?",
    [
      opt(
        "Decisive: A bad build, draft, deck, economy, or setup can put the player in a losing position before execution begins.",
        { macro: 80 },
      ),
      opt(
        "Important but recoverable: Good execution can overcome a bad setup.",
        { macro: 30, micro: 40 },
      ),
      opt("Minor: Preparation exists but is not a major part of success.", {
        macro: -20,
      }),
    ],
    { target: CHALLENGE, keyPhrase: "preparation" },
  ),
  question(
    "Q4B",
    "Without preparation, what mostly decides success?",
    [
      opt("Execution and positioning", {
        micro: 70,
        mystiko: 15,
        macro: -40,
      }),
      opt("Resource decisions during the game", { macro: 40, micro: 30 }),
    ],
    { target: CHALLENGE, keyPhrase: "what mostly decides success" },
  ),
  question(
    "Q5",
    "How much does the player have to work with incomplete information?",
    [
      opt(
        "A lot: Sound, hidden enemies, fog, clues, or prediction are essential.",
        { mystiko: 85 },
      ),
      opt(
        "Some: Scouting, vision, information gathering, or prediction matter.",
        { mystiko: 60, macro: 20 },
      ),
      opt(
        "Little: Enemies are usually visible and information is immediately available.",
        { mystiko: 20, micro: 40 },
      ),
      opt("None: Everything important is visible.", { mystiko: -30 }),
    ],
    { target: CHALLENGE, keyPhrase: "work with incomplete information" },
  ),
  question(
    "Q6",
    "How important is controlling space?",
    [
      opt(
        "Changing the environment: Destroying walls, opening paths, changing terrain, etc.",
        { next: "Q6A" },
      ),
      opt(
        "Controlling fixed space: Zones, waves, traps, abilities, positioning, etc.",
        { next: "Q6B" },
      ),
    ],
    { target: CHALLENGE, keyPhrase: "controlling space" },
  ),
  question(
    "Q6A",
    "How central is changing the environment?",
    [
      opt("Essential: Changing the environment is central to winning fights.", {
        mystiko: 60,
        macro: 40,
      }),
      opt(
        "Occasional: It helps, but most fights happen in predictable spaces.",
        { macro: 20, mystiko: 15 },
      ),
    ],
    { target: CHALLENGE, keyPhrase: "changing the environment" },
  ),
  question(
    "Q6B",
    "How do players control fixed space?",
    [
      opt("Abilities/units control space", { macro: 60 }),
      opt("Precise utility/timing controls space", { micro: 40, macro: 20 }),
      opt("Direct positioning wins space", { micro: 50 }),
    ],
    { target: CHALLENGE, keyPhrase: "control fixed space" },
  ),
  question(
    "Q7",
    "When there is a decisive clash, what usually determines the winner?",
    [
      opt("Execution: Aim, reactions, combos, movement, timing.", {
        micro: 90,
      }),
      opt(
        "A mix of everything: Information, preparation, decisions, and execution all matter heavily.",
        { micro: 35, macro: 35, mystiko: 35 },
      ),
      opt(
        "Team/system coordination: Ability combinations, cooldowns, positioning, roles, etc.",
        { macro: 75, micro: 15 },
      ),
      opt(
        "Numbers and setup: Better economy, build, cards, equipment, or scaling wins.",
        { macro: 85 },
      ),
    ],
    { target: CHALLENGE, keyPhrase: "usually determines the winner" },
  ),
  question(
    "Q8",
    "Does the game reward mind games or deception?",
    [opt("Yes", { next: "Q8A" }), opt("No", { next: "Q8B" })],
    { target: CHALLENGE, keyPhrase: "mind games or deception" },
  ),
  question(
    "Q8A",
    "What kind of deception is it?",
    [
      opt(
        "Fakes and conditioning: Making opponents expect one thing and doing another.",
        { mystiko: 70 },
      ),
      opt(
        "Baiting abilities/resources: Making the opponent waste something valuable before attacking.",
        { macro: 60, mystiko: 25 },
      ),
    ],
    { target: CHALLENGE, keyPhrase: "What kind of deception" },
  ),
  question(
    "Q8B",
    "Without deception, what decides the outcome?",
    [
      opt("Physical execution", { micro: 60 }),
      opt("Resource/system advantage", { macro: 40 }),
    ],
    { target: CHALLENGE, keyPhrase: "what decides the outcome" },
  ),
];

const PART2: QuestionNode[] = [
  question(
    "Q9",
    "What gives the biggest high-stakes payoff?",
    [
      opt("Pulling off an amazing clutch or difficult fight", { micro: 90 }),
      opt("Outsmarting the opponent", { next: "Q9A" }),
      opt("Executing a brilliant strategy/setup", { next: "Q9B" }),
    ],
    { target: REWARD, keyPhrase: "biggest high-stakes payoff" },
  ),
  question(
    "Q9A",
    "What kind of outsmarting is it?",
    [
      opt("Reading hidden information", { mystiko: 85 }),
      opt("Setting up the situation beforehand", { macro: 60, mystiko: 25 }),
    ],
    { target: REWARD, keyPhrase: "What kind of outsmarting" },
  ),
  question(
    "Q9B",
    "How was that strategy executed?",
    [
      opt("Team planning and coordination", { macro: 80 }),
      opt("Adapting quickly during chaos", { macro: 40, micro: 30 }),
    ],
    { target: REWARD, keyPhrase: "that strategy" },
  ),
  question(
    "Q10",
    "What best shows a player's mastery?",
    [
      opt("High rank", { macro: 85 }),
      opt("Amazing mechanical plays", { micro: 80 }),
      opt(
        "Deep game knowledge: Knowing obscure mechanics, maps, timings, counters, etc.",
        { mystiko: 60, macro: 25 },
      ),
      opt(
        "Pure intensity: The game is rewarding mainly because every moment feels high-stakes.",
        { micro: 30, mystiko: 30 },
      ),
    ],
    { target: REWARD, keyPhrase: "best shows a player's mastery" },
  ),
  question(
    "Q11",
    "When watching top-level play, what is most impressive?",
    [
      opt(
        "Mechanical skill: Incredible reactions, combos, aim, movement, etc.",
        { micro: 85 },
      ),
      opt(
        "Strategy: Drafts, compositions, resource plans, or coordinated tactics",
        { next: "Q11A" },
      ),
      opt("Mind games: Predictions, deception, traps, or clever reads", {
        mystiko: 80,
      }),
    ],
    { target: REWARD, keyPhrase: "what is most impressive" },
  ),
  question(
    "Q11A",
    "Do ordinary players copy professional strategies?",
    [
      opt("Yes, heavily", { macro: 85 }),
      opt("Rarely", { micro: 35, macro: 25 }),
    ],
    { target: REWARD, keyPhrase: "copy professional strategies" },
  ),
  question(
    "Q12",
    "When the player is tired, what breaks down first?",
    [
      opt("Physical execution", { micro: 80 }),
      opt("Game sense", { mystiko: 75, next: "Q12A" }),
      opt("Strategic decisions", { macro: 75, next: "Q12B" }),
    ],
    { target: REWARD, keyPhrase: "what breaks down first" },
  ),
  question(
    "Q12A",
    "Can raw skill compensate?",
    [opt("Yes", { micro: 40 }), opt("No", { mystiko: 40 })],
    { target: REWARD, keyPhrase: "raw skill" },
  ),
  question(
    "Q12B",
    "Can the player switch to a simpler/supporting role?",
    [opt("Yes", { macro: 50 }), opt("No", { micro: 30, macro: 20 })],
    { target: REWARD, keyPhrase: "switch to a simpler/supporting role" },
  ),
  question(
    "Q13",
    "Outside the actual match/run, what keeps players coming back?",
    [
      opt("Cosmetics and trading", { micro: 60, macro: 20 }),
      opt("New characters/classes/cards", { macro: 70, micro: 20 }),
      opt(
        "Mastery progression: Ranks, weapon mastery, achievements, account progression, etc.",
        { mystiko: 35, macro: 35 },
      ),
    ],
    { target: REWARD, keyPhrase: "what keeps players coming back" },
  ),
  question(
    "Q14",
    "When players lose, what is usually the real reason?",
    [
      opt("Bad strategy/team decisions", { macro: 85 }),
      opt("The opponent was mechanically better", { micro: 85 }),
      opt("They didn't see/read something", { mystiko: 80 }),
      opt("The system was exploited or cheated", {
        micro: 30,
        macro: 30,
        mystiko: 30,
      }),
    ],
    { target: REWARD, keyPhrase: "the real reason" },
  ),
];

export const SET_D: QuestionSetDefinition = buildSet(
  "D",
  "Challenge",
  PART1,
  PART2,
);
