"""
``import_initial_steam_games`` management command — SBGC-126.

Reads the SBGC-125 catalogue manifest (``games/fixtures/initial_catalogue_200.json``)
and imports every ``source == "STEAM"`` entry through the canonical Steam import
pipeline (``SteamGameImportService``).  No Steam fetching or JSON parsing is
re-implemented here — this command only sequences the existing service and then
applies the manifest-owned editorial fields (``aesthetic``, ``listing_status``)
that the import service deliberately does not set.

Idempotent: identity is ``(source_type=steam, external_id=app_id)``, so re-running
updates existing rows instead of tripping the unique constraints.

Usage::

    # Plan only — no network, no writes.
    python manage.py import_initial_steam_games --dry-run

    # Import the first 5 entries with the default 0.5s inter-request delay.
    python manage.py import_initial_steam_games --limit 5

    # Full import.
    python manage.py import_initial_steam_games
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser

from games.models import Aesthetic, Game, ListingStatus, SourceType
from games.services.imports.factory import build_steam_import_service
from games.services.imports.steam import SteamGameImportStatus
from games.types import ContentType

DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "initial_catalogue_200.json"
)
DEFAULT_DELAY_SECONDS = 0.5

_CANONICAL_AESTHETICS = {choice.value for choice in Aesthetic}

_OUTCOME_LABELS = {
    SteamGameImportStatus.CREATED: "Created",
    SteamGameImportStatus.UPDATED: "Updated",
    SteamGameImportStatus.UNCHANGED: "Unchanged",
}


class Command(BaseCommand):
    help = (
        "Import the initial catalogue's Steam games (SBGC-125 manifest) through "
        "the canonical Steam import pipeline."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--manifest",
            type=Path,
            default=DEFAULT_MANIFEST_PATH,
            help="Path to the catalogue manifest (defaults to the SBGC-125 fixture).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the planned actions without network calls or writes.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process at most N Steam entries (for staged verification).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=DEFAULT_DELAY_SECONDS,
            help="Seconds to sleep between Steam API calls (default: 0.5).",
        )

    def handle(self, *args: object, **options: object) -> None:
        manifest_path: Path = options["manifest"]  # type: ignore[assignment]
        entries = self._load_steam_entries(manifest_path)

        limit = options["limit"]
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise CommandError("--limit must be a non-negative integer.")
            entries = entries[:limit]

        delay: float = options["delay"]  # type: ignore[assignment]
        if delay < 0:
            raise CommandError("--delay must be non-negative.")

        if not entries:
            self.stdout.write("No Steam entries to import.")
            return

        self.stdout.write(
            f"Manifest: {manifest_path} ({len(entries)} Steam entries selected)"
        )

        if options["dry_run"]:
            self._report_dry_run(entries)
            return

        self._run_import(entries, delay=delay)

    # -- manifest ---------------------------------------------------------------

    def _load_steam_entries(self, manifest_path: Path) -> list[dict]:
        """Return the manifest's Steam entries, failing fast on a malformed one."""
        if not manifest_path.is_file():
            raise CommandError(f"Manifest not found: {manifest_path}")

        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Manifest is not valid JSON: {exc}") from exc

        if not isinstance(raw, list):
            raise CommandError("Manifest root must be a JSON array.")

        entries: list[dict] = []
        for index, entry in enumerate(raw):
            if not isinstance(entry, dict):
                raise CommandError(f"Manifest entry {index} is not an object.")
            if entry.get("source") != "STEAM":
                continue

            label = entry.get("slug") or f"entry[{index}]"
            for key in ("slug", "name", "steam_appid", "primary_aesthetic"):
                if entry.get(key) in (None, ""):
                    raise CommandError(f"{label}: missing required key {key!r}.")

            app_id = entry["steam_appid"]
            if isinstance(app_id, bool) or not isinstance(app_id, int) or app_id <= 0:
                raise CommandError(f"{label}: steam_appid must be a positive integer.")

            if entry["primary_aesthetic"] not in _CANONICAL_AESTHETICS:
                raise CommandError(
                    f"{label}: unknown aesthetic {entry['primary_aesthetic']!r}."
                )

            entries.append(entry)

        return entries

    # -- dry run ----------------------------------------------------------------

    def _report_dry_run(self, entries: list[dict]) -> None:
        """Report the planned actions.  Reads the DB only — no writes, no network."""
        would_create = 0
        would_update = 0

        for position, entry in enumerate(entries, start=1):
            app_id = str(entry["steam_appid"])
            exists = Game.objects.filter(
                source_type=SourceType.STEAM,
                external_id=app_id,
            ).exists()

            action = "update" if exists else "create"
            if exists:
                would_update += 1
            else:
                would_create += 1

            self.stdout.write(
                f"[{position}/{len(entries)}] DRY-RUN would {action}: "
                f"{entry['name']} (AppID {app_id})"
            )

        self.stdout.write("")
        self.stdout.write("Summary (dry run — nothing written, no network calls)")
        self.stdout.write(f"  Would create: {would_create}")
        self.stdout.write(f"  Would update: {would_update}")
        self.stdout.write(f"  Total:        {len(entries)}")

    # -- import -----------------------------------------------------------------

    def _run_import(self, entries: list[dict], *, delay: float) -> None:
        service = build_steam_import_service()

        created = 0
        updated = 0
        skipped = 0
        failed = 0
        published = 0
        withheld: list[str] = []
        errors: list[str] = []

        total = len(entries)
        for position, entry in enumerate(entries, start=1):
            app_id = str(entry["steam_appid"])
            label = f"{entry['name']} (AppID {app_id})"
            prefix = f"[{position}/{total}]"

            try:
                result = service.import_app(app_id)
            except Exception as exc:  # noqa: BLE001 — one bad app must not abort the batch
                failed += 1
                errors.append(f"{label}: {type(exc).__name__}: {exc}")
                self.stdout.write(f"{prefix} Failed: {label}")
                continue

            if result.status == SteamGameImportStatus.UNAVAILABLE:
                skipped += 1
                self.stdout.write(f"{prefix} Skipped (unavailable): {label}")
            else:
                if result.status == SteamGameImportStatus.CREATED:
                    created += 1
                elif result.status == SteamGameImportStatus.UPDATED:
                    updated += 1
                else:
                    skipped += 1

                outcome = _OUTCOME_LABELS[result.status]

                if self._apply_manifest_fields(result.game_id, entry):
                    published += 1
                    self.stdout.write(f"{prefix} {outcome}: {label}")
                else:
                    withheld.append(label)
                    self.stdout.write(f"{prefix} {outcome} (not a base game): {label}")

            if position < total and delay > 0:
                time.sleep(delay)

        self._report_summary(
            created=created,
            updated=updated,
            skipped=skipped,
            failed=failed,
            published=published,
            withheld=withheld,
            errors=errors,
            total=total,
        )

    def _apply_manifest_fields(self, game_id: int | None, entry: dict) -> bool:
        """Publish *game_id* and stamp the manifest aesthetic.

        Returns ``False`` when the row is not a base game, in which case it is left
        untouched (drafts stay draft) — imports never publish non-game content.
        """
        if game_id is None:
            return False

        game = Game.objects.get(pk=game_id)
        if game.content_type != ContentType.GAME:
            return False

        changed: list[str] = []
        aesthetic = entry["primary_aesthetic"]
        if game.aesthetic != aesthetic:
            game.aesthetic = aesthetic
            changed.append("aesthetic")
        if game.listing_status != ListingStatus.PUBLISHED:
            game.listing_status = ListingStatus.PUBLISHED
            changed.append("listing_status")

        if changed:
            game.save(update_fields=[*changed, "updated_at"])
        return True

    # -- output -----------------------------------------------------------------

    def _report_summary(
        self,
        *,
        created: int,
        updated: int,
        skipped: int,
        failed: int,
        published: int,
        withheld: Sequence[str],
        errors: Sequence[str],
        total: int,
    ) -> None:
        self.stdout.write("")
        self.stdout.write("Summary")
        self.stdout.write(f"  Created:  {created}")
        self.stdout.write(f"  Updated:  {updated}")
        self.stdout.write(f"  Skipped:  {skipped}")
        self.stdout.write(f"  Failed:   {failed}")
        self.stdout.write(f"  Total:    {total}")
        self.stdout.write(f"  Published (listing_status=PUBLISHED): {published}")

        if withheld:
            self.stdout.write("")
            self.stdout.write(f"Left unpublished (not a base game): {len(withheld)}")
            for label in withheld:
                self.stdout.write(f"  - {label}")

        if errors:
            self.stdout.write("")
            self.stdout.write(f"Errors: {len(errors)}")
            for message in errors:
                self.stdout.write(f"  - {message}")
