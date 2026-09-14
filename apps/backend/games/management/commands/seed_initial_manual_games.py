"""
``seed_initial_manual_games`` management command — SBGC-127.

Reads the SBGC-125 catalogue manifest (``games/fixtures/initial_catalogue_200.json``)
and seeds every ``source == "MANUAL"`` entry through the canonical manual-game
service (``create_manual_game`` / ``update_manual_game``).  No Steam adapter, no
HTTP, no network of any kind — manual Games are entirely local.

The manual service owns identity (``source_type=manual``, ``external_id=NULL``)
and validates every field.  It does not set the manifest-owned ``aesthetic`` or
the optional hero/capsule artwork, so this command applies those afterwards.

Artwork: the manifest carries no image URLs, and the catalogue card already
renders a local placeholder for games with no artwork
(``catalogue-card--no-artwork``), so the fields are deliberately left blank.  If
a curator later adds ``manual_image_url`` / ``manual_hero_url`` /
``manual_capsule_url`` to a manifest entry, the value is honoured.

Idempotent: lookup is ``(source_type=manual, slug=...)``, so re-running updates
existing rows instead of duplicating or tripping the unique slug constraint.

Usage::

    # Plan only — no writes.
    python manage.py seed_initial_manual_games --dry-run

    # Seed all 25 manual entries.
    python manage.py seed_initial_manual_games
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser

from games.models import Aesthetic, Game, ListingStatus, SourceType
from games.services.manual import create_manual_game, update_manual_game
from games.types import ContentType

DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "initial_catalogue_200.json"
)

_CANONICAL_AESTHETICS = {choice.value for choice in Aesthetic}

#: Optional manifest keys applied after the manual service has run.
_ARTWORK_FIELDS = ("manual_image_url", "manual_hero_url", "manual_capsule_url")


class Command(BaseCommand):
    help = (
        "Seed the initial catalogue's manual non-Steam games (SBGC-125 manifest) "
        "through the canonical manual-game service."
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
            help="Report the planned actions without writing to the database.",
        )

    def handle(self, *args: object, **options: object) -> None:
        manifest_path: Path = options["manifest"]  # type: ignore[assignment]
        entries = self._load_manual_entries(manifest_path)

        if not entries:
            self.stdout.write("No manual entries to seed.")
            return

        self.stdout.write(
            f"Manifest: {manifest_path} ({len(entries)} manual entries selected)"
        )

        if options["dry_run"]:
            self._report_dry_run(entries)
            return

        self._run_seed(entries)

    # -- manifest ---------------------------------------------------------------

    def _load_manual_entries(self, manifest_path: Path) -> list[dict]:
        """Return the manifest's MANUAL entries, failing fast on a malformed one."""
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
            if entry.get("source") != "MANUAL":
                continue

            label = entry.get("slug") or f"entry[{index}]"
            for key in (
                "slug",
                "name",
                "developer",
                "release_date",
                "primary_aesthetic",
            ):
                if entry.get(key) in (None, ""):
                    raise CommandError(f"{label}: missing required key {key!r}.")

            if entry["primary_aesthetic"] not in _CANONICAL_AESTHETICS:
                raise CommandError(
                    f"{label}: unknown aesthetic {entry['primary_aesthetic']!r}."
                )

            try:
                date.fromisoformat(entry["release_date"])
            except (TypeError, ValueError) as exc:
                raise CommandError(
                    f"{label}: release_date must be ISO YYYY-MM-DD, got "
                    f"{entry['release_date']!r}."
                ) from exc

            entries.append(entry)

        return entries

    # -- dry run ----------------------------------------------------------------

    def _report_dry_run(self, entries: list[dict]) -> None:
        """Report the planned actions.  Reads the DB only — never writes."""
        would_create = 0
        would_update = 0

        for position, entry in enumerate(entries, start=1):
            exists = self._find_existing(entry["slug"]) is not None
            action = "update" if exists else "create"
            if exists:
                would_update += 1
            else:
                would_create += 1

            self.stdout.write(
                f"[{position}/{len(entries)}] DRY-RUN would {action}: "
                f"{entry['name']} (slug {entry['slug']})"
            )

        self.stdout.write("")
        self.stdout.write("Summary (dry run — nothing written)")
        self.stdout.write(f"  Would create: {would_create}")
        self.stdout.write(f"  Would update: {would_update}")
        self.stdout.write(f"  Total:        {len(entries)}")

    # -- seed -------------------------------------------------------------------

    def _run_seed(self, entries: list[dict]) -> None:
        created = 0
        updated = 0
        unchanged = 0
        failed = 0
        errors: list[str] = []

        total = len(entries)
        for position, entry in enumerate(entries, start=1):
            label = f"{entry['name']} (slug {entry['slug']})"
            prefix = f"[{position}/{total}]"

            try:
                outcome = self._seed_entry(entry)
            except Exception as exc:  # noqa: BLE001 — one bad row must not abort the batch
                failed += 1
                errors.append(f"{label}: {type(exc).__name__}: {exc}")
                self.stdout.write(f"{prefix} Failed: {label}")
                continue

            if outcome == "created":
                created += 1
                self.stdout.write(f"{prefix} Created: {label}")
            elif outcome == "updated":
                updated += 1
                self.stdout.write(f"{prefix} Updated: {label}")
            else:
                unchanged += 1
                self.stdout.write(f"{prefix} Unchanged: {label}")

        self._report_summary(
            created=created,
            updated=updated,
            unchanged=unchanged,
            failed=failed,
            errors=errors,
            total=total,
        )

    def _seed_entry(self, entry: dict) -> str:
        """Create or update one manual Game.

        Returns ``created``, ``updated``, or ``unchanged``.
        """
        existing = self._find_existing(entry["slug"])
        release_date = date.fromisoformat(entry["release_date"])

        if existing is None:
            game = create_manual_game(
                name=entry["name"],
                slug=entry["slug"],
                content_type=ContentType.GAME,
                listing_status=ListingStatus.PUBLISHED,
                release_date=release_date,
                developer=entry["developer"],
                manual_image_url=entry.get("manual_image_url", ""),
            )
            self._apply_manifest_fields(game, entry)
            return "created"

        before = _snapshot(existing)
        update_manual_game(
            existing,
            name=entry["name"],
            developer=entry["developer"],
            release_date=release_date,
            listing_status=ListingStatus.PUBLISHED,
            manual_image_url=entry.get("manual_image_url") or None,
        )
        self._apply_manifest_fields(existing, entry)
        existing.refresh_from_db()
        return "unchanged" if _snapshot(existing) == before else "updated"

    def _find_existing(self, slug: str) -> Game | None:
        """Find the manual Game for *slug*.  Never matches a Steam record."""
        return (
            Game.objects.filter(source_type=SourceType.MANUAL, slug=slug).first()
            or None
        )

    def _apply_manifest_fields(self, game: Game, entry: dict) -> bool:
        """Stamp the manifest aesthetic and any optional artwork.

        Returns ``True`` when something was written.  The manual service has no
        parameter for these fields, so they are applied here — the manifest is
        their owner.
        """
        changed: list[str] = []

        aesthetic = entry["primary_aesthetic"]
        if game.aesthetic != aesthetic:
            game.aesthetic = aesthetic
            changed.append("aesthetic")

        for field_name in _ARTWORK_FIELDS:
            value = entry.get(field_name)
            if value and getattr(game, field_name) != value:
                setattr(game, field_name, value)
                changed.append(field_name)

        if not changed:
            return False

        game.full_clean()
        game.save(update_fields=[*changed, "updated_at"])
        return True

    # -- output -----------------------------------------------------------------

    def _report_summary(
        self,
        *,
        created: int,
        updated: int,
        unchanged: int,
        failed: int,
        errors: list[str],
        total: int,
    ) -> None:
        self.stdout.write("")
        self.stdout.write("Summary")
        self.stdout.write(f"  Created:   {created}")
        self.stdout.write(f"  Updated:   {updated}")
        self.stdout.write(f"  Unchanged: {unchanged}")
        self.stdout.write(f"  Failed:    {failed}")
        self.stdout.write(f"  Total:     {total}")

        if errors:
            self.stdout.write("")
            self.stdout.write(f"Errors: {len(errors)}")
            for message in errors:
                self.stdout.write(f"  - {message}")


def _snapshot(game: Game) -> tuple:
    """Comparable projection of the fields this command may write."""
    return (
        game.name,
        game.developer,
        game.release_date,
        game.listing_status,
        game.aesthetic,
        game.manual_image_url,
        game.manual_hero_url,
        game.manual_capsule_url,
    )
