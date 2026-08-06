"""
Game domain model — SBGC-45.

Canonical product identity and editorial state.  Owned by the ``games`` app.
Never makes network requests, never imports Steam services.
"""

from __future__ import annotations

from classifications.skills import EditorialProfile, SkillCategory
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

    # -- editorial classification ----------------------------------------------

    def editorially_classified(self):
        """Return only Games that have a complete editorial classification.

        Requires: parent row + Challenge profile + Reward profile.
        Excludes: no parent, parent-only, Challenge-only, Reward-only.
        """
        return self.filter(
            editorial_classification__isnull=False,
            editorial_classification__challenge_profile__isnull=False,
            editorial_classification__reward_profile__isnull=False,
        )

    def with_editorial_profiles(self):
        """``select_related`` all editorial classification rows.

        Does NOT filter — returns every Game regardless of classification.
        """
        return self.select_related(
            "editorial_classification",
            "editorial_classification__updated_by",
            "editorial_classification__challenge_profile",
            "editorial_classification__reward_profile",
        )

    # -- dominant skill annotations --------------------------------------------

    def with_dominant_skill_categories(self):
        """Annotate each Game with its Challenge and Reward dominant skill.

        Annotated fields (``str | None``):
        * ``challenge_dominant_skill_category``
        * ``reward_dominant_skill_category``

        Ties produce ``None``.  Missing profiles produce ``None``.
        Uses strict-greater-than comparisons via Django ``Case/When/Q/F``.
        """
        from django.db.models import Case, F, Q, Value, When

        def _dominant(pfx: str):
            micro = f"{pfx}__micro_score"
            mystiko = f"{pfx}__mystiko_score"
            macro = f"{pfx}__macro_score"
            none_val = Value(None)
            return Case(
                When(
                    condition=Q(**{f"{pfx}__isnull": True}),
                    then=none_val,
                ),
                When(
                    condition=(
                        Q(**{f"{micro}__gt": F(mystiko)})
                        & Q(**{f"{micro}__gt": F(macro)})
                    ),
                    then=Value(SkillCategory.MICRO),
                ),
                When(
                    condition=(
                        Q(**{f"{mystiko}__gt": F(micro)})
                        & Q(**{f"{mystiko}__gt": F(macro)})
                    ),
                    then=Value(SkillCategory.MYSTIKO),
                ),
                When(
                    condition=(
                        Q(**{f"{macro}__gt": F(micro)})
                        & Q(**{f"{macro}__gt": F(mystiko)})
                    ),
                    then=Value(SkillCategory.MACRO),
                ),
                default=none_val,
            )

        return self.annotate(
            challenge_dominant_skill_category=_dominant(
                "editorial_classification__challenge_profile"
            ),
            reward_dominant_skill_category=_dominant(
                "editorial_classification__reward_profile"
            ),
        )

    # -- dominant filtering ----------------------------------------------------

    def filter_by_dominant_skill_category(self, *, profile: str, category: str):
        """Return Games whose *profile* dominant skill equals *category*.

        Ties are excluded (strict-greater-than).  Requires complete
        editorial classification.
        """
        _validate_profile_category(profile, category)

        return (
            self.editorially_classified()
            .with_dominant_skill_categories()
            .filter(**{f"{profile}_dominant_skill_category": category})
        )

    # -- score filtering -------------------------------------------------------

    def filter_by_editorial_score(
        self,
        *,
        profile: str,
        category: str,
        minimum: int | None = None,
        maximum: int | None = None,
    ):
        """Return Games whose editorial score falls within inclusive bounds.

        At least one bound must be provided.  Bounds must be integers
        0–100.  *profile* and *category* are validated before querying.
        Requires complete editorial classification.
        """
        if minimum is None and maximum is None:
            raise ValueError("At least one of minimum or maximum is required.")

        _validate_profile_category(profile, category)
        _validate_score_bound(minimum, "minimum")
        _validate_score_bound(maximum, "maximum")

        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError(
                f"minimum ({minimum}) must not exceed maximum ({maximum})."
            )

        field_path = _score_field_path(profile, category)
        qs = self.editorially_classified()

        if minimum is not None:
            qs = qs.filter(**{f"{field_path}__gte": minimum})
        if maximum is not None:
            qs = qs.filter(**{f"{field_path}__lte": maximum})

        return qs

    # -- score sorting ---------------------------------------------------------

    def order_by_editorial_score(
        self,
        *,
        profile: str,
        category: str,
        descending: bool = True,
    ):
        """Order Games by editorial score with deterministic tie-breaking.

        Tie-breaker: selected score → name → id.
        Requires complete editorial classification.
        """
        if not isinstance(descending, bool):
            raise TypeError("descending must be a boolean.")

        _validate_profile_category(profile, category)

        field_path = _score_field_path(profile, category)
        direction = "-" if descending else ""

        return self.editorially_classified().order_by(
            f"{direction}{field_path}",
            "name",
            "id",
        )


# ---------------------------------------------------------------------------
# Query helper validators (private, no DB/network)
# ---------------------------------------------------------------------------


def _validate_profile_category(profile: str, category: str) -> None:
    """Raise ``ValueError`` if *profile* or *category* is invalid."""
    if profile not in EditorialProfile.values:
        raise ValueError(
            f"profile must be one of {set(EditorialProfile.values)}, got {profile!r}."
        )
    if category not in SkillCategory.values:
        raise ValueError(
            f"category must be one of {set(SkillCategory.values)}, got {category!r}."
        )


def _validate_score_bound(value: int | None, label: str) -> None:
    """Raise ``TypeError`` or ``ValueError`` for invalid score bounds."""
    if value is None:
        return
    if isinstance(value, bool):
        raise TypeError(f"{label} must be an integer, not a boolean.")
    if not isinstance(value, int):
        raise TypeError(f"{label} must be an integer.")
    if value < 0 or value > 100:
        raise ValueError(f"{label} must be 0–100 (got {value}).")


_SCORE_FIELD_PATHS: dict[tuple[str, str], str] = {
    (EditorialProfile.CHALLENGE, SkillCategory.MICRO): (
        "editorial_classification__challenge_profile__micro_score"
    ),
    (EditorialProfile.CHALLENGE, SkillCategory.MYSTIKO): (
        "editorial_classification__challenge_profile__mystiko_score"
    ),
    (EditorialProfile.CHALLENGE, SkillCategory.MACRO): (
        "editorial_classification__challenge_profile__macro_score"
    ),
    (EditorialProfile.REWARD, SkillCategory.MICRO): (
        "editorial_classification__reward_profile__micro_score"
    ),
    (EditorialProfile.REWARD, SkillCategory.MYSTIKO): (
        "editorial_classification__reward_profile__mystiko_score"
    ),
    (EditorialProfile.REWARD, SkillCategory.MACRO): (
        "editorial_classification__reward_profile__macro_score"
    ),
}


def _score_field_path(profile: str, category: str) -> str:
    """Return the ORM field path for *profile*/*category*, or raise."""
    key = (profile, category)
    path = _SCORE_FIELD_PATHS.get(key)
    if path is None:
        raise ValueError(f"Unsupported profile/category: {profile!r}/{category!r}")
    return path


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
