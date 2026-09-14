"""
``classify_initial_catalogue`` management command — SBGC-128.

Seeds an editorial classification for every game in the SBGC-125 catalogue
manifest, from the curated SBGC-128 fixture.  Entries are ingested through the
canonical editorial service (``create_submission`` / ``update_submission``), so
role resolution, base-weight snapshots, profile validation, and the
``(game, submitted_by)`` uniqueness rule all stay owned by that service.

Idempotent: an existing submission by the same user for the same game is updated
in place rather than re-created, so the command can be re-run at any time.

No network access of any kind.

Usage::

    # Validate the whole fixture without writing anything.
    python manage.py classify_initial_catalogue --dry-run

    # Seed all 200 games as the catalogue owner.
    python manage.py classify_initial_catalogue --username timunlessteh
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser
from games.models import Game

from classifications.models import AESTHETIC_CHOICES, EditorialClassification
from classifications.services.submissions import (
    ScoreDistribution,
    create_submission,
    update_submission,
)

DEFAULT_USERNAME = "timunlessteh"
DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "initial_classifications_200.json"
)

DIMENSIONS = ("micro", "mystiko", "macro")
CANONICAL_AESTHETICS = {value for value, _label in AESTHETIC_CHOICES}


class Command(BaseCommand):
    help = (
        "Seed editorial classifications for the initial 200-game catalogue "
        "(SBGC-128 fixture) through the canonical editorial service."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--username",
            default=DEFAULT_USERNAME,
            help=f"Submitting user (default: {DEFAULT_USERNAME}).",
        )
        parser.add_argument(
            "--fixture",
            type=Path,
            default=DEFAULT_FIXTURE_PATH,
            help="Path to the classifications fixture (defaults to the SBGC-128 file).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate every entry without writing to the database.",
        )

    def handle(self, *args: object, **options: object) -> None:
        username: str = options["username"]  # type: ignore[assignment]
        fixture_path: Path = options["fixture"]  # type: ignore[assignment]
        dry_run: bool = options["dry_run"]  # type: ignore[assignment]

        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(
                f"User {username!r} does not exist. Create it (or pass --username) "
                "before running this command."
            )

        entries = self._load_entries(fixture_path)
        self.stdout.write(
            f"Fixture: {fixture_path} ({len(entries)} entries) | submitter: {username}"
        )

        games = {
            game.slug: game
            for game in Game.objects.filter(slug__in=[e["slug"] for e in entries])
        }

        if dry_run:
            self._report_dry_run(entries, games, user)
            return

        self._run_ingest(entries, games, user)

    # -- fixture ----------------------------------------------------------------

    def _load_entries(self, fixture_path: Path) -> list[dict]:
        """Load and fully validate the fixture, failing fast on malformed data."""
        if not fixture_path.is_file():
            raise CommandError(f"Fixture not found: {fixture_path}")

        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Fixture is not valid JSON: {exc}") from exc

        if not isinstance(raw, list):
            raise CommandError("Fixture root must be a JSON array.")

        entries: list[dict] = []
        for index, entry in enumerate(raw):
            if not isinstance(entry, dict):
                raise CommandError(f"Fixture entry {index} is not an object.")

            label = entry.get("slug") or f"entry[{index}]"
            for key in (
                "slug",
                "primary_aesthetic",
                "secondary_aesthetic",
                "challenge_profile",
                "reward_profile",
                "rationale",
            ):
                if not entry.get(key) and key != "secondary_aesthetic":
                    raise CommandError(f"{label}: missing required key {key!r}.")

            for key in ("primary_aesthetic", "secondary_aesthetic"):
                if entry.get(key) and entry[key] not in CANONICAL_AESTHETICS:
                    raise CommandError(f"{label}: unknown aesthetic {entry[key]!r}.")

            # Reuse the canonical validator: ints 0-100 totalling exactly 100.
            self._distribution(label, entry["challenge_profile"], "Challenge")
            self._distribution(label, entry["reward_profile"], "Reward")

            entries.append(entry)

        return entries

    @staticmethod
    def _distribution(label: str, raw: object, profile_label: str) -> ScoreDistribution:
        if not isinstance(raw, dict) or set(raw) != set(DIMENSIONS):
            raise CommandError(
                f"{label}: {profile_label} profile must have exactly "
                f"{'/'.join(DIMENSIONS)}."
            )
        distribution = ScoreDistribution(
            micro=raw["micro"], mystiko=raw["mystiko"], macro=raw["macro"]
        )
        try:
            distribution.validate(profile_label=profile_label)
        except Exception as exc:  # noqa: BLE001 — re-raised as an operator error
            raise CommandError(
                f"{label}: {profile_label} profile invalid: {exc}"
            ) from exc
        return distribution

    # -- dry run ----------------------------------------------------------------

    def _report_dry_run(
        self, entries: list[dict], games: dict[str, Game], user
    ) -> None:
        """Validate and report the plan.  Reads the DB only — never writes."""
        would_create = 0
        would_update = 0
        missing: list[str] = []

        for position, entry in enumerate(entries, start=1):
            game = games.get(entry["slug"])
            if game is None:
                missing.append(entry["slug"])
                self.stdout.write(
                    f"[{position}/{len(entries)}] DRY-RUN missing game: {entry['slug']}"
                )
                continue

            exists = self._existing(game, user) is not None
            action = "update" if exists else "create"
            if exists:
                would_update += 1
            else:
                would_create += 1

            self.stdout.write(
                f"[{position}/{len(entries)}] DRY-RUN would {action}: "
                f"{game.name} {self._vector_summary(entry)}"
            )

        self.stdout.write("")
        self.stdout.write("Summary (dry run — nothing written)")
        self.stdout.write(f"  Would create: {would_create}")
        self.stdout.write(f"  Would update: {would_update}")
        self.stdout.write(f"  Missing games: {len(missing)}")
        self.stdout.write(f"  Total: {len(entries)}")

    # -- ingest -----------------------------------------------------------------

    def _run_ingest(self, entries: list[dict], games: dict[str, Game], user) -> None:
        created = 0
        updated = 0
        skipped = 0
        failed = 0
        errors: list[str] = []

        total = len(entries)
        for position, entry in enumerate(entries, start=1):
            slug = entry["slug"]
            prefix = f"[{position}/{total}]"

            game = games.get(slug)
            if game is None:
                skipped += 1
                self.stdout.write(f"{prefix} Skipped (no game): {slug}")
                continue

            challenge = self._distribution(
                slug, entry["challenge_profile"], "Challenge"
            )
            reward = self._distribution(slug, entry["reward_profile"], "Reward")
            existing = self._existing(game, user)

            try:
                if existing is None:
                    create_submission(
                        game=game,
                        submitted_by=user,
                        updated_by=user,
                        challenge=challenge,
                        reward=reward,
                        notes=entry["rationale"],
                        aesthetic=entry["primary_aesthetic"],
                        secondary_aesthetic=entry.get("secondary_aesthetic"),
                    )
                    created += 1
                    outcome = "Created"
                else:
                    update_submission(
                        existing,
                        updated_by=user,
                        challenge=challenge,
                        reward=reward,
                        notes=entry["rationale"],
                        aesthetic=entry["primary_aesthetic"],
                        secondary_aesthetic=entry.get("secondary_aesthetic"),
                    )
                    updated += 1
                    outcome = "Updated"
            except Exception as exc:  # noqa: BLE001 — one bad entry must not abort the batch
                failed += 1
                errors.append(f"{slug}: {type(exc).__name__}: {exc}")
                self.stdout.write(f"{prefix} Failed: {game.name}")
                continue

            self.stdout.write(
                f"{prefix} {outcome}: {game.name} {self._vector_summary(entry)}"
            )

        self._report_summary(
            created=created,
            updated=updated,
            skipped=skipped,
            failed=failed,
            errors=errors,
            total=total,
        )

    @staticmethod
    def _existing(game: Game, user) -> EditorialClassification | None:
        """Return *user*'s existing submission for *game*, if any.

        Scoped to the submitting user, so another editor's submission for the
        same game is neither matched nor overwritten.
        """
        return EditorialClassification.objects.filter(
            game=game, submitted_by=user
        ).first()

    # -- output -----------------------------------------------------------------

    @staticmethod
    def _vector_summary(entry: dict) -> str:
        def render(values: dict) -> str:
            return "/".join(str(values[dimension]) for dimension in DIMENSIONS)

        return (
            f"(challenge {render(entry['challenge_profile'])} | "
            f"reward {render(entry['reward_profile'])})"
        )

    def _report_summary(
        self,
        *,
        created: int,
        updated: int,
        skipped: int,
        failed: int,
        errors: Sequence[str],
        total: int,
    ) -> None:
        self.stdout.write("")
        self.stdout.write("Summary")
        self.stdout.write(f"  Created: {created}")
        self.stdout.write(f"  Updated: {updated}")
        self.stdout.write(f"  Skipped: {skipped}")
        self.stdout.write(f"  Failed:  {failed}")
        self.stdout.write(f"  Total:   {total}")

        if errors:
            self.stdout.write("")
            self.stdout.write(f"Errors: {len(errors)}")
            for message in errors:
                self.stdout.write(f"  - {message}")
