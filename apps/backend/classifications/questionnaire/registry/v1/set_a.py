"""
Question set A — Sensory aesthetic (v1.0.0) — SBGC-173.

Part 1 (Challenge, Q3–Q8) and Part 2 (Reward, Q9–Q14) roots plus their child
branch nodes.  Weights use the registry notation: μ = micro, M = macro,
κ = mystiko.
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
        "How much does precise button timing affect your enjoyment?",
        [
            opt("Huge", micro=20),
            opt("Modest", micro=15),
            opt("Little", micro=10),
            opt("No effect", micro=-10),
            opt("None", micro=-30),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4",
        "Does the order in which you perform tasks matter?",
        [
            opt("Yes", next="Q4A"),
            opt("No", next="Q4B"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4A",
        "Does getting the task sequence wrong have a negative effect?",
        [
            opt("Yes", macro=5),
            opt("No"),
            opt("Maybe", macro=2),
            opt("Linear", next="Q4C"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4B",
        "Do you assign your own task order?",
        [
            opt("Yes", macro=10),
            opt("Sometimes", macro=2),
            opt("No"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4C",
        "Do major story consequences follow from that order?",
        [
            opt("Yes", macro=10),
            opt("No", macro=-30),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q5",
        "Do you like knowing the game's secrets in advance?",
        [
            opt("Yes", mystiko=10),
            opt("No", mystiko=-10),
            opt("None", mystiko=-15),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6",
        "After a four-hour session, do you feel physically sore?",
        [
            opt("Yes", micro=80),
            opt("Sometimes", micro=65),
            opt("Rarely", micro=20),
            opt("Less", micro=-20),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q7",
        "How central is out-guessing your opponents?",
        [
            opt("Core", mystiko=80),
            opt("Stats", mystiko=20, macro=60),
            opt("Skill", mystiko=20, micro=60),
            opt("Rarely", mystiko=10),
            opt("Not at all", mystiko=-10),
            opt("No opponents", mystiko=-100),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8",
        "Does the game track player stats or HP?",
        [
            opt("Yes", next="Q8A"),
            opt("No", next="Q8B"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8A",
        "What decides the outcome: stats or skill?",
        [
            opt("Skill", micro=35, macro=5),
            opt("Equal", micro=15, macro=70),
            opt("Stats most", macro=95),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8B",
        "Do you repeat the same actions often?",
        [
            opt("Yes", next="Q8C"),
            opt("No", micro=-20, next="Q8D"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8C",
        "Is that repeated action the sole test of skill?",
        [
            opt("Yes", micro=100),
            opt("Important", micro=50),
            opt("Other things", micro=5),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8D",
        "Do you read the dialogue?",
        [
            opt("Yes", next="Q8E"),
            opt("No", next="Q8F"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8E",
        "Turn-based or real-time?",
        [
            opt("Turn", mystiko=10),
            opt("Active", micro=10),
            opt("Mid", micro=5, mystiko=5),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8F",
        "Do you enjoy puzzles and mysteries?",
        [
            opt("Yes", mystiko=40),
            opt("No", mystiko=-10),
        ],
        target=CHALLENGE,
    ),
)

PART2 = (
    question(
        "Q9",
        "Do you chase unlockable art or cosmetics?",
        [
            opt("Yes", next="Q9A"),
            opt("No", next="Q9B"),
        ],
        target=REWARD,
    ),
    question(
        "Q9A",
        "How do you prefer to unlock them?",
        [
            opt("Progression", micro=100, next="Q9C"),
            opt("Money", micro=25, macro=30, next="Q9C"),
            opt("Both", micro=40, macro=30, next="Q9C"),
        ],
        target=REWARD,
    ),
    question(
        "Q9B",
        "Do you chase unlockable items or characters?",
        [
            opt("Yes", next="Q9E"),
            opt("No", micro=-20, macro=-20),
        ],
        target=REWARD,
    ),
    question(
        "Q9C",
        "Do they need to be resellable or tradeable?",
        [
            opt("Yes", macro=40, next="Q9D"),
            opt("No", micro=30, macro=20, next="Q9D"),
        ],
        target=REWARD,
    ),
    question(
        "Q9D",
        "Do you want additional items or characters?",
        [
            opt("Yes", next="Q9E"),
            opt("No", micro=-20, macro=-20),
        ],
        target=REWARD,
    ),
    question(
        "Q9E",
        "Should unlocks affect gameplay?",
        [
            opt("Changes gameplay", micro=20, next="Q9F"),
            opt("Balanced", micro=10, macro=20, next="Q9F"),
            opt("Zero effect", macro=-10, mystiko=15, next="Q9F"),
        ],
        target=REWARD,
    ),
    question(
        "Q9F",
        "What does ranked, Elo, or a leaderboard mean to you?",
        [
            opt("Only care", macro=90),
            opt("Dont care", macro=20, mystiko=50),
            opt("Not sure", macro=5, mystiko=50),
            opt("No", macro=-15),
        ],
        target=REWARD,
    ),
    question(
        "Q10",
        "What is most oddly satisfying?",
        [
            opt("Impossible to describe", mystiko=100),
            opt("Keep playing despite parts", mystiko=150),
            opt("Great gameplay", micro=90),
            opt("Great story", mystiko=50),
            opt("With friends", macro=30),
        ],
        target=REWARD,
    ),
    question(
        "Q11",
        "What would you miss most?",
        [
            opt("Cosmetics/items", micro=80),
            opt("Healing place", mystiko=60, next="Q11A"),
            opt("Elo/rank", macro=100),
            opt("Money spent", micro=30, macro=30),
            opt("Speedrun", micro=40, macro=60),
            opt("Memories", micro=40, mystiko=30),
        ],
        target=REWARD,
    ),
    question(
        "Q11A",
        "Does it keep your cortisol low?",
        [
            opt("Yes", mystiko=200),
            opt("Somewhat", mystiko=50),
            opt("Hell nah", micro=20, macro=10),
        ],
        target=REWARD,
    ),
    question(
        "Q12",
        "Does fatigue change how you play?",
        [
            opt("Yes", micro=30, next="Q12A"),
            opt("Energizes", micro=-10),
            opt("Not really", micro=0),
        ],
        target=REWARD,
    ),
    question(
        "Q12A",
        "Why does fatigue affect you?",
        [
            opt("Cant focus", micro=10),
            opt("Painful", micro=20),
            opt("Losing streak", micro=10, macro=50),
            opt("Dont know", micro=15),
            opt("More tired", micro=17),
        ],
        target=REWARD,
    ),
    question(
        "Q13",
        "Do you watch streams or clips of the game?",
        [
            opt("Yes", next="Q13A"),
            opt("No", next="Q13B"),
        ],
        target=REWARD,
    ),
    question(
        "Q13A",
        "Why do you watch?",
        [
            opt("Inspiring", micro=20, macro=50),
            opt("Improve", micro=50, macro=10),
            opt("Funny", mystiko=10),
            opt("New builds", micro=23),
            opt("Pros", micro=15, macro=50),
            opt("Too tired to play", mystiko=29),
        ],
        target=REWARD,
    ),
    question(
        "Q13B",
        "Is the game less fun to watch than to play?",
        [
            opt("Yes", micro=67),
            opt("No time but entertaining", mystiko=5),
        ],
        target=REWARD,
    ),
    question(
        "Q14",
        "What is the worst thing about a game?",
        [
            opt("Cheaters", micro=30, macro=60),
            opt("Bugs", micro=65, mystiko=20, next="Q14A"),
            opt("P2W Whales", macro=80),
            opt("Balancing", micro=35, macro=35),
            opt("Repetitious", micro=10, next="Q14A"),
            opt("Grinding", micro=-22, next="Q14A"),
            opt("Lootboxes", macro=-2, next="Q14A"),
            opt("Lack of players", mystiko=19, next="Q14A"),
        ],
        target=REWARD,
    ),
    question(
        "Q14A",
        "What is the most underrated aspect?",
        [
            opt("Achievements", macro=44),
            opt("Mechanics", micro=31),
            opt("Own genre", mystiko=77),
            opt("Cross-progression", macro=15),
            opt("Character designs", micro=15, macro=5),
            opt("Something else"),
        ],
        target=REWARD,
    ),
)

SET_A = build_set("A", "Sensory", PART1, PART2)

__all__ = ["SET_A"]
