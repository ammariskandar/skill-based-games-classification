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
    "How much does physical skill matter for surviving?",
    [
      opt(
        "A lot: Aiming, dodging, movement, or fast reactions are important.",
        {
          micro: 75,
        },
      ),
      opt("Some: There are QTEs or occasional timing checks.", {
        micro: 10,
        mystiko: 40,
      }),
      opt("Little: Combat uses turns, menus, cards, or choices.", {
        micro: -40,
        macro: 30,
      }),
      opt(
        "None: The game mainly asks the player to read, investigate, explore, or choose dialogue.",
        { micro: -50 },
      ),
    ],
    {
      target: CHALLENGE,
      keyPhrase: "physical skill",
    },
  ),
  question(
    "Q4",
    "Does the game put pressure on time or resources?",
    [opt("Yes", { next: "Q4A" }), opt("No", { next: "Q4B" })],
    {
      target: CHALLENGE,
      keyPhrase: "pressure on time or resources",
    },
  ),
  question(
    "Q4A",
    "What kind of pressure is it?",
    [
      opt(
        "Survival resources: Ammunition, health, crafting materials, money, etc. are scarce.",
        { macro: 85, micro: 25 },
      ),
      opt(
        "Limited time: Days, schedules, deadlines, or action points force difficult choices.",
        { macro: 85 },
      ),
      opt("Resources exist but are comfortable", { macro: 25 }),
    ],
    { target: CHALLENGE, keyPhrase: "What kind of pressure" },
  ),
  question(
    "Q4B",
    "Without time or resource pressure, how do players get past obstacles?",
    [
      opt("Investigating clues is how players get past obstacles", {
        mystiko: 85,
      }),
      opt("Understanding people/choices is the main challenge", {
        mystiko: 45,
      }),
    ],
    { target: CHALLENGE, keyPhrase: "get past obstacles" },
  ),
  question(
    "Q5",
    "When the game gives the player a mystery, what must they do?",
    [
      opt(
        "Read people: Detect lies, understand motives, or predict what someone will do.",
        { mystiko: 85 },
      ),
      opt("Predict combat: Learn attacks, weaknesses, or enemy patterns.", {
        mystiko: 55,
        macro: 35,
      }),
      opt("Study behaviour: Watch patrols, sound, sightlines, and timing.", {
        micro: 45,
        macro: 25,
        mystiko: 15,
      }),
    ],
    { target: CHALLENGE, keyPhrase: "gives the player a mystery" },
  ),
  question(
    "Q6",
    "What happens when the player makes a major mistake?",
    [
      opt("The story permanently changes", { next: "Q6A" }),
      opt("Game Over/checkpoint", { next: "Q6B" }),
    ],
    { target: CHALLENGE, keyPhrase: "makes a major mistake" },
  ),
  question(
    "Q6A",
    "What prevents the permanent change?",
    [
      opt("Reading people and choices prevents it", { mystiko: 90 }),
      opt("Fast reactions prevent it", { micro: 30, mystiko: 60 }),
    ],
    { target: CHALLENGE, keyPhrase: "prevents the permanent change" },
  ),
  question(
    "Q6B",
    "What usually causes the Game Over?",
    [
      opt("Running out of supplies", { macro: 50, micro: 40 }),
      opt("Bad party/setup decisions", { macro: 75, mystiko: 15 }),
      opt("Bad physical execution", { micro: 70 }),
    ],
    { target: CHALLENGE, keyPhrase: "causes the Game Over" },
  ),
  question(
    "Q7",
    "How can players gain an advantage before a confrontation?",
    [
      opt("Stealth and positioning", { macro: 45, micro: 45 }),
      opt(
        "Getting the first move by watching enemies and choosing the right moment",
        { macro: 30, mystiko: 30 },
      ),
      opt(
        "Investigating beforehand: Finding evidence, secrets, weaknesses, or useful information",
        { mystiko: 90 },
      ),
    ],
    {
      target: CHALLENGE,
      keyPhrase: "advantage before a confrontation",
    },
  ),
  question(
    "Q8",
    "Where is the game's deepest complexity?",
    [
      opt(
        "Story choices: Many decisions lead to different scenes, characters, or endings.",
        { mystiko: 95 },
      ),
      opt(
        "Character/system building: Skills, equipment, abilities, or party choices interact deeply.",
        { macro: 90 },
      ),
      opt("Upgrading survival/combat tools", { macro: 55, micro: 35 }),
    ],
    { target: CHALLENGE, keyPhrase: "game's deepest complexity" },
  ),
];

