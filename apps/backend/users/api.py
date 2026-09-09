"""Users API router — SBGC-221.

Owns the public profile read.  It maps persisted ``UserProfile``/``UserTopGame``
data (plus a deterministic Game-DNA stub) into the public DTO and flags the
viewer-owner state from the ambient request user.  It never calculates DNA and
never writes.
"""

from __future__ import annotations

from api.errors import ApiException
from django.contrib.auth.models import User
from games.models import Game
from ninja import Router, Schema

from users.models import UserProfile, UserTopGame

router = Router(tags=["Users"])


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
    avatar_key: str
    border_type: str
    border_preset_id: int | None = None
    border_color: str
    is_steam_linked: bool
    steam_profile_url: str | None = None
    top_games: list[TopGameOut]
    dna_scores: ProfileScoresOut | None = None
    is_viewer_owner: bool = False


# Username whose Game DNA is stubbed from a canonical published classification
# until real per-user submission DNA lands (SBGC-221 seeder contract).
DNA_STUB_USERNAME = "thenamesammaris"
DNA_STUB_GAME_SLUG = "portal-2"


@router.get("/{username}", response=PublicUserProfileOut)
def public_profile(request, username: str):
    user = (
        User.objects.filter(username__iexact=username).select_related("profile").first()
    )
    if user is None:
        raise ApiException(404, "NOT_FOUND", "User not found.")

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

    return PublicUserProfileOut(
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        bio=profile.bio if profile else "",
        avatar_key=profile.avatar_key if profile else "male_1",
        border_type=(profile.border_type if profile else UserProfile.BorderType.NONE),
        border_preset_id=profile.border_preset_id if profile else None,
        border_color=profile.border_color if profile else "",
        is_steam_linked=profile.is_steam_linked if profile else False,
        steam_profile_url=((profile.steam_profile_url or None) if profile else None),
        top_games=top_games,
        dna_scores=_dna_scores(user),
        is_viewer_owner=(
            request.user.is_authenticated
            and request.user.username.lower() == user.username.lower()
        ),
    )


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
