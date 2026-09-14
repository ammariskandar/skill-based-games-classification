#!/usr/bin/env python3
"""Initial catalogue classification fixture validator — SBGC-128.

Validates ``apps/backend/classifications/fixtures/initial_classifications_200.json``
and, because the fixture is *derived* rather than hand-tuned, re-derives every
profile from the answers it records:

* the fixture parses as a JSON array with exactly 200 entries
* slugs are unique and match ``games/fixtures/initial_catalogue_200.json`` on the nose
* aesthetics match the manifest and the canonical enums
* every profile is three integers in ``[0, 100]`` summing to exactly 100
* every ``registry_version`` matches the checked-in questionnaire registry
* each recorded answer path is a legal traversal of that game's assembled
  questionnaire (no missing, out-of-range, or unreachable answers)
* recomputing the path through ``compute_raw_profile`` / ``normalize_profile``
  reproduces the stored Challenge and Reward profiles exactly

It then prints the derived Challenge-dominant distribution and the per-game
divergence report against the manifest's ``intended_dominant`` curation label.
Divergences are informational: the SBGC-128 course-correction makes the
questionnaire instrument authoritative over the curation label, so they are
reported rather than treated as failures.

Usage (from the repository root):

    apps/backend/.venv/bin/python scripts/verify-initial-classifications.py

Exit code 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = (
    REPO_ROOT / "apps" / "backend" / "games" / "fixtures" / "initial_catalogue_200.json"
)
FIXTURE_PATH = (
    REPO_ROOT
    / "apps"
    / "backend"
    / "classifications"
    / "fixtures"
    / "initial_classifications_200.json"
)

sys.path.insert(0, str(REPO_ROOT / "apps" / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
os.environ.setdefault("DJANGO_SKIP_DOTENV", "1")

import django  # noqa: E402

django.setup()

from classifications.models import AESTHETIC_CHOICES  # noqa: E402
from classifications.questionnaire.aesthetic_resolver import (  # noqa: E402
    resolve_aesthetic,
)
from classifications.questionnaire.domain import AestheticCategory  # noqa: E402
from classifications.questionnaire.registry.v1.assembler import (  # noqa: E402
    assemble_questionnaire,
)
from classifications.questionnaire.registry.v1.types import (  # noqa: E402
    REGISTRY_VERSION,
    ProfileTarget,
    QuestionNode,
)
from classifications.questionnaire.scoring.engine import (  # noqa: E402
    compute_raw_profile,
    normalize_profile,
)

EXPECTED_TOTAL = 200
DIMENSIONS = ("micro", "mystiko", "macro")
PROFILE_KEYS = (
    ("challenge_profile", "challenge_answers", ProfileTarget.CHALLENGE),
    ("reward_profile", "reward_answers", ProfileTarget.REWARD),
)

FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)
    print(f"[FAIL] {message}")


def ok(message: str) -> None:
    print(f"[PASS] {message}")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_json(path: Path, label: str):
    if not path.exists():
        fail(f"{label} not found at {path.relative_to(REPO_ROOT)}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{label} is not valid JSON: {exc}")
        return None
    if not isinstance(data, list):
        fail(f"{label} root must be a JSON array")
        return None
    ok(f"{label} parses as a JSON array ({len(data)} entries)")
    return data


# ---------------------------------------------------------------------------
# Answer path resolution
# ---------------------------------------------------------------------------


def assembled_for(entry: dict):
    """Assemble the questionnaire the game's aesthetic pair dispatches to."""
    resolution = resolve_aesthetic(
        AestheticCategory(entry["primary_aesthetic"]),
        AestheticCategory(entry["secondary_aesthetic"]),
    )
    return assemble_questionnaire(resolution)


