"""Users API router — SBGC-221 / SBGC-222.

Owns the public profile read and the authenticated self-update.  It maps
persisted ``UserProfile``/``UserTopGame`` data (plus a deterministic Game-DNA
stub) into the public DTO and flags the viewer-owner state from the ambient
request user.  It never calculates DNA and never writes on the read path; the
``PATCH /me`` endpoint is the single write boundary for profile edits.
"""

from __future__ import annotations

import unicodedata

from api.errors import ApiException
from django.contrib.auth.models import User
from django.db import transaction
from games.models import Game
from ninja import Field, Router, Schema
from pydantic import field_validator

from users.models import UserProfile, UserTopGame

router = Router(tags=["Users"])


# Lockout statuses surfaced to the owner so the frontend can render the forced
# remediation UI (SBGC-223).
class TopGameOut(Schema):
    rank: int
    game_name: str
    slug: str
    capsule_url: str | None = None


class ProfileScoresOut(Schema):
    challenge_micro: int
    challenge_mystiko: int
    challenge_macro: int
    reward_micro: int
    reward_mystiko: int
    reward_macro: int


class PublicUserProfileOut(Schema):
    username: str
    first_name: str
    last_name: str
    bio: str
    bio_mode: str
    avatar_key: str
    border_type: str
    border_preset_id: int | None = None
    border_color: str
    is_steam_linked: bool
    steam_profile_url: str | None = None
    top_games: list[TopGameOut]
    dna_scores: ProfileScoresOut | None = None
    is_viewer_owner: bool = False
    moderation_lockout: str | None = None


# Canonical avatar keys matching the 18 ingested AVIF assets (SBGC-221).
AVATAR_KEYS = frozenset(
    {
        "male_1",
        "male_2",
        "male_3",
        "male_4",
        "male_5",
        "female_1",
        "female_2",
        "female_3",
        "female_4",
        "female_5",
        "anime_male_1",
        "anime_male_2",
        "anime_male_3",
        "anime_male_4",
        "anime_female_1",
        "anime_female_2",
        "anime_female_3",
        "anime_female_4",
    }
)

# Username whose Game DNA is stubbed from a canonical published classification
# until real per-user submission DNA lands (SBGC-221 seeder contract).
DNA_STUB_USERNAME = "thenamesammaris"
DNA_STUB_GAME_SLUG = "portal-2"


class ProfileUpdateIn(Schema):
    first_name: str = Field(default="", max_length=100)
    last_name: str = Field(default="", max_length=100)
    bio: str = Field(default="", max_length=500)
    bio_mode: str = Field(default="PLAIN", pattern="^(PLAIN|BBCODE)$")
    avatar_key: str = Field(default="male_1", max_length=64)
    border_type: str = Field(default="NONE", pattern="^(NONE|PRESET|SOLID)$")
    border_preset_id: int | None = Field(default=None, ge=1, le=5)
    border_color: str = Field(default="", pattern="^(|#[0-9A-Fa-f]{6})$")

    @field_validator("avatar_key")
    @classmethod
    def validate_avatar_key(cls, value: str) -> str:
        if value not in AVATAR_KEYS:
            raise ValueError(f"Invalid avatar_key '{value}'.")
        return value

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_characters(cls, value: str) -> str:
        # Full Unicode support: letters, digits, whitespace, hyphens,
        # apostrophes, and combining/format marks (e.g. decomposed accents).
        for ch in value:
            category = unicodedata.category(ch)
            if ch.isalnum() or ch.isspace() or ch in ("-", "'"):
                continue
            if category.startswith("M") or category == "Cf":
                continue
            raise ValueError(
                "Names must contain only letters, numbers, spaces, hyphens, "
                "and apostrophes."
            )
        return value.strip()