const PART2: QuestionNode[] = [
  question(
    "Q9",
    "Does the game reward players with extra story or lore?",
    [opt("Yes", { next: "Q9A" }), opt("No", { next: "Q9B" })],
    { target: REWARD, keyPhrase: "extra story or lore" },
  ),
  question(
    "Q9A",
    "What kind of extra content is it?",
    [
      opt("Art/audio extras: Galleries, music, cutscenes, models, etc.", {
        micro: 85,
        macro: 15,
      }),
      opt("World lore: Notes, recordings, books, environmental details, etc.", {
        mystiko: 85,
      }),
      opt("Story branches: New scenes, paths, character fates, or endings.", {
        mystiko: 60,
        macro: 30,
      }),
    ],
    { target: REWARD, keyPhrase: "What kind of extra content" },
  ),
  question(
    "Q9B",
    "Without extra lore, what drives progression?",
    [
      opt("Visible equipment upgrades", { micro: 50, macro: 30 }),
      opt("Changing relationships", { mystiko: 65 }),
      opt(
        "World exploration and discovery: Finding hidden areas, environmental details, or optional locations that expand the setting.",
        { mystiko: 60, macro: 20 },
      ),
    ],
    { target: REWARD, keyPhrase: "what drives progression" },
  ),
  question(
    "Q10",
    "What makes the game's big emotional payoff?",
    [
      opt("A powerful ending or tragedy", { mystiko: 110 }),
      opt("Solving the central mystery and reaching the true ending", {
        mystiko: 80,
        macro: 30,
      }),
      opt("Surviving something extremely difficult", { micro: 60, macro: 50 }),
    ],
    { target: REWARD, keyPhrase: "big emotional payoff" },
  ),
  question(
    "Q11",
    "Does exploring the world reveal secret story content?",
    [opt("Yes", { next: "Q11A" }), opt("No", { next: "Q11B" })],
    { target: REWARD, keyPhrase: "secret story content" },
  ),
  question(
    "Q11A",
    "What kind of secret content is it?",
    [
      opt("Secret bosses/content", { macro: 75, mystiko: 35 }),
      opt("Hidden story revelations", { mystiko: 90 }),
      opt("Clues, codes, and hidden rooms", { mystiko: 45, macro: 45 }),
    ],
    { target: REWARD, keyPhrase: "What kind of secret content" },
  ),
  question(
    "Q11B",
    "Without secrets, what keeps the player engaged?",
    [
      opt("Cinematic pacing and acting", { mystiko: 60, micro: 40 }),
      opt(
        "Character relationships: Following character interactions, personal conflicts, and changing relationships keeps the player invested.",
        { mystiko: 80 },
      ),
      opt(
        "The main story itself: Following the central plot, its major events, and how it unfolds keeps the player engaged.",
        { mystiko: 75 },
      ),
      opt(
        "Player-driven choices: Deciding what to do or say and seeing those choices affect the journey keeps the player engaged.",
        { mystiko: 60, macro: 20 },
      ),
    ],
    { target: REWARD, keyPhrase: "what keeps the player engaged" },
  ),
  question(
    "Q12",
    "How important is 100% completion?",
    [
      opt("Very important", { macro: 85 }),
      opt("Nice extra", { macro: 30, mystiko: 45 }),
      opt("Not important", { mystiko: 75 }),
    ],
    { target: REWARD, keyPhrase: "100% completion" },
  ),
  question(
    "Q13",
    "What does fatigue mainly make harder?",
    [
      opt("Reflexes", { micro: 80 }),
      opt("Understanding the story", { mystiko: 85 }),
      opt("Managing systems", { macro: 85 }),
    ],
    { target: REWARD, keyPhrase: "fatigue" },
  ),
  question(
    "Q14",
    "What best represents the game's lasting identity?",
    [
      opt("Style and presentation", { micro: 80, mystiko: 20 }),
      opt("Ideas and moral questions", { mystiko: 100 }),
      opt("Tense physical survival/gameplay", { macro: 60, micro: 30 }),
    ],
    { target: REWARD, keyPhrase: "the game's lasting identity" },
  ),
];

export const SET_C: QuestionSetDefinition = buildSet(
  "C",
  "Narrative",
  PART1,
  PART2,
);
