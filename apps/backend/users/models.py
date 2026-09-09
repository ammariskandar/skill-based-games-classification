"""User profile and social metadata — SBGC-221.

``UserProfile`` is a one-to-one *presentation* extension of the auth ``User``,
kept separate from ``authentication.UserSecurityProfile`` (which owns the
rotation/login-activity state).  ``UserTopGame`` records the ranked top-5 game
strip shown on a profile.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.validators import MaxLengthValidator, RegexValidator
from django.db import models
from games.models import Game


class UserProfile(models.Model):
    class BorderType(models.TextChoices):
        NONE = "NONE", "None"
        PRESET = "PRESET", "Custom Preset Border"
        SOLID = "SOLID", "Solid Color Border"

    class BioMode(models.TextChoices):
        PLAIN = "PLAIN", "Plain Text Mode"
        BBCODE = "BBCODE", "Advanced BBCode Mode"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.CharField(
        max_length=500,
        blank=True,
        default="",
        validators=[MaxLengthValidator(500)],
        help_text="Public profile bio (max 500 raw characters; 250 visible).",
    )
    bio_mode = models.CharField(
        max_length=10,
        choices=BioMode.choices,
        default=BioMode.PLAIN,
        help_text="Formatting engine used to parse and render the bio.",
    )
    avatar_key = models.CharField(
        max_length=64,
        default="male_1",
        help_text="Key identifier of the pre-rendered avatar asset.",
    )
    border_type = models.CharField(
        max_length=10,
        choices=BorderType.choices,
        default=BorderType.NONE,
    )
    border_preset_id = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Border preset index (1 through 5).",
    )
    border_color = models.CharField(
        max_length=7,
        blank=True,
        default="",
        validators=[
            RegexValidator(
                r"^#[0-9A-Fa-f]{6}$", "Must be a valid 6-digit hex color code."
            )
        ],
        help_text="Hex color code for solid color border (e.g. #00FFCC).",
    )
    steam_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Linked 64-bit Steam Community ID.",
    )
    steam_profile_url = models.URLField(
        blank=True,
        default="",
        help_text="Public URL to Steam community profile.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "auth_user_profile"

    def __str__(self) -> str:
        return f"Profile of {self.user.username}"

    @property
    def is_steam_linked(self) -> bool:
        return bool(self.steam_id or self.steam_profile_url)


class UserTopGame(models.Model):
    """Ranked top-5 games displayed on the user profile."""

    profile = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="top_games"
    )
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    rank = models.PositiveSmallIntegerField(help_text="Order rank from 1 to 6.")

    class Meta:
        db_table = "auth_user_top_game"
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "rank"], name="unique_profile_game_rank"
            ),
            models.UniqueConstraint(
                fields=["profile", "game"], name="unique_profile_game_entry"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.profile.user.username} #{self.rank}: {self.game.name}"
