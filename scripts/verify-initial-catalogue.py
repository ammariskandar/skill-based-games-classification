#!/usr/bin/env python3
"""Initial catalogue manifest validator — SBGC-125.

Validates ``apps/backend/games/fixtures/initial_catalogue_200.json`` against the
canonical domain vocabulary and, with ``--online``, against the live Steam Store
API so every ``steam_appid`` is proven to resolve to a standalone base game.

Offline checks (default) need no network and run in CI:

* the manifest parses as a JSON array of objects
* exactly 200 entries, split 175 ``STEAM`` / 25 ``MANUAL``
* slugs and non-null ``steam_appid`` values are unique
* every Steam entry has a positive integer ``steam_appid`` and no manual metadata
* every manual entry has ``steam_appid: null`` plus ``developer`` and ``release_date``
* aesthetics and ``intended_dominant`` match the canonical enums
* ``primary_aesthetic != secondary_aesthetic``

Online checks (``--online``) query ``store.steampowered.com`` per AppID and assert
``success == true`` and ``data.type == "game"`` (rejecting DLC, demos, soundtracks,
and software).  This is the gate that keeps SBGC-126's bulk import free of 404s.

Usage (from the repository root):

    apps/backend/.venv/bin/python scripts/verify-initial-catalogue.py
    apps/backend/.venv/bin/python scripts/verify-initial-catalogue.py --online

Exit code 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = (
    REPO_ROOT / "apps" / "backend" / "games" / "fixtures" / "initial_catalogue_200.json"
)

sys.path.insert(0, str(REPO_ROOT / "apps" / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
os.environ.setdefault("DJANGO_SKIP_DOTENV", "1")

import django  # noqa: E402

django.setup()

EXPECTED_TOTAL = 200
EXPECTED_STEAM = 175
EXPECTED_MANUAL = 25

APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails?appids={appid}"
ONLINE_DELAY_SECONDS = 0.6
ONLINE_TIMEOUT_SECONDS = 20
ONLINE_ATTEMPTS = 5

FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)
    print(f"[FAIL] {message}")


def ok(message: str) -> None:
    print(f"[PASS] {message}")


# ---------------------------------------------------------------------------
# Offline validation
# ---------------------------------------------------------------------------


def canonical_vocabulary() -> tuple[set[str], set[str], set[str]]:
    """Return (aesthetics, dimensions, source labels) from the real enums."""
    from classifications.questionnaire.registry.v1.types import Dimension
    from games.models import Aesthetic, SourceType

    aesthetics = {choice.value for choice in Aesthetic}
    dimensions = {dimension.value for dimension in Dimension}
    sources = {SourceType.STEAM.upper(), SourceType.MANUAL.upper()}
    return aesthetics, dimensions, sources


def load_manifest() -> list[dict] | None:
    if not MANIFEST_PATH.exists():
        fail(f"manifest not found at {MANIFEST_PATH.relative_to(REPO_ROOT)}")
        return None
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"manifest is not valid JSON: {exc}")
        return None
    if not isinstance(data, list):
        fail("manifest root must be a JSON array")
        return None
    ok(f"manifest parses as a JSON array ({len(data)} entries)")
    return data


def check_counts(entries: list[dict]) -> None:
    if len(entries) != EXPECTED_TOTAL:
        fail(f"expected {EXPECTED_TOTAL} entries, found {len(entries)}")
    else:
        ok(f"entry count is exactly {EXPECTED_TOTAL}")

    sources = Counter(entry.get("source") for entry in entries)
    steam = sources.get("STEAM", 0)
    manual = sources.get("MANUAL", 0)
    if steam != EXPECTED_STEAM or manual != EXPECTED_MANUAL:
        fail(f"expected {EXPECTED_STEAM}/{EXPECTED_MANUAL} split, got {steam}/{manual}")
    else:
        ok(f"source split is exactly {EXPECTED_STEAM} STEAM / {EXPECTED_MANUAL} MANUAL")

    dominants = Counter(entry.get("intended_dominant") for entry in entries)
    summary = ", ".join(f"{key}={dominants[key]}" for key in sorted(dominants))
    ok(f"intended_dominant distribution: {summary}")


def check_uniqueness(entries: list[dict]) -> None:
    duplicate_slugs = [
        slug
        for slug, count in Counter(e.get("slug") for e in entries).items()
        if count > 1
    ]
    if duplicate_slugs:
        fail(f"duplicate slugs: {duplicate_slugs}")
    else:
        ok("all slugs are unique")

    appids = [e.get("steam_appid") for e in entries if e.get("steam_appid") is not None]
    duplicate_appids = [appid for appid, count in Counter(appids).items() if count > 1]
    if duplicate_appids:
        fail(f"duplicate steam_appid values: {duplicate_appids}")
    else:
        ok("all non-null steam_appid values are unique")


def check_entry_shape(
    entries: list[dict], aesthetics: set[str], dimensions: set[str], sources: set[str]
) -> None:
    problems: list[str] = []
    for index, entry in enumerate(entries):
        label = entry.get("slug") or f"entry[{index}]"
        missing = {
            "slug",
            "name",
            "source",
            "steam_appid",
            "primary_aesthetic",
            "secondary_aesthetic",
            "intended_dominant",
        } - set(entry)
        if missing:
            problems.append(f"{label}: missing keys {sorted(missing)}")
            continue

        if entry["source"] not in sources:
            problems.append(f"{label}: unknown source {entry['source']!r}")
        if entry["primary_aesthetic"] not in aesthetics:
            problems.append(
                f"{label}: unknown primary_aesthetic {entry['primary_aesthetic']!r}"
            )
        if entry["secondary_aesthetic"] not in aesthetics:
            problems.append(
                f"{label}: unknown secondary_aesthetic {entry['secondary_aesthetic']!r}"
            )
        if entry["primary_aesthetic"] == entry["secondary_aesthetic"]:
            problems.append(f"{label}: primary and secondary aesthetic are identical")
        if entry["intended_dominant"] not in dimensions:
            problems.append(
                f"{label}: unknown intended_dominant {entry['intended_dominant']!r}"
            )

        appid = entry["steam_appid"]
        if entry["source"] == "STEAM":
            if not isinstance(appid, int) or isinstance(appid, bool) or appid <= 0:
                problems.append(
                    f"{label}: STEAM steam_appid must be a positive int, got {appid!r}"
                )
        else:
            if appid is not None:
                problems.append(
                    f"{label}: MANUAL entry must have steam_appid null, got {appid!r}"
                )
            for field in ("developer", "release_date"):
                if not entry.get(field):
                    problems.append(f"{label}: MANUAL entry is missing '{field}'")

    if problems:
        for problem in problems:
            fail(problem)
    else:
        ok("every entry matches the schema contract and canonical enums")


def check_aesthetic_spread(entries: list[dict]) -> None:
    primary = Counter(e["primary_aesthetic"] for e in entries)
    summary = ", ".join(f"{key}={primary[key]}" for key in sorted(primary))
    ok(f"primary_aesthetic distribution: {summary}")
    if len(primary) != 4:
        fail(f"all four aesthetics must be represented, found {sorted(primary)}")
    if min(primary.values()) < 15:
        fail(
            f"under-represented aesthetics: {[k for k, v in primary.items() if v < 15]}"
        )


# ---------------------------------------------------------------------------
# Online validation
# ---------------------------------------------------------------------------


def fetch_app(appid: int) -> dict | None:
    """Return the Steam appdetails payload for *appid*, retrying transient errors.

    The Store API rate-limits bursts, so a 429/5xx or a truncated read is treated
    as retryable with a linear backoff rather than as an unknown AppID.
    """
    request = urllib.request.Request(
        APP_DETAILS_URL.format(appid=appid),
        headers={
            "User-Agent": "MyGameDNA-CatalogueValidator/1.0",
            "Accept-Encoding": "identity",
        },
    )
    for attempt in range(1, ONLINE_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(
                request, timeout=ONLINE_TIMEOUT_SECONDS
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get(str(appid))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            if attempt == ONLINE_ATTEMPTS:
                return None
            time.sleep(ONLINE_DELAY_SECONDS * attempt * 2)
    return None


def check_steam_online(entries: list[dict]) -> None:
    steam_entries = [e for e in entries if e["source"] == "STEAM"]
    print(f"── querying store.steampowered.com for {len(steam_entries)} AppIDs ──")

    invalid: list[str] = []
    type_counts: Counter[str] = Counter()

    for position, entry in enumerate(steam_entries, start=1):
        appid = entry["steam_appid"]
        payload = fetch_app(appid)
        if payload is None:
            invalid.append(
                f"{entry['slug']} ({appid}): fetch failed x{ONLINE_ATTEMPTS}"
            )
        elif not payload.get("success"):
            invalid.append(f"{entry['slug']} ({appid}): success=false (unknown AppID)")
        else:
            data = payload.get("data") or {}
            app_type = data.get("type")
            type_counts[app_type] += 1
            if app_type != "game":
                invalid.append(
                    f"{entry['slug']} ({appid}): type={app_type!r}, not a game"
                )
        if position % 25 == 0:
            print(f"    ...{position}/{len(steam_entries)} checked")
        time.sleep(ONLINE_DELAY_SECONDS)

    if invalid:
        for item in invalid:
            fail(f"steam: {item}")
    else:
        ok(f"all {len(steam_entries)} Steam AppIDs resolve to standalone games")

    summary = ", ".join(f"{key}={value}" for key, value in sorted(type_counts.items()))
    ok(f"Steam AppID type distribution: {summary}")


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--online",
        action="store_true",
        help="verify AppIDs against the Steam Store API",
    )
    args = parser.parse_args()

    aesthetics, dimensions, sources = canonical_vocabulary()
    ok(f"canonical aesthetics: {sorted(aesthetics)}")
    ok(f"canonical dimensions: {sorted(dimensions)}")

    entries = load_manifest()
    if entries is None:
        return 1

    check_counts(entries)
    check_uniqueness(entries)
    check_entry_shape(entries, aesthetics, dimensions, sources)
    check_aesthetic_spread(entries)

    if args.online:
        check_steam_online(entries)

    print("─" * 68)
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("Catalogue manifest verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
