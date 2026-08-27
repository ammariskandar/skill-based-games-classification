"""
Game domain model — SBGC-45.

Canonical product identity and editorial state.  Owned by the ``games`` app.
Never makes network requests, never imports Steam services.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from games.services.assets import ManualAssetError, validate_manual_image_url
from games.types import CONTENT_TYPE_CHOICES, ContentType


class SourceType(models.TextChoices):
    STEAM = "steam", "Steam"
    MANUAL = "manual", "Manual"


class ListingStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class GameQuerySet(models.QuerySet):
    """Custom queryset for ``Game`` — SBGC-48 / SBGC-49."""

    # -- listing ---------------------------------------------------------------

    def publicly_listable(self):
        """Return only records eligible for the public game listing.

        A game is publicly listable when it has:
        * ``content_type = GAME``
        * ``listing_status = PUBLISHED``
        """
        return self.filter(
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )

    # -- source ----------------------------------------------------------------

    def steam(self):
        """Return only Steam-sourced records."""
        return self.filter(source_type=SourceType.STEAM)

    def manual(self):
        """Return only manual records."""
        return self.filter(source_type=SourceType.MANUAL)


class GameManager(models.Manager["Game"]):
    """Typed manager exposing ``GameQuerySet`` custom methods."""

    def get_queryset(self) -> GameQuerySet:
        return GameQuerySet(self.model, using=self._db)

    # Delegate all custom queryset methods so the type checker sees them.

    def publicly_listable(self) -> GameQuerySet:
        return self.get_queryset().publicly_listable()

    def steam(self) -> GameQuerySet:
        return self.get_queryset().steam()

    def manual(self) -> GameQuerySet:
        return self.get_queryset().manual()


class Game(models.Model):
    """
    Canonical product identity with editorial state.

    Internal Django primary key is the universal identity — Steam App ID,
    external ID, slug, and name are never the primary key.
    """

    # -- Source -----------------------------------------------------------------

    source_type = models.CharField(
        max_length=16,
        choices=SourceType,
    )

    external_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text=(
            "Steam App ID (decimal) — required for Steam, must be NULL for manual."
        ),
    )

    # -- Name and slug ----------------------------------------------------------

    name = models.CharField(max_length=255)

    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="Unique URL-safe identifier. Not regenerated on name changes.",
    )

    # -- Content type -----------------------------------------------------------

    content_type = models.CharField(
        max_length=16,
        choices=CONTENT_TYPE_CHOICES,
        default=ContentType.GAME,
    )

    # -- Listing status ---------------------------------------------------------

    listing_status = models.CharField(
        max_length=16,
        choices=ListingStatus,
        default=ListingStatus.DRAFT,
    )

    # -- Manual metadata --------------------------------------------------------

    release_date = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Release date. Steam-managed for Steam Games unless overridden "
            "in Admin; manually editable for Manual Games. Accepted formats: "
            "YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, or YYYY/MM/DD."
        ),
    )

    developer = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            "Developer name. Steam-managed for Steam Games unless overridden "
            "in Admin; manually editable for Manual Games."
        ),
    )

    description = models.TextField(
        blank=True,
        help_text=(
            "Short description. Steam-managed for Steam Games unless "
            "overridden in Admin; manually editable for Manual Games."
        ),
    )
    manual_image_url = models.URLField(max_length=500, blank=True)
    manual_hero_url = models.URLField(max_length=500, blank=True)
    manual_capsule_url = models.URLField(max_length=500, blank=True)
    manual_website_url = models.URLField(max_length=500, blank=True)

    # -- Steam override provenance (SBGC-188) -----------------------------------

    description_overridden = models.BooleanField(
        default=False,
        help_text=(
            "True = description is human-owned; Steam refresh preserves it. "
            "False = Steam-managed (Steam Games only)."
        ),
    )
    developer_overridden = models.BooleanField(
        default=False,
        help_text=(
            "True = developer is human-owned; Steam refresh preserves it. "
            "False = Steam-managed (Steam Games only)."
        ),
    )
    release_date_overridden = models.BooleanField(
        default=False,
        help_text=(
            "True = release date is human-owned; Steam refresh preserves it. "
            "False = Steam-managed (Steam Games only)."
        ),
    )

    # -- Steam-owned metadata ---------------------------------------------------

    steam_image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text=(
            "Steam header-image URL persisted from import data.  Never "
            "populated from manual/editorial data; use manual_image_url for "
            "manual records."
        ),
    )

    library_hero_url = models.URLField(
        max_length=500,
        blank=True,
        help_text=(
            "Steam Library Hero image URL for the layered Game-detail "
            "presentation.  Steam-owned and derived from the App ID for "
            "base Games; blank for manual and non-game Steam content."
        ),
    )

    library_capsule_url = models.URLField(
        max_length=500,
        blank=True,
        help_text=(
            "Steam Library Capsule (portrait key-art) image URL for the "
            "layered Game-detail presentation.  Steam-owned and derived "
            "from the App ID for base Games; blank for manual and non-game "
            "Steam content."
        ),
    )

    last_steam_refresh_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "When this Steam record's metadata was last successfully "
            "verified against Steam.  NULL = never refreshed.  Not set when "
            "the Steam app is unavailable."
        ),
    )

    # -- Timestamps -------------------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects: GameManager = GameManager()  # type: ignore[assignment]

    # -- Meta -------------------------------------------------------------------

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            # Steam → non-null, nonempty external_id.
            # Manual → NULL external_id.
            models.CheckConstraint(
                condition=(
                    models.Q(source_type=SourceType.STEAM, external_id__isnull=False)
                    & ~models.Q(external_id="")
                )
                | models.Q(
                    source_type=SourceType.MANUAL,
                    external_id__isnull=True,
                ),
                name="game_source_external_id_ck",
            ),
            # Source-qualified unique external identity.
            models.UniqueConstraint(
                fields=["source_type", "external_id"],
                condition=models.Q(external_id__isnull=False),
                name="game_unique_source_external_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["listing_status", "name", "id"],
                name="game_listing_name_idx",
            ),
        ]

    # -- Magic methods ----------------------------------------------------------

    def __str__(self) -> str:
        return f"{self.name} [{self.display_identity}]"

    # -- Validation -------------------------------------------------------------

    def clean(self) -> None:
        super().clean()

        # Name must not be whitespace-only.
        if self.name is not None and self.name.strip() == "":
            raise ValidationError({"name": "Name must not be whitespace-only."})

        # Manual asset references — editor-supplied, HTTPS-only image URLs with
        # a supported extension (SBGC-60 / SBGC-190).  Blank means none.
        for field_name in ("manual_image_url", "manual_hero_url", "manual_capsule_url"):
            value = getattr(self, field_name)
            if value:
                try:
                    setattr(self, field_name, validate_manual_image_url(value))
                except ManualAssetError as exc:
                    raise ValidationError({field_name: str(exc)}) from exc

        # Steam external-ID validation — no network calls.
        if self.source_type == SourceType.STEAM:
            if not self.external_id:
                raise ValidationError(
                    {"external_id": "Steam records require a nonempty App ID."}
                )
            if not self.external_id.isdigit():
                raise ValidationError(
                    {"external_id": "Steam App ID must be a decimal number."}
                )
        else:
            # Manual records must not have an external_id.
            if self.external_id is not None:
                raise ValidationError(
                    {
                        "external_id": (
                            "Manual records must not have an external ID (leave blank)."
                        )
                    }
                )

    # -- Identity ---------------------------------------------------------------

    @property
    def is_manual(self) -> bool:
        """Whether this Game is manual-sourced (SBGC-61)."""
        return self.source_type == SourceType.MANUAL

    @property
    def is_steam(self) -> bool:
        """Whether this Game is Steam-sourced (SBGC-61)."""
        return self.source_type == SourceType.STEAM

    @property
    def display_identity(self) -> str:
        if self.is_steam:
            return f"steam:{self.external_id}"
        return f"manual:{self.slug}"

    @property
    def display_image_url(self) -> str:
        """Effective display image (SBGC-60 / SBGC-190).

        Manual/editorial ``manual_image_url`` is the override when present;
        otherwise Steam-owned ``steam_image_url`` is used.  Manual Games never
        fall back to Steam-owned fields.  Pure — no network or extra query.
        """
        if self.is_steam:
            return self.manual_image_url or self.steam_image_url
        return self.manual_image_url

    @property
    def display_hero_url(self) -> str:
        """Effective Hero artwork (SBGC-190).

        Manual-first with Steam fallback for Steam Games; Manual Games use only
        their manual Hero value.
        """
        if self.is_steam:
            return self.manual_hero_url or self.library_hero_url
        return self.manual_hero_url

    @property
    def display_capsule_url(self) -> str:
        """Effective Capsule artwork (SBGC-190).

        Manual-first with Steam fallback for Steam Games; Manual Games use only
        their manual Capsule value.
        """
        if self.is_steam:
            return self.manual_capsule_url or self.library_capsule_url
        return self.manual_capsule_url


class SteamRefreshRun(models.Model):
    """One daily scheduled Steam-refresh run — the sole retained current audit."""

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    scheduled_at = models.DateTimeField()
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.RUNNING
    )
    selected_count = models.PositiveIntegerField(default=0)
    successful_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    alert_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["-scheduled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["status"],
                condition=models.Q(status="running"),
                name="steam_refresh_run_single_active_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"Steam refresh run {self.scheduled_at.isoformat()}"


class SteamRefreshGameAttempt(models.Model):
    """One per-Game refresh attempt inside a daily run."""

    class Outcome(models.TextChoices):
        SUCCESS = "success", "Success"
        UNAVAILABLE = "unavailable", "Unavailable"
        FAILED = "failed", "Failed"

    run = models.ForeignKey(
        SteamRefreshRun,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="steam_refresh_attempts",
    )
    attempt_number = models.PositiveSmallIntegerField()
    timestamp = models.DateTimeField(default=timezone.now)
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    error_code = models.CharField(max_length=48, blank=True)
    error_summary = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["attempt_number", "game_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "game", "attempt_number"],
                name="steam_refresh_attempt_run_game_num_uniq",
            ),
        ]

    def __str__(self) -> str:
        game_id = self.game_id  # pyright: ignore[reportAttributeAccessIssue]
        run_id = self.run_id  # pyright: ignore[reportAttributeAccessIssue]
        return f"Attempt {self.attempt_number} for {game_id} in run {run_id}"


__all__ = [
    "ContentType",
    "CONTENT_TYPE_CHOICES",
    "Game",
    "ListingStatus",
    "SourceType",
    "SteamRefreshGameAttempt",
    "SteamRefreshRun",
]
