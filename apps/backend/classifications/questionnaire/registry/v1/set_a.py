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
        "How much does precise physical input affect what happens?",
        [
            opt(
                "A lot: Missing a dodge, shot, combo, jump, or timing window can quickly cause failure or heavy damage.",
                micro=20,
            ),
            opt(
                "Somewhat: Timing and accuracy matter, but mistakes are usually recoverable.",
                micro=15,
            ),
            opt(
                "A little: The game rewards accurate input, but the timing is fairly forgiving.",
                micro=10,
            ),
            opt(
                "Barely: Actions work almost the same regardless of exactly when the player presses.",
                micro=-10,
            ),
            opt(
                "Not at all: The game mainly uses turns, menus, clicks, or choices rather than physical timing.",
                micro=-30,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4",
        "How much does the order of actions matter?",
        [
            opt("A fixed order matters", next="Q4A"),
            opt("The player chooses the order", next="Q4B"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4A",
        "What happens if the player does things in the wrong order?",
        [
            opt(
                "Fails badly: The objective fails, the run resets, or there is a major penalty.",
                macro=5,
            ),
            opt(
                "Slight setback: It still works, but wastes time or gives a worse result.",
                macro=2,
            ),
            opt(
                "No difference: The player can do things in any order with essentially the same result.",
                macro=0,
            ),
            opt(
                "The game blocks it: The next step simply cannot happen until the previous one is completed.",
                next="Q4C",
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4B",
        "How important is choosing your own order?",
        [
            opt(
                "Very important: A poor order can make success much harder or cause a timer/resource problem.",
                macro=10,
            ),
            opt(
                "Helpful: A good order makes things easier, but almost any order works.",
                macro=2,
            ),
            opt("Not important: The order barely changes anything.", macro=0),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4C",
        "Can the player's choices change what happens later?",
        [
            opt(
                "Yes, significantly: Different choices can change routes, mechanics, characters, or endings.",
                macro=10,
            ),
            opt(
                "No: Everyone follows essentially the same path and gets the same outcome.",
                macro=-30,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q5",
        "How much does the game hide useful tricks or rules?",
        [
            opt(
                "A lot: Players can discover hidden interactions, unusual combos, secret rules, or tricks that make them substantially better.",
                mystiko=10,
            ),
            opt(
                "A little: There are some secrets or tricks, but most important rules are obvious.",
            ),
            opt(
                "Almost none: The game tells the player nearly everything they need to know.",
                mystiko=-10,
            ),
            opt(
                "None: There is effectively no hidden gameplay knowledge to discover.",
                mystiko=-15,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6",
        "How much fast or continuous input does the game demand?",
        [
            opt(
                "Very high: The player is constantly moving, aiming, clicking, dodging, or pressing buttons quickly.",
                micro=80,
            ),
            opt(
                "High: There is frequent physical input, but regular breaks exist.",
                micro=65,
            ),
            opt("Low: Inputs are occasional or comfortably paced.", micro=20),
            opt(
                "Very low: Most actions are slow, menu-based, or turn-based.",
                micro=-20,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q7",
        "How important is predicting what happens next?",
        [
            opt(
                "Essential: Players must read enemy attacks, movement, hazards, or patterns before they happen.",
                mystiko=80,
            ),
            opt(
                "Mostly stats: Prediction helps, but stronger equipment, characters, or resources usually matter more.",
                mystiko=20,
                macro=60,
            ),
            opt(
                "Mostly reaction: The player mainly reacts after something happens.",
                mystiko=-10,
                micro=60,
            ),
            opt(
                "Sometimes useful: Prediction helps, but basic reactions are usually enough.",
                mystiko=10,
            ),
            opt(
                "No threats to predict: There are no meaningful enemies or moving hazards.",
                mystiko=-100,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8",
        "Does the game calculate success using stats (i.e. HP, damage, levels, gear)?",
        [
            opt("Yes", next="Q8A"),
            opt("No", next="Q8B"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8A",
        "What matters most when the game calculates success with stats?",
        [
            opt(
                "Player skill wins: Good aim, movement, timing, or execution can overcome better numbers.",
                micro=35,
                macro=5,
            ),
            opt(
                "Both matter: Stats create a major advantage, but skilled play can still overcome some of it.",
                micro=15,
                macro=70,
            ),
            opt(
                "Stats win: Level, gear, damage, or other numbers overwhelmingly decide the outcome.",
                macro=95,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8B",
        "Does the game mainly revolve around repeating a physical action?",
        [
            opt("Yes", next="Q8C"),
            opt("No", micro=-20, next="Q8D"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8C",
        "How much of the game is about mastering that action?",
        [
            opt(
                "Almost all of it: Mastering the action is basically the whole game.",
                micro=100,
            ),
            opt(
                "Most of it: The action is the main activity, with a few supporting systems.",
                micro=50,
            ),
            opt(
                "Only one part: The action exists, but other systems are equally or more important.",
                micro=5,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8D",
        "Does the game use text, dialogue, or narration heavily?",
        [
            opt("Yes", next="Q8E"),
            opt("No", next="Q8F"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8E",
        "During those sections, how much physical control does the player still have?",
        [
            opt(
                "No physical control: The player mostly reads, chooses, or waits.",
                mystiko=10,
            ),
            opt(
                "Full physical control: The player is still moving, aiming, driving, etc.",
                micro=10,
            ),
            opt(
                "Both: The player must follow the story while still reacting to what is happening.",
                micro=5,
                mystiko=5,
            ),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8F",
        "Does the game require solving puzzles or figuring things out?",
        [
            opt(
                "Yes: Progress depends on solving puzzles, clues, or deductions.",
                mystiko=40,
            ),
            opt(
                "No: Navigation and objectives are mostly straightforward.",
                mystiko=-10,
            ),
        ],
        target=CHALLENGE,
    ),
)

PART2 = (
    question(
        "Q9",
        "What kind of unlockable rewards does the game provide?",
        [
            opt("Looks and cosmetics", next="Q9A"),
            opt("Useful gameplay rewards", next="Q9B"),
            opt("Neither", micro=-20, macro=-20),
        ],
        target=REWARD,
    ),
    question(
        "Q9A",
        "How are the cosmetics mainly earned?",
        [
            opt(
                "Playing the game: Completing activities, challenges, chapters, or grinding earns them.",
                micro=100,
                next="Q9C",
            ),
            opt(
                "Paid or random: They mainly come from purchases, battle passes, loot boxes, or gacha.",
                micro=25,
                macro=30,
                next="Q9C",
            ),
            opt(
                "Both: Players can earn cosmetics and also buy them.",
                micro=40,
                macro=30,
                next="Q9C",
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q9B",
        "What kind of progression reward matters most?",
        [
            opt(
                "Bigger numbers: Better damage, stats, levels, equipment, etc.",
                macro=80,
                next="Q9E",
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
        "Q9C",
        "Can players trade those cosmetics?",
        [
            opt(
                "Yes: Players can buy, sell, or trade them.",
                macro=40,
                next="Q9D",
            ),
            opt(
                "No: They stay with the player's account/save.",
                micro=30,
                macro=20,
                next="Q9D",
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q9D",
        "Are there also gameplay-changing unlocks?",
        [
            opt("Yes", next="Q9E"),
            opt("No", micro=-20, macro=-20),
        ],
        target=REWARD,
    ),
    question(
        "Q9E",
        "How much do those unlocks change gameplay?",
        [
            opt(
                "A lot: They add major abilities or significantly increase power.",
                micro=20,
                next="Q9F",
            ),
            opt(
                "Somewhat: They offer different but reasonably balanced ways to play.",
                micro=10,
                macro=20,
                next="Q9F",
            ),
            opt(
                "Not at all: They mainly exist for appearance, story, or collection.",
                macro=-10,
                mystiko=15,
                next="Q9F",
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q9F",
        "Does the game have a rank or leaderboard?",
        [
            opt("Yes, it's a major part of the game", macro=90),
            opt("Yes, but it's secondary", macro=20, mystiko=50),
            opt("Yes, but hardly anyone cares about it", macro=5, mystiko=50),
            opt("No", macro=-15),
        ],
        target=REWARD,
    ),
    question(
        "Q10",
        "What gives the game most of its moment-to-moment satisfaction?",
        [
            opt(
                "Physical feel: Movement, aiming, hitting, driving, shooting, jumping, cleaning, etc. feel satisfying.",
                micro=90,
            ),
            opt(
                "Beautiful sensory experience: Music, visuals, atmosphere, sound, or effects are the main reward.",
                micro=50,
                mystiko=20,
            ),
            opt(
                "Discovering things: Exploration, secrets, strange events, or new places provide the biggest payoff.",
                mystiko=100,
            ),
            opt(
                "Making a clever setup work: Builds, combinations, planning, or systems suddenly pay off.",
                macro=80,
            ),
            opt(
                "Playing together: Coordination with other players creates the main payoff.",
                macro=30,
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q11",
        "If the player's progress disappeared, what would be the biggest loss?",
        [
            opt("Cosmetics and collection", micro=80),
            opt("Personal world/space", mystiko=60, next="Q11A"),
            opt("Rank and competitive status", macro=100),
            opt("Money spent", micro=30, macro=30),
            opt("Records and best times", micro=40, macro=60),
            opt(
                "Shared memories and things built with others",
                micro=40,
                mystiko=30,
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q11A",
        "How relaxing is the game designed to be?",
        [
            opt(
                "Almost completely relaxing: Very few meaningful failure states or pressure.",
                mystiko=200,
            ),
            opt(
                "Mostly relaxing: Calm overall, but some pressure, timers, or resource problems exist.",
                mystiko=50,
            ),
            opt(
                "Not actually relaxing: It may look cozy, but failure and pressure still matter.",
                micro=20,
                macro=10,
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q12",
        "How much does fatigue affect physical play?",
        [
            opt("A lot", next="Q12A"),
            opt("Very little because the game is relaxing", micro=-10),
            opt("Neither", micro=0),
        ],
        target=REWARD,
    ),
    question(
        "Q12A",
        "What becomes harder when tired?",
        [
            opt("Paying attention", micro=10),
            opt("Handling lots of sensory information", micro=20),
            opt("Reacting quickly", micro=10, macro=50),
            opt("Staying aware of what is happening", micro=15),
            opt("Rapid repeated input", micro=17),
        ],
        target=REWARD,
    ),
    question(
        "Q13",
        "Do you enjoy watching clips or streams of the game being played by other people (i.e. YouTube, Twitch)?",
        [
            opt("Yes", next="Q13A"),
            opt("No", next="Q13B"),
        ],
        target=REWARD,
    ),
    question(
        "Q13A",
        "What makes the game interesting to watch?",
        [
            opt(
                "Amazing skill: Watching highly skilled players do things most players cannot.",
                micro=20,
                macro=50,
            ),
            opt(
                "Smart play: Watching clever builds, routes, strategies, or decisions.",
                micro=50,
                macro=10,
            ),
            opt(
                "Unexpected chaos: Funny, strange, or unpredictable things happen.",
                mystiko=10,
            ),
            opt(
                "New discoveries: Watching players find new tricks, builds, or interactions.",
                micro=23,
            ),
            opt(
                "Competition: Watching coordinated high-level matches.",
                micro=15,
                macro=50,
            ),
            opt(
                "Relaxation: Watching the game is calming even when playing it is demanding.",
                mystiko=29,
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q13B",
        "If it is not especially interesting to watch, why not?",
        [
            opt(
                "Hands-on feel: The fun mostly comes from personally controlling it.",
                micro=67,
            ),
            opt(
                "Slow personal pace: Reading, planning, or doing things at your own pace is hard to make exciting as a spectator.",
                mystiko=5,
            ),
        ],
        target=REWARD,
    ),
    question(
        "Q14",
        "What is the game's biggest weakness?",
        [
            opt("Cheating/exploits", micro=30, macro=60),
            opt("Technical problems", micro=65, mystiko=20, next="Q14A"),
            opt("Bad monetization", macro=80),
            opt("Bad balance", micro=35, macro=35),
            opt("Repetitive gameplay", micro=10, next="Q14A"),
            opt("Too much grinding", micro=-22, next="Q14A"),
            opt("Too much random loot", macro=-2, next="Q14A"),
            opt("Too few players", mystiko=19, next="Q14A"),
        ],
        target=REWARD,
    ),
    question(
        "Q14A",
        "What is the game's most underrated strength?",
        [
            opt("Achievements/challenges", macro=44),
            opt("Game feel", micro=31),
            opt("Unique ideas", mystiko=77),
            opt("Cross-platform progression", macro=15),
            opt("Art/animation/visuals", micro=15, macro=5),
            opt("None"),
        ],
        target=REWARD,
    ),
)

SET_A = build_set("A", "Sensory", PART1, PART2)

__all__ = ["SET_A"]
