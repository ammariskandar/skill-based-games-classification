"""
Question set B — Fantasy aesthetic (v1.0.0) — SBGC-173.

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
        "How much does real-time control matter during difficult situations?",
        [
            opt(
                "Very high: Dodging, aiming, timing attacks, platforming, or movement accurately is essential.",
                micro=85,
            ),
            opt(
                "Moderate: Real-time action matters, but mistakes can often be recovered from.",
                micro=35,
                macro=45,
            ),
            opt(
                "Very low: The game mostly uses turns, menus, cards, or automatic actions.",
                micro=-40,
                macro=50,
            ),
            opt(
                "Low but stats matter: Simple actions are enough, while levels, gear, or abilities do most of the work.",
                micro=15,
                macro=65,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4",
        "When the game becomes difficult, what usually gets the player past it?",
        [
            opt(
                "Better preparation: Change the character, equipment, deck, resources, or setup.",
                next="Q4A",
            ),
            opt(
                "Better execution: Learn attacks, patterns, timing, or movement.",
                next="Q4B",
            ),
            opt(
                "A different approach: Use the environment, stealth, dialogue, building, or another system.",
                next="Q4C",
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4A",
        "How much can preparation solve it?",
        [
            opt("Preparation can almost solve it", macro=85),
            opt("Preparation helps, but skill is still needed", macro=50, micro=35),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4B",
        "What execution skill is most important?",
        [
            opt("Reaction and timing", micro=80, mystiko=20),
            opt("Learning patterns", micro=50, mystiko=50),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4C",
        "What kind of alternative approach is it?",
        [
            opt(
                "Using the world/system: Physics, elements, traps, terrain, etc.",
                mystiko=60,
                macro=40,
            ),
            opt(
                "Using social or non-combat choices: Dialogue, disguise, stealth, quests, etc.",
                mystiko=80,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q5",
        "How much must players figure out enemy weaknesses?",
        [
            opt(
                "A lot: Attacks, patterns, weaknesses, or tricks must be learned.",
                mystiko=75,
                micro=25,
            ),
            opt(
                "Somewhat: Knowing weaknesses helps, but stats and equipment also matter.",
                mystiko=65,
                macro=35,
            ),
            opt(
                "A little: Enemies are mostly obvious and predictable.",
                mystiko=-30,
                macro=40,
            ),
            opt(
                "Turn-based planning: Reading enemy options and deciding how to spend actions is central.",
                mystiko=45,
                macro=55,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6",
        "How much does planning your character or team matter?",
        [
            opt("It's the core of the game", next="Q6A"),
            opt("It's secondary", next="Q6B"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6A",
        "What kind of planning matters most?",
        [
            opt(
                "Team planning: Managing several characters and their abilities is the main challenge.",
                macro=85,
                mystiko=15,
            ),
            opt(
                "Character building: Skills, equipment, crafting, or upgrades are the main challenge.",
                macro=85,
            ),
            opt(
                "Switching tools/characters during play: Combining different abilities in real time matters.",
                macro=60,
                micro=30,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6B",
        "What matters most instead?",
        [
            opt("Weapon feel and moves matter most", micro=80),
            opt("Looks/roleplay matter more than numbers", mystiko=50, micro=20),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q7",
        "How much does where you are affect what happens?",
        [
            opt(
                "A lot: Terrain, height, cover, environmental effects, or chokepoints change the outcome.",
                macro=70,
                mystiko=35,
            ),
            opt(
                "A lot during action: Tight spaces, hazards, ledges, or movement make positioning difficult.",
                micro=70,
                mystiko=20,
            ),
            opt(
                "Very little: The ground and surroundings rarely change the outcome.",
                macro=-20,
                micro=20,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8",
        "How much does the game make players find their own way?",
        [
            opt(
                "Story/choice deduction: Players need to understand characters, choices, or consequences.",
                mystiko=80,
                macro=20,
            ),
            opt(
                "Exploration: Players need to notice clues, hidden paths, or discover where to go.",
                mystiko=90,
            ),
            opt(
                "Clear directions: Objectives are clearly marked and little figuring-out is needed.",
                mystiko=-30,
                macro=30,
            ),
        ],
        target=CHALLENGE,
    ),
)

PART2 = (
    question(
        "Q9",
        "What kind of progression reward matters most?",
        [
            opt("Cosmetics/characters", next="Q9A"),
            opt("Power and better equipment", next="Q9B"),
        ],
        target=REWARD,
    ),
    question(
        "Q9A",
        "How are they obtained?",
        [
            opt("Buy or randomly obtain them", micro=70, macro=30),
            opt("Earn them through difficult content", micro=60, mystiko=30),
            opt("Create/customize them yourself", macro=45, mystiko=35),
        ],
        target=REWARD,
    ),
    question(
        "Q9B",
        "What kind of power progression is it?",
        [
            opt(
                "Bigger numbers: Better damage, stats, levels, equipment, etc.",
                macro=80,
            ),
            opt(
                "New abilities: Unlocking movement, exploration, or new ways to interact with the world.",
                mystiko=70,
                macro=20,
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q10",
        "What gives the game its biggest sense of wonder?",
        [
            opt("Big beautiful places", mystiko=120),
            opt("Finding things nobody told you about", mystiko=110, macro=20),
            opt("Becoming extremely powerful", macro=60, micro=50),
            opt("Getting attached to characters", mystiko=90),
        ],
        target=REWARD,
    ),
    question(
        "Q11",
        "If your save disappeared, what would hurt to lose most?",
        [
            opt("Build and resources", macro=85),
            opt("Choices and world changes", mystiko=90),
            opt("Characters/cosmetics", next="Q11A"),
        ],
        target=REWARD,
    ),
    question(
        "Q11A",
        "How was that collection assembled?",
        [
            opt("Paid/saved-for collection", micro=75, macro=30),
            opt("Earned through hard gameplay", micro=80),
        ],
        target=REWARD,
    ),
    question(
        "Q12",
        "How does the game provide status or prestige?",
        [
            opt("High-level gear/achievements/leaderboards", macro=90),
            opt("Beating other players", micro=80, macro=15),
            opt("Having a rare/high-investment collection", macro=80, micro=25),
            opt("No external status: Progress is mainly personal.", mystiko=80),
        ],
        target=REWARD,
    ),
    question(
        "Q13",
        "What becomes hardest when the player is tired?",
        [
            opt("Reflexes and movement", micro=80),
            opt("Reading and understanding", next="Q13A"),
            opt("Nothing much: The game remains comfortable to play.", mystiko=90),
        ],
        target=REWARD,
    ),
    question(
        "Q13A",
        "What is hardest to read or manage when tired?",
        [
            opt("Story/puzzles", mystiko=75),
            opt("Managing systems/builds/resources", macro=85),
        ],
        target=REWARD,
    ),
    question(
        "Q14",
        "What produces the biggest payoff?",
        [
            opt("Finally beating something through skill", micro=90),
            opt("Making a clever build/setup work", macro=85),
            opt("Finding a major secret", mystiko=100),
            opt("Getting an extremely rare reward", micro=65, macro=25),
        ],
        target=REWARD,
    ),
)

SET_B = build_set("B", "Fantasy", PART1, PART2)

__all__ = ["SET_B"]