def walk(nodes: tuple[QuestionNode, ...], indexes: dict, label: str) -> dict[str, str]:
    """Resolve ``{node_id: option_index}`` into ``{node_id: option_id}``.

    Follows every root and the branch chain its selected options route to, so a
    missing answer, an out-of-range index, or an answer for a node the path never
    reaches is reported instead of silently ignored.
    """
    by_id = {node.id: node for node in nodes}
    resolved: dict[str, str] = {}
    for root in [node for node in nodes if not node.is_branch]:
        node: QuestionNode | None = root
        while node is not None:
            if node.id not in indexes:
                raise ValueError(f"no answer for {node.id}")
            index = indexes[node.id]
            if isinstance(index, bool) or not isinstance(index, int):
                raise ValueError(f"{node.id} index {index!r} is not an integer")
            if not 0 <= index < len(node.options):
                raise ValueError(
                    f"{node.id} index {index} out of range (0..{len(node.options) - 1})"
                )
            option = node.options[index]
            resolved[node.id] = option.id
            node = by_id[option.next_question_id] if option.next_question_id else None

    unused = sorted(set(indexes) - set(resolved))
    if unused:
        raise ValueError(f"answers on unreachable nodes: {unused}")
    return resolved


def recompute(entry: dict, answers_key: str, target: ProfileTarget) -> dict:
    assembled = assembled_for(entry)
    nodes = (
        assembled.part1_challenge_nodes
        if target is ProfileTarget.CHALLENGE
        else assembled.part2_reward_nodes
    )
    answers = walk(nodes, entry[answers_key], f"{entry['slug']}.{answers_key}")
    normalized = normalize_profile(compute_raw_profile(answers, nodes, target))
    return {
        "micro": normalized.micro,
        "mystiko": normalized.mystiko,
        "macro": normalized.macro,
    }


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_fixture_shape(
    fixture: list[dict], manifest: list[dict], aesthetics: set[str]
) -> None:
    problems: list[str] = []
    manifest_by_slug = {entry["slug"]: entry for entry in manifest}

    for index, entry in enumerate(fixture):
        label = entry.get("slug") or f"entry[{index}]"
        missing = {
            "slug",
            "primary_aesthetic",
            "secondary_aesthetic",
            "intended_dominant",
            "registry_version",
            "challenge_profile",
            "reward_profile",
            "challenge_answers",
            "reward_answers",
            "rationale",
        } - set(entry)
        if missing:
            problems.append(f"{label}: missing keys {sorted(missing)}")
            continue

        source = manifest_by_slug.get(entry["slug"])
        if source is None:
            problems.append(f"{label}: slug is not in the catalogue manifest")
        else:
            for key in ("primary_aesthetic", "secondary_aesthetic"):
                if entry[key] != source[key]:
                    problems.append(
                        f"{label}: {key} {entry[key]!r} != manifest {source[key]!r}"
                    )

        for key in ("primary_aesthetic", "secondary_aesthetic"):
            if entry[key] not in aesthetics:
                problems.append(f"{label}: unknown {key} {entry[key]!r}")
        if entry["intended_dominant"] not in DIMENSIONS:
            problems.append(
                f"{label}: unknown intended_dominant {entry['intended_dominant']!r}"
            )
        if entry["registry_version"] != REGISTRY_VERSION:
            problems.append(
                f"{label}: registry_version {entry['registry_version']!r} != "
                f"{REGISTRY_VERSION!r}"
            )
        if not entry["rationale"].strip():
            problems.append(f"{label}: empty rationale")

        for profile_key, _answers_key, _target in PROFILE_KEYS:
            profile = entry[profile_key]
            if not isinstance(profile, dict) or set(profile) != set(DIMENSIONS):
                problems.append(f"{label}: {profile_key} must be {list(DIMENSIONS)}")
                continue
            for dimension in DIMENSIONS:
                value = profile[dimension]
                if isinstance(value, bool) or not isinstance(value, int):
                    problems.append(f"{label}: {profile_key}.{dimension} is not an int")
                elif not 0 <= value <= 100:
                    problems.append(
                        f"{label}: {profile_key}.{dimension} out of range ({value})"
                    )
            if sum(profile.values()) != 100:
                problems.append(
                    f"{label}: {profile_key} sums to {sum(profile.values())}, not 100"
                )

    if problems:
        for problem in problems:
            fail(problem)
    else:
        ok("every entry matches the schema contract, manifest, and canonical enums")


