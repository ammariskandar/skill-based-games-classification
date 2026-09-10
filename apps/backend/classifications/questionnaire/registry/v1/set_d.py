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
        "What happens when your mechanical execution is imperfect?",
        [
            opt("Instant elimination", micro=90),
            opt("Abilities absorb", micro=35, macro=45),
            opt("Execution secondary", micro=10, macro=70),
            opt("Does not test aim", micro=-30),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4",
        "Does pre-round preparation matter?",
        [
            opt("Yes", next="Q4A"),
            opt("No", next="Q4B"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4A",
        "How decisive is that preparation?",
        [
            opt("Decisive", macro=80),
            opt("Crack mechanics win", macro=30, micro=40),
            opt("Decorative", macro=-20),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q4B",
        "How do the maps shape the challenge?",
        [
            opt("Static maps", micro=70, mystiko=15, macro=-40),
            opt("Economy-driven", macro=40, micro=30),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q5",
        "How do you learn enemy positions?",
        [
            opt("3D sound propagation", mystiko=85),
            opt("Recon utility", mystiko=60, macro=20),
            opt("Line-of-sight", mystiko=20, micro=40),
            opt("Open arena/HUD", mystiko=-30),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6",
        "Can you alter the map geometry?",
        [
            opt("Yes", next="Q6A"),
            opt("No", next="Q6B"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6A",
        "How central is procedural destruction?",
        [
            opt("Core to every fight", mystiko=60, macro=40),
            opt("Occasional utility", macro=20, mystiko=15),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q6B",
        "How do you control space on a static map?",
        [
            opt("Shields/barriers", macro=60),
            opt("Line-of-sight grenades", micro=40, macro=20),
            opt("Positional aggression", micro=50),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q7",
        "What decides a high-stakes engagement?",
        [
            opt("Mechanical execution", micro=90),
            opt("Three-way synergy", micro=35, macro=35, mystiko=35),
            opt("Ultimate trading", macro=75, micro=15),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8",
        "Do you enjoy tactical mind games?",
        [
            opt("Yes", next="Q8A"),
            opt("No", next="Q8B"),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8A",
        "What form does your deception take?",
        [
            opt("Sound fakes/lurks", mystiko=70),
            opt("Baiting cooldowns", macro=60, mystiko=25),
        ],
        target=CHALLENGE,
    ),
    question(
        "Q8B",
        "What wins when there is no deception?",
        [
            opt("Raw fragging", micro=60),
            opt("Systemic advantage", macro=40),
        ],
        target=CHALLENGE,
    ),
)

PART2 = (
    question(
        "Q9",
        "What is your highest dopamine rush?",
        [
            opt("1vX clutch", micro=90),
            opt("Hidden intel outplay", next="Q9A"),
            opt("Textbook counter-play", next="Q9B"),
        ],
        target=REWARD,
    ),
    question(
        "Q9A",
        "What intelligence grounds the play?",
        [
            opt("Sound/blind wallbang", mystiko=85),
            opt("Utility traps", macro=60, mystiko=25),
        ],
        target=REWARD,
    ),
    question(
        "Q9B",
        "How does team synergy pay off?",
        [
            opt("Shot-calling", macro=80),
            opt("Instinctive layering", macro=40, micro=30),
        ],
        target=REWARD,
    ),
    question(
        "Q10",
        "What does competitive rank mean to you?",
        [
            opt("Tier is everything", macro=85),
            opt("KD/ADR highlights", micro=80),
            opt("Game sense depth", mystiko=60, macro=25),
            opt("Adrenaline rush", micro=30, mystiko=30),
        ],
        target=REWARD,
    ),
    question(
        "Q11",
        "Why do you watch Pro play?",
        [
            opt("Inhuman aim", micro=85),
            opt("Team strategies", next="Q11A"),
            opt("200 IQ reads", mystiko=80),
        ],
        target=REWARD,
    ),
    question(
        "Q11A",
        "Do you try to replicate pro tactics?",
        [
            opt("Yes in custom games", macro=85),
            opt("Rarely/solo aim", micro=35, macro=25),
        ],
        target=REWARD,
    ),
    question(
        "Q12",
        "What breaks down first when you are fatigued?",
        [
            opt("Aim evaporates", micro=80),
            opt("Game sense numb", mystiko=75, next="Q12A"),
            opt("Macro collapses", macro=75, next="Q12B"),
        ],
        target=REWARD,
    ),
    question(
        "Q12A",
        "Can raw mechanics bail you out?",
        [
            opt("Yes raw aim", micro=40),
            opt("No automatic death", mystiko=40),
        ],
        target=REWARD,
    ),
    question(
        "Q12B",
        "Do you switch roles instead?",
        [
            opt("Yes support", macro=50),
            opt("No must frag", micro=30, macro=20),
        ],
        target=REWARD,
    ),
    question(
        "Q13",
        "What keeps you coming back?",
        [
            opt("Weapon skins/trading", micro=60, macro=20),
            opt("Roster expansion", macro=70, micro=20),
            opt("Stat grinding/charms", mystiko=35, macro=35),
        ],
        target=REWARD,
    ),
    question(
        "Q14",
        "What makes you want to throw your controller?",
        [
            opt("Teammates throwing", macro=85),
            opt("Mechanically diffed", micro=85),
            opt("Dying to unseen", mystiko=80),
            opt("Cheating/smurfing", micro=30, macro=30, mystiko=30),
        ],
        target=REWARD,
    ),
)

SET_D = build_set("D", "Challenge", PART1, PART2)

__all__ = ["SET_D"]
