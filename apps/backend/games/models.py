"""
Game domain model — SBGC-45.

Canonical product identity and editorial state.  Owned by the ``games`` app.
Never makes network requests, never imports Steam services.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models


class SourceType(models.TextChoices):
    STEAM = "steam", "Steam"
    MANUAL = "manual", "Manual"


class ContentType(models.TextChoices):
    GAME = "game", "Game"
    DLC = "dlc", "Downloadable content"
    DEMO = "demo", "Demo"
    SOFTWARE = "software", "Software"
    SOUNDTRACK = "soundtrack", "Soundtrack"
    UNKNOWN = "unknown", "Unknown"


class ListingStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class GameQuerySet(models.QuerySet):
    """Custom queryset for ``Game`` — SBGC-48."""

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
        choices=ContentType,
        default=ContentType.GAME,
    )

    # -- Listing status ---------------------------------------------------------

    listing_status = models.CharField(
        max_length=16,
        choices=ListingStatus,
        default=ListingStatus.DRAFT,
    )

    # -- Manual metadata --------------------------------------------------------

    manual_description = models.TextField(blank=True)
    manual_image_url = models.URLField(max_length=500, blank=True)
    manual_website_url = models.URLField(max_length=500, blank=True)

    # -- Timestamps -------------------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = GameQuerySet.as_manager()

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
    def display_identity(self) -> str:
        if self.source_type == SourceType.STEAM:
            return f"steam:{self.external_id}"
        return f"manual:{self.slug}"


__all__ = [
    "ContentType",
    "Game",
    "ListingStatus",
    "SourceType",
]