def check_counts(fixture: list[dict], manifest: list[dict]) -> None:
    if len(fixture) != EXPECTED_TOTAL:
        fail(f"expected {EXPECTED_TOTAL} entries, found {len(fixture)}")
    else:
        ok(f"entry count is exactly {EXPECTED_TOTAL}")

    slugs = [entry["slug"] for entry in fixture]
    duplicates = [slug for slug, count in Counter(slugs).items() if count > 1]
    if duplicates:
        fail(f"duplicate slugs: {duplicates}")
    else:
        ok("all slugs are unique")

    orphaned = sorted(set(slugs) - {entry["slug"] for entry in manifest})
    uncovered = sorted({entry["slug"] for entry in manifest} - set(slugs))
    if orphaned:
        fail(f"fixture slugs absent from the manifest: {orphaned}")
    if uncovered:
        fail(f"manifest slugs missing from the fixture: {uncovered}")
    if not orphaned and not uncovered:
        ok("fixture slug set matches the catalogue manifest exactly")


def check_derivation(fixture: list[dict]) -> None:
    problems: list[str] = []
    for entry in fixture:
        for profile_key, answers_key, target in PROFILE_KEYS:
            try:
                derived = recompute(entry, answers_key, target)
            except (ValueError, KeyError) as exc:
                problems.append(f"{entry['slug']}: {answers_key}: {exc}")
                continue
            if derived != entry[profile_key]:
                problems.append(
                    f"{entry['slug']}: {profile_key} {entry[profile_key]} != "
                    f"recomputed {derived}"
                )

    if problems:
        for problem in problems:
            fail(problem)
    else:
        ok(
            f"all {len(fixture)} entries recompute their Challenge and Reward "
            "profiles from the recorded answers"
        )


def report_distribution(fixture: list[dict]) -> None:
    derived = Counter(
        max(DIMENSIONS, key=lambda dimension: entry["challenge_profile"][dimension])
        for entry in fixture
    )
    intended = Counter(entry["intended_dominant"] for entry in fixture)
    summary = ", ".join(f"{key}={derived[key]}" for key in DIMENSIONS)
    ok(f"derived Challenge-dominant distribution: {summary}")
    print(
        "       intended_dominant distribution: "
        + ", ".join(f"{key}={intended[key]}" for key in DIMENSIONS)
    )


def report_divergences(fixture: list[dict]) -> None:
    divergences = []
    for entry in fixture:
        challenge = entry["challenge_profile"]
        lead = max(DIMENSIONS, key=lambda dimension: challenge[dimension])
        if lead == entry["intended_dominant"]:
            continue
        reward = entry["reward_profile"]
        divergences.append(
            f"{entry['slug']}: intended {entry['intended_dominant']}, "
            f"derived challenge {lead} "
            f"({challenge['micro']}/{challenge['mystiko']}/{challenge['macro']}), "
            f"reward "
            f"({reward['micro']}/{reward['mystiko']}/{reward['macro']})"
        )

    print("─" * 68)
    print(
        f"Divergence report: {len(divergences)} of {len(fixture)} games read "
        "differently by the instrument than by the manifest label"
    )
    for line in divergences:
        print(f"  {line}")


# ---------------------------------------------------------------------------


def main() -> int:
    manifest = load_json(MANIFEST_PATH, "catalogue manifest")
    fixture = load_json(FIXTURE_PATH, "classification fixture")
    if manifest is None or fixture is None:
        return 1

    aesthetics = {value for value, _label in AESTHETIC_CHOICES}
    ok(f"canonical aesthetics: {sorted(aesthetics)}")
    print(f"       questionnaire registry: {REGISTRY_VERSION}")

    check_counts(fixture, manifest)
    check_fixture_shape(fixture, manifest, aesthetics)
    check_derivation(fixture)
    report_distribution(fixture)
    report_divergences(fixture)

    print("─" * 68)
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("Classification fixture verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
