"""
Question set D — Challenge aesthetic (v1.0.0) — SBGC-173.

Weights use the registry notation: μ = micro, M = macro, κ = mystiko.
"""

from __future__ import annotations

from classifications.questionnaire.registry.v1.types import (
    ProfileTarget,
    build_set,
    opt,
    question,
)

CHALLENGE = ProfileTarget.CHALLENGE
REWARD = ProfileTarget.REWARD

PART1 = (
    question(
        "Q3",
        "When the player makes a mistake, how much does it hurt?",
        [
            opt(
                "Very heavily: One mistake can immediately lose a life, round, run, or fight.",
                micro=90,
            ),
            opt(
                "Heavily but recoverably: Mistakes hurt, but good positioning, defence, or resources can save the situation.",
                micro=35,
                macro=45,
            ),
            opt(
                "Mostly absorbed by strategy: A strong build, team, deck, or setup can compensate for mistakes.",
                micro=10,
                macro=70,
            ),
            opt(
                "Physical execution barely matters: The challenge mainly comes from decisions.",
                micro=-30,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4",
        "Does the player need preparation before acting?",
        [
            opt("Yes", next="Q4A"),
            opt("No", next="Q4B"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4A",
        "How important is that preparation?",
        [
            opt(
                "Decisive: A bad build, draft, deck, economy, or setup can put the player in a losing position before execution begins.",
                macro=80,
            ),
            opt(
                "Important but recoverable: Good execution can overcome a bad setup.",
                macro=30,
                micro=40,
            ),
            opt(
                "Minor: Preparation exists but is not a major part of success.",
                macro=-20,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4B",
        "Without preparation, what mostly decides success?",
        [
            opt(
                "Execution and positioning",
                micro=70,
                mystiko=15,
                macro=-40,
            ),
            opt("Resource decisions during the game", macro=40, micro=30),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q5",
        "How much does the player have to work with incomplete information?",
        [
            opt(
                "A lot: Sound, hidden enemies, fog, clues, or prediction are essential.",
                mystiko=85,
            ),
            opt(
                "Some: Scouting, vision, information gathering, or prediction matter.",
                mystiko=60,
                macro=20,
            ),
            opt(
                "Little: Enemies are usually visible and information is immediately available.",
                mystiko=20,
                micro=40,
            ),
            opt("None: Everything important is visible.", mystiko=-30),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6",
        "How important is controlling space?",
        [
            opt(
                "Changing the environment: Destroying walls, opening paths, changing terrain, etc.",
                next="Q6A",
            ),
            opt(
                "Controlling fixed space: Zones, waves, traps, abilities, positioning, etc.",
                next="Q6B",
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6A",
        "How central is changing the environment?",
        [
            opt(
                "Essential: Changing the environment is central to winning fights.",
                mystiko=60,
                macro=40,
            ),
            opt(
                "Occasional: It helps, but most fights happen in predictable spaces.",
                macro=20,
                mystiko=15,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6B",
        "How do players control fixed space?",
        [
            opt("Abilities/units control space", macro=60),
            opt("Precise utility/timing controls space", micro=40, macro=20),
            opt("Direct positioning wins space", micro=50),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q7",
        "When there is a decisive clash, what usually determines the winner?",
        [
            opt("Execution: Aim, reactions, combos, movement, timing.", micro=90),
            opt(
                "A mix of everything: Information, preparation, decisions, and execution all matter heavily.",
                micro=35,
                macro=35,
                mystiko=35,
            ),
            opt(
                "Team/system coordination: Ability combinations, cooldowns, positioning, roles, etc.",
                macro=75,
                micro=15,
            ),
            opt(
                "Numbers and setup: Better economy, build, cards, equipment, or scaling wins.",
                macro=85,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8",
        "Does the game reward mind games or deception?",
        [
            opt("Yes", next="Q8A"),
            opt("No", next="Q8B"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8A",
        "What kind of deception is it?",
        [
            opt(
                "Fakes and conditioning: Making opponents expect one thing and doing another.",
                mystiko=70,
            ),
            opt(
                "Baiting abilities/resources: Making the opponent waste something valuable before attacking.",
                macro=60,
                mystiko=25,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8B",
        "Without deception, what decides the outcome?",
        [
            opt("Physical execution", micro=60),
            opt("Resource/system advantage", macro=40),
        ],
        target=CHALLENGE,
    ),
)

PART2 = (
    question(
        "Q9",
        "What gives the biggest high-stakes payoff?",
        [
            opt("Pulling off an amazing clutch or difficult fight", micro=90),
            opt("Outsmarting the opponent", next="Q9A"),
            opt("Executing a brilliant strategy/setup", next="Q9B"),
        ],
        target=REWARD,
    ),
    question(
        "Q9A",
        "What kind of outsmarting is it?",
        [
            opt("Reading hidden information", mystiko=85),
            opt("Setting up the situation beforehand", macro=60, mystiko=25),
        ],
        target=REWARD,
    ),
    question(
        "Q9B",
        "How was that strategy executed?",
        [
            opt("Team planning and coordination", macro=80),
            opt("Adapting quickly during chaos", macro=40, micro=30),
        ],
        target=REWARD,
    ),
    question(
        "Q10",
        "What best shows a player's mastery?",
        [
            opt("High rank", macro=85),
            opt("Amazing mechanical plays", micro=80),
            opt(
                "Deep game knowledge: Knowing obscure mechanics, maps, timings, counters, etc.",
                mystiko=60,
                macro=25,
            ),
            opt(
                "Pure intensity: The game is rewarding mainly because every moment feels high-stakes.",
                micro=30,
                mystiko=30,
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q11",
        "When watching top-level play, what is most impressive?",
        [
            opt(
                "Mechanical skill: Incredible reactions, combos, aim, movement, etc.",
                micro=85,
            ),
            opt(
                "Strategy: Drafts, compositions, resource plans, or coordinated tactics",
                next="Q11A",
            ),
            opt(
                "Mind games: Predictions, deception, traps, or clever reads",
                mystiko=80,
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q11A",
        "Do ordinary players copy professional strategies?",
        [
            opt("Yes, heavily", macro=85),
            opt("Rarely", micro=35, macro=25),
        ],
        target=REWARD,
    ),
    question(
        "Q12",
        "When the player is tired, what breaks down first?",
        [
            opt("Physical execution", micro=80),
            opt("Game sense", mystiko=75, next="Q12A"),
            opt("Strategic decisions", macro=75, next="Q12B"),
        ],
        target=REWARD,
    ),
    question(
        "Q12A",
        "Can raw skill compensate?",
        [
            opt("Yes", micro=40),
            opt("No", mystiko=40),
        ],
        target=REWARD,
    ),
    question(
        "Q12B",
        "Can the player switch to a simpler/supporting role?",
        [
            opt("Yes", macro=50),
            opt("No", micro=30, macro=20),
        ],
        target=REWARD,
    ),
    question(
        "Q13",
        "Outside the actual match/run, what keeps players coming back?",
        [
            opt("Cosmetics and trading", micro=60, macro=20),
            opt("New characters/classes/cards", macro=70, micro=20),
            opt(
                "Mastery progression: Ranks, weapon mastery, achievements, account progression, etc.",
                mystiko=35,
                macro=35,
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q14",
        "When players lose, what is usually the real reason?",
        [
            opt("Bad strategy/team decisions", macro=85),
            opt("The opponent was mechanically better", micro=85),
            opt("They didn't see/read something", mystiko=80),
            opt(
                "The system was exploited or cheated",
                micro=30,
                macro=30,
                mystiko=30,
            ),
        ],
        target=REWARD,
    ),
)

SET_D = build_set("D", "Challenge", PART1, PART2)

__all__ = ["SET_D"]
