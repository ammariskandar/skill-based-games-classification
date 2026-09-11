"""
Similar-games math & engine — SBGC-227.

Two layers:

* **Pure math** (this is what the unit tests exercise): distance-based Challenge
  and Reward similarity, aesthetic compatibility, asymmetric confidence
  weighting, 10%-step floor quantization, and the final rounding.
* **DB engine** (``compute_similarities_for`` / ``run_similarity_engine``):
  discovers changed games and bulk-upserts directed :class:`GameSimilarity`
  rows.  Imported lazily so the math stays usable without Django app setup.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from games.models import Game

CHALLENGE_WEIGHT = 50.0
REWARD_WEIGHT = 40.0
PROFILE_DENOMINATOR = 200.0

BASE_GAME_CONFIDENCE_WEIGHT = 0.30
CANDIDATE_CONFIDENCE_WEIGHT = 0.70

CONFIDENCE_FLOOR = 0.10
CONFIDENCE_STEP = 10.0

AESTHETIC_EXACT = 10
AESTHETIC_DOMINANT = 6
AESTHETIC_INVERTED = 4
AESTHETIC_SECONDARY = 2
AESTHETIC_OPPOSITE = 1
AESTHETIC_NONE = 0


@dataclass(frozen=True)
class ProfileVector:
    """One 100-point (Micro, Macro, Mystiko) profile."""

    micro: int
    macro: int
    mystiko: int

    @staticmethod
    def from_unified(values: Sequence[int] | None) -> ProfileVector | None:
        """Build from the snapshot's canonical ``[micro, macro, mystiko]`` list."""
        if not values or len(values) < 3:
            return None
        try:
            micro, macro, mystiko = (int(values[0]), int(values[1]), int(values[2]))
        except (TypeError, ValueError):
            return None
        return ProfileVector(micro=micro, macro=macro, mystiko=mystiko)


@dataclass(frozen=True)
class AestheticLabel:
    """A resolved primary/secondary aesthetic pair (either may be ``None``)."""

    primary: str | None
    secondary: str | None


def _l1(a: ProfileVector, b: ProfileVector) -> int:
    return abs(a.micro - b.micro) + abs(a.macro - b.macro) + abs(a.mystiko - b.mystiko)


def challenge_similarity(a: ProfileVector | None, b: ProfileVector | None) -> float:
    """Challenge similarity in ``[0, 50]``; 0 when either side is unpublished."""
    if a is None or b is None:
        return 0.0
    return CHALLENGE_WEIGHT * (1 - _l1(a, b) / PROFILE_DENOMINATOR)


def reward_similarity(a: ProfileVector | None, b: ProfileVector | None) -> float:
    """Reward similarity in ``[0, 40]``; 0 when either side is unpublished."""
    if a is None or b is None:
        return 0.0
    return REWARD_WEIGHT * (1 - _l1(a, b) / PROFILE_DENOMINATOR)


def aesthetic_similarity(a: AestheticLabel, b: AestheticLabel) -> int:
    """Aesthetic compatibility in ``[0, 10]``.

    An unresolved (``None``) primary or secondary on either side scores 0.
    """
    pa, sa = a.primary, a.secondary
    pb, sb = b.primary, b.secondary
    if pa is None or sa is None or pb is None or sb is None:
        return AESTHETIC_NONE
    if pa == pb and sa == sb:
        return AESTHETIC_EXACT
    if pa == pb:
        return AESTHETIC_DOMINANT
    if pa == sb and sa == pb:
        return AESTHETIC_INVERTED
    if sa == sb:
        return AESTHETIC_SECONDARY
    if pa == sb or sa == pb:
        return AESTHETIC_OPPOSITE
    return AESTHETIC_NONE


def base_similarity(
    *,
    challenge_a: ProfileVector | None,
    challenge_b: ProfileVector | None,
    reward_a: ProfileVector | None,
    reward_b: ProfileVector | None,
    aesthetic_a: AestheticLabel,
    aesthetic_b: AestheticLabel,
) -> float:
    """``S_base = S_challenge + S_reward + S_aesthetic`` (``[0, 100]``)."""
    return (
        challenge_similarity(challenge_a, challenge_b)
        + reward_similarity(reward_a, reward_b)
        + aesthetic_similarity(aesthetic_a, aesthetic_b)
    )


def weighted_confidence(confidence_a: float, confidence_b: float) -> float:
    """Asymmetric blend: base game 30%, candidate game 70%."""
    return (
        BASE_GAME_CONFIDENCE_WEIGHT * confidence_a
        + CANDIDATE_CONFIDENCE_WEIGHT * confidence_b
    )