@router.patch("/me", response=PublicUserProfileOut)
def update_current_user_profile(request, payload: ProfileUpdateIn):
    if not request.user.is_authenticated:
        raise ApiException(401, "AUTHENTICATION_ERROR", "Authentication required.")

    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # Consistency validation for the border customization attributes.
    if payload.border_type == UserProfile.BorderType.PRESET:
        if payload.border_preset_id is None:
            raise ApiException(
                422,
                "VALIDATION_ERROR",
                "border_preset_id is required when border_type is PRESET.",
            )
        border_preset_id = payload.border_preset_id
        border_color = ""
    elif payload.border_type == UserProfile.BorderType.SOLID:
        if not payload.border_color:
            raise ApiException(
                422,
                "VALIDATION_ERROR",
                "border_color is required when border_type is SOLID.",
            )
        border_preset_id = None
        border_color = payload.border_color.upper()
    else:
        border_preset_id = None
        border_color = ""

    with transaction.atomic():
        before = (user.first_name, user.last_name)
        profile_before = profile.bio if profile else ""

        user.first_name = payload.first_name
        user.last_name = payload.last_name
        user.save(update_fields=["first_name", "last_name"])

        profile.bio = payload.bio
        profile.bio_mode = payload.bio_mode
        profile.avatar_key = payload.avatar_key
        profile.border_type = payload.border_type
        profile.border_preset_id = border_preset_id
        profile.border_color = border_color
        profile.save()

    _resolve_bio_lockout_if_changed(
        user,
        changed=(user.first_name, user.last_name) != before
        or profile.bio != profile_before,
    )

    return resolve_public_profile(user, viewer=user)


def _resolve_bio_lockout_if_changed(user: User, *, changed: bool) -> None:
    """Clear a forced name/bio lockout once a real delta is saved (SBGC-223)."""
    if not changed:
        return
    from security.models import ReportStatus
    from security.services.reporting import (
        active_lockout_status,
        complete_bio_remediation,
    )

    if active_lockout_status(user) == ReportStatus.PENDING_BIO_CHANGE:
        complete_bio_remediation(user)


@router.get("/{username}", response=PublicUserProfileOut)
def public_profile(request, username: str):
    user = (
        User.objects.filter(username__iexact=username).select_related("profile").first()
    )
    if user is None:
        raise ApiException(404, "NOT_FOUND", "User not found.")

    return resolve_public_profile(user, viewer=request.user)


def resolve_public_profile(user: User, viewer: User | None) -> PublicUserProfileOut:
    """Build the public DTO for *user* with ownership flagged for *viewer*."""
    profile = getattr(user, "profile", None)

    top_games: list[TopGameOut] = []
    if profile is not None:
        for top in UserTopGame.objects.filter(profile=profile).select_related("game"):
            top_games.append(
                TopGameOut(
                    rank=top.rank,
                    game_name=top.game.name,
                    slug=top.game.slug,
                    capsule_url=top.game.display_capsule_url or None,
                )
            )

    is_owner = (
        viewer is not None
        and viewer.is_authenticated
        and viewer.username.lower() == user.username.lower()
    )

    return PublicUserProfileOut(
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        bio=profile.bio if profile else "",
        bio_mode=profile.bio_mode if profile else UserProfile.BioMode.PLAIN,
        avatar_key=profile.avatar_key if profile else "male_1",
        border_type=(profile.border_type if profile else UserProfile.BorderType.NONE),
        border_preset_id=profile.border_preset_id if profile else None,
        border_color=profile.border_color if profile else "",
        is_steam_linked=profile.is_steam_linked if profile else False,
        steam_profile_url=((profile.steam_profile_url or None) if profile else None),
        top_games=top_games,
        dna_scores=_dna_scores(user),
        is_viewer_owner=is_owner,
        moderation_lockout=(_owner_lockout(user) if is_owner else None),
    )


def _owner_lockout(user: User) -> str | None:
    """Return the viewer-owner's active moderation lockout, if any (SBGC-223)."""
    from security.services.reporting import active_lockout_status

    return active_lockout_status(user)


def _dna_scores(user: User) -> ProfileScoresOut | None:
    """Return the stubbed Game DNA for the designated test user, if available."""
    if user.username.lower() != DNA_STUB_USERNAME:
        return None

    game = Game.objects.filter(slug=DNA_STUB_GAME_SLUG).first()
    if game is None:
        return None

    # Lazy import keeps the classification engine out of the users module
    # import surface — this is a read-only boundary, never a calculation.
    from classifications.services.calculations import get_published_classification

    published = get_published_classification(game)
    if not published.available or not published.unified:
        return None

    # Canonical persisted order is [micro, macro, mystiko] (SBGC-81).
    challenge = published.unified.get("challenge") or []
    reward = published.unified.get("reward") or []
    if len(challenge) != 3 or len(reward) != 3:
        return None

    return ProfileScoresOut(
        challenge_micro=challenge[0],
        challenge_mystiko=challenge[2],
        challenge_macro=challenge[1],
        reward_micro=reward[0],
        reward_mystiko=reward[2],
        reward_macro=reward[1],
    )