def quantize_confidence(confidence: float) -> float:
    """Floor a 0–100 confidence to 10% steps with a 0.10 minimum floor."""
    stepped = (int(confidence // CONFIDENCE_STEP) * CONFIDENCE_STEP) / 100
    return max(CONFIDENCE_FLOOR, stepped)


def quantized_confidence_percent(confidence_a: float, confidence_b: float) -> int:
    """Weighted, floor-quantized confidence as an integer percent (min 10)."""
    weighted = weighted_confidence(confidence_a, confidence_b)
    stepped = int(weighted // CONFIDENCE_STEP) * int(CONFIDENCE_STEP)
    return max(int(CONFIDENCE_STEP), stepped)


def final_similarity(
    base: float,
    confidence_a: float,
    confidence_b: float,
) -> int:
    """``round(S_base × F_conf)`` using the weighted, quantized confidence.

    The factor is applied as an integer percent (``base * pct / 100``) so the
    result is not skewed by binary ``0.7``/``0.3`` representation error.
    """
    percent = quantized_confidence_percent(confidence_a, confidence_b)
    return int(round(base * percent / 100))


# ---------------------------------------------------------------------------
# Per-Game resolved inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimilarityGame:
    """One Game's similarity inputs, resolved from persisted state.

    ``challenge``/``reward`` are the published current READY unified integer
    profiles (``None`` when unpublished).  ``aesthetic`` is the canonical pair
    resolved from the Game's questionnaire votes; ``confidence`` is that Game's
    calibrated confidence (an integer percent).
    """

    game_id: int
    challenge: ProfileVector | None
    reward: ProfileVector | None
    aesthetic: AestheticLabel
    confidence: float
    snapshot_calculated_at: datetime | None = None


@dataclass(frozen=True)
class SimilarityRunReport:
    """Summary of one engine invocation."""

    delta: bool
    games_considered: int
    changed_games: int
    pairs_written: int


@dataclass(frozen=True)
class SimilarGame:
    """One public similar-Game read row."""

    slug: str
    name: str
    capsule_url: str
    score: int


def pair_similarity(source: SimilarityGame, target: SimilarityGame) -> int:
    """Final directed similarity for the ordered ``(source, target)`` pair."""
    base = base_similarity(
        challenge_a=source.challenge,
        challenge_b=target.challenge,
        reward_a=source.reward,
        reward_b=target.reward,
        aesthetic_a=source.aesthetic,
        aesthetic_b=target.aesthetic,
    )
    return final_similarity(base, source.confidence, target.confidence)


# ---------------------------------------------------------------------------
# DB engine (lazy imports keep the pure math importable without Django)
# ---------------------------------------------------------------------------


def _load_similarity_games() -> dict[int, SimilarityGame]:
    """Resolve every publicly-listable Game with a published READY snapshot.

    The canonical aesthetic pair comes from the Game's questionnaire votes
    aggregated through :func:`resolve_aesthetic_consensus`; when a Game has no
    questionnaire votes it falls back to its stored ``Game.aesthetic`` primary
    with no secondary.  An unparseable/absent pair simply scores 0 on the
    aesthetic term downstream.
    """
    from classifications.calculations.results import READY
    from classifications.models import ClassificationSnapshot, QuestionnaireResult
    from classifications.services.aesthetic_consensus import (
        resolve_aesthetic_consensus,
    )

    from games.models import ContentType, ListingStatus

    snapshots = list(
        ClassificationSnapshot.objects.filter(
            is_current=True,
            status=READY,
            game__content_type=ContentType.GAME,
            game__listing_status=ListingStatus.PUBLISHED,
        ).select_related("game")
    )
    if not snapshots:
        return {}

    game_ids = [
        snapshot.game_id  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
        for snapshot in snapshots
    ]
    votes: dict[int, list[tuple[str, str | None]]] = {gid: [] for gid in game_ids}
    vote_rows = QuestionnaireResult.objects.filter(game_id__in=game_ids).values_list(
        "game_id", "dominant_aesthetic", "secondary_aesthetic"
    )
    for game_id, primary, secondary in vote_rows:
        votes.setdefault(game_id, []).append((primary, secondary))

    games: dict[int, SimilarityGame] = {}
    for snapshot in snapshots:
        game_id = snapshot.game_id  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
        game = snapshot.game
        base_confidence = (
            float(snapshot.confidence_final)
            if snapshot.confidence_final is not None
            else 100.0
        )
        game_votes = votes.get(game_id) or []
        if game_votes:
            consensus = resolve_aesthetic_consensus(
                game_votes, base_confidence=base_confidence
            )
            aesthetic = AestheticLabel(consensus.primary, consensus.secondary)
            confidence = float(consensus.confidence)
        else:
            aesthetic = AestheticLabel(game.aesthetic, None)
            confidence = base_confidence

        games[game_id] = SimilarityGame(
            game_id=game_id,
            challenge=ProfileVector.from_unified(snapshot.unified_integer_challenge),
            reward=ProfileVector.from_unified(snapshot.unified_integer_reward),
            aesthetic=aesthetic,
            confidence=confidence,
            snapshot_calculated_at=snapshot.calculated_at,
        )
    return games


def _changed_game_ids(
    games: dict[int, SimilarityGame], rows: dict[int, Game]
) -> set[int]:
    """Games whose snapshot is newer than their last similarity generation."""
    changed: set[int] = set()
    for game_id, info in games.items():
        game = rows.get(game_id)
        if game is None:
            continue
        last = game.similarity_calculated_at
        if last is None or (
            info.snapshot_calculated_at is not None
            and info.snapshot_calculated_at > last
        ):
            changed.add(game_id)
    return changed


def run_similarity_engine(*, delta: bool = False) -> SimilarityRunReport:
    """Recompute and persist directed similarity rows.

    ``delta=False`` recomputes every ordered pair among publicly-listable Games
    with published READY snapshots.  ``delta=True`` only recomputes pairs that
    touch a changed Game (its snapshot newer than ``similarity_calculated_at``),
    in both directions.  Canonical ``Game.aesthetic`` primaries resolved from
    questionnaire votes are synced as a side effect.
    """
    from django.db import transaction
    from django.utils import timezone

    from games.models import Game, GameSimilarity

    games = _load_similarity_games()
    if not games:
        return SimilarityRunReport(
            delta=delta, games_considered=0, changed_games=0, pairs_written=0
        )

    rows: dict[int, Game] = {
        game.pk: game for game in Game.objects.filter(pk__in=games)
    }
    now = timezone.now()

    # Sync the canonical primary aesthetic resolved from questionnaire votes.
    aesthetic_updates: list[Game] = []
    for game_id, info in games.items():
        primary = info.aesthetic.primary
        game = rows.get(game_id)
        if primary and game is not None and game.aesthetic != primary:
            game.aesthetic = primary
            aesthetic_updates.append(game)
    if aesthetic_updates:
        Game.objects.bulk_update(aesthetic_updates, ["aesthetic"])

    if delta:
        changed = _changed_game_ids(games, rows)
    else:
        changed = set(games)

    ids = list(games)
    pair_ids: set[tuple[int, int]] = set()
    if delta:
        for game_id in changed:
            for other in ids:
                if other == game_id:
                    continue
                pair_ids.add((game_id, other))
                pair_ids.add((other, game_id))
    else:
        for source_id in ids:
            for target_id in ids:
                if source_id != target_id:
                    pair_ids.add((source_id, target_id))

    similarity_rows = [
        GameSimilarity(
            source_game_id=source_id,
            target_game_id=target_id,
            score=pair_similarity(games[source_id], games[target_id]),
            calculated_at=now,
        )
        for source_id, target_id in pair_ids
    ]

    with transaction.atomic():
        if similarity_rows:
            GameSimilarity.objects.bulk_create(
                similarity_rows,
                update_conflicts=True,
                unique_fields=["source_game", "target_game"],
                update_fields=["score", "calculated_at"],
                batch_size=1000,
            )
        if changed:
            Game.objects.filter(pk__in=changed).update(similarity_calculated_at=now)

    return SimilarityRunReport(
        delta=delta,
        games_considered=len(games),
        changed_games=len(changed),
        pairs_written=len(similarity_rows),
    )


def get_similar_games(game, limit: int = 6) -> list[SimilarGame]:
    """Return the top similar publicly-listable Games for *game*.

    Reads persisted :class:`GameSimilarity` rows only — never recomputes.  Still
    filters the target for current public eligibility so a Game unpublished
    since the last engine run cannot leak into the list.
    """
    from games.models import ContentType, GameSimilarity, ListingStatus

    queryset = (
        GameSimilarity.objects.filter(
            source_game=game,
            target_game__content_type=ContentType.GAME,
            target_game__listing_status=ListingStatus.PUBLISHED,
        )
        .select_related("target_game")
        .order_by("-score", "target_game__name", "target_game__id")[:limit]
    )
    return [
        SimilarGame(
            slug=row.target_game.slug,
            name=row.target_game.name,
            capsule_url=row.target_game.display_capsule_url,
            score=row.score,
        )
        for row in queryset
    ]


__all__ = [
    "AestheticLabel",
    "ProfileVector",
    "SimilarGame",
    "SimilarityGame",
    "SimilarityRunReport",
    "aesthetic_similarity",
    "base_similarity",
    "challenge_similarity",
    "final_similarity",
    "get_similar_games",
    "pair_similarity",
    "quantize_confidence",
    "quantized_confidence_percent",
    "reward_similarity",
    "run_similarity_engine",
    "weighted_confidence",
]
