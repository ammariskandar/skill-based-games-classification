"""
Community score-submission ingestion — SBGC-216.

Implements the temporal duplicate/supersession state machine for game score
submissions:

* Chained duplicate rejection  — an identical replay within 2 minutes of the
  previous attempt returns the existing row with ``is_duplicate=True``.
* Rapid revision — a different payload within 2 minutes overwrites the latest
  row in place.
* 15-day window update — any submission within 15 days of the latest row's
  ``created_at`` supersedes it in place.
* 15-day branching — a submission >= 15 days after ``created_at`` inserts a new
  standalone row.

Attempt metadata (used to reject duplicates without persisting rejected rows)
is buffered in Django's cache under ``sub_attempt:{user}:{game}`` with a
10-minute sliding TTL.

Users who resolve to an editorial role (Superuser / Moderator / Community
Leader) are routed to the editorial classification flow instead — zero rows are
ever written to ``UserGameScoreSubmission`` for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from games.models import Game

from classifications.models import (
    EditorialClassification,
    QuestionnaireClassification,
    UserGameScoreSubmission,
)
from classifications.questionnaire.domain import AestheticCategory
from classifications.roles import EditorialRole
from classifications.services.submissions import (
    EditorialRoleError,
    EditorialSubmissionError,
    ScoreDistribution,
    create_submission,
    resolve_editorial_role,
    update_submission,
)

CACHE_ATTEMPT_KEY = "sub_attempt:{user_id}:{game_id}"
CACHE_TTL_SECONDS = 600  # 10-minute sliding window

TWO_MINUTES = timedelta(minutes=2)
FIFTEEN_DAYS = timedelta(days=15)

#: Canonical stored aesthetic values (SBGC-172), used for normalization.
TRUE_AESTHETIC_VALUES: frozenset[str] = frozenset(
    member.value
    for member in (
        AestheticCategory.SENSORY,
        AestheticCategory.FANTASY,
        AestheticCategory.NARRATIVE,
        AestheticCategory.CHALLENGE,
    )
)


@dataclass(frozen=True)
class IngestionResult:
    """Outcome of one score-submission ingestion."""

    submission: UserGameScoreSubmission | EditorialClassification
    is_duplicate: bool
    is_updated: bool
    is_created: bool
    status_code: int


def is_editorial_submitter(user) -> bool:
    """Return True when *user* resolves to an editorial (non-community) role.

    Superusers, Moderators, and Community Leaders all submit through the
    editorial flow so their submissions retain their weighted editorial
    provenance.  A group-flag conflict (user in both a Moderator and Community
    Leader group) falls back to the community path rather than erroring.
    """
    try:
        role = resolve_editorial_role(user)
    except EditorialRoleError:
        return False
    return role != EditorialRole.COMMUNITY


def extract_score_dict(payload: dict[str, Any]) -> dict[str, int]:
    """Flatten an API payload into model-field keyed integers."""
    return {
        "challenge_micro": payload["challenge"]["micro"],
        "challenge_mystiko": payload["challenge"]["mystiko"],
        "challenge_macro": payload["challenge"]["macro"],
        "reward_micro": payload["reward"]["micro"],
        "reward_mystiko": payload["reward"]["mystiko"],
        "reward_macro": payload["reward"]["macro"],
    }


def normalize_aesthetic(value: object) -> str | None:
    """Return the canonical uppercase aesthetic for *value*, or ``None``.

    Accepts any casing (the frontend picker and legacy clients may send lower
    case) and ignores values outside the four-aesthetic taxonomy.
    """
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized if normalized in TRUE_AESTHETIC_VALUES else None


def extract_aesthetic(payload: dict[str, Any]) -> str | None:
    """Normalize the optional primary aesthetic from *payload*.

    Aesthetic is captured alongside the scores and never participates in score
    math or sum-to-100 validation.
    """
    return normalize_aesthetic(payload.get("aesthetic"))


def extract_secondary_aesthetic(payload: dict[str, Any]) -> str | None:
    """Normalize the optional secondary aesthetic from *payload*."""
    return normalize_aesthetic(payload.get("secondary_aesthetic"))


def scores_match_record(
    scores: dict[str, int],
    record: UserGameScoreSubmission | EditorialClassification | None,
) -> bool:
    if record is None:
        return False
    return all(getattr(record, key) == value for key, value in scores.items())


def _apply_scores(record, scores: dict[str, int]) -> None:
    for field, value in scores.items():
        setattr(record, field, value)


def _retire_questionnaire_source(record: UserGameScoreSubmission) -> bool:
    """Flip a questionnaire-origin community row to a manual row.

    Returns ``True`` when the row was questionnaire-origin.  The
    ``questionnaire_result`` provenance FK is cleared so ``source`` and the FK
    stay consistent; the immutable ``QuestionnaireResult`` and the ledger's
    ``latest_result`` still preserve the audit trail.
    """
    if record.source != UserGameScoreSubmission.SubmissionSource.QUESTIONNAIRE:
        return False
    record.source = UserGameScoreSubmission.SubmissionSource.MANUAL
    record.questionnaire_result = None
    return True


def _supersede_questionnaire_ledger(user, game: Game) -> None:
    """Mark the viewer's active questionnaire as superseded by a manual score.

    Only an ``ACTIVE_IN_CALCULATION`` ledger row is transitioned; archived or
    already-superseded states are left untouched.
    """
    QuestionnaireClassification.objects.filter(
        user=user,
        game=game,
        status=QuestionnaireClassification.PrecedenceStatus.ACTIVE_IN_CALCULATION,
    ).update(status=QuestionnaireClassification.PrecedenceStatus.SUPERSEDED_BY_MANUAL)


def _absorb_questionnaire_row(
    user, game: Game, record: UserGameScoreSubmission
) -> None:
    """Retire a replaced questionnaire row and its active ledger entry."""
    if _retire_questionnaire_source(record):
        _supersede_questionnaire_ledger(user, game)


def ingest_score_submission(
    *,
    user,
    game: Game,
    payload: dict[str, Any],
    aesthetic: str | None = None,
    secondary_aesthetic: str | None = None,
) -> IngestionResult:
    """Ingest *payload* for one (user, game), returning the temporal outcome.

    ``aesthetic`` / ``secondary_aesthetic`` default to the payload's keys
    (normalized); pass them explicitly to override, e.g. from a caller that has
    already validated them.
    """
    if user is None or user.pk is None:
        raise TypeError("user must be a saved user.")
    if not isinstance(game, Game) or game.pk is None:
        raise TypeError("game must be a saved Game instance.")

    new_scores = extract_score_dict(payload)
    if aesthetic is None:
        aesthetic = extract_aesthetic(payload)
    if secondary_aesthetic is None:
        secondary_aesthetic = extract_secondary_aesthetic(payload)

    # 1. Staff / editorial routing gate.
    if is_editorial_submitter(user):
        return _route_to_editorial_submission(
            user, game, new_scores, aesthetic, secondary_aesthetic
        )

    return _ingest_community_submission(
        user, game, new_scores, aesthetic, secondary_aesthetic
    )


# ---------------------------------------------------------------------------
# Community pipeline
# ---------------------------------------------------------------------------


def _ingest_community_submission(
    user,
    game: Game,
    scores: dict[str, int],
    aesthetic: str | None = None,
    secondary_aesthetic: str | None = None,
):
    cache_key = CACHE_ATTEMPT_KEY.format(user_id=user.pk, game_id=game.pk)
    now = timezone.now()

    with transaction.atomic():
        latest = (
            UserGameScoreSubmission.objects.select_for_update()
            .filter(user=user, game=game)
            .order_by("-created_at", "-id")
            .first()
        )

        last_attempt = cache.get(cache_key)
        if latest is not None and last_attempt is not None:
            time_since_last_attempt = now - last_attempt["timestamp"]
            if time_since_last_attempt < TWO_MINUTES:
                _mark_attempt(cache_key, now, scores)
                if scores_match_record(scores, latest):
                    # Identical replay → chained duplicate, return existing row.
                    return IngestionResult(
                        submission=latest,
                        is_duplicate=True,
                        is_updated=False,
                        is_created=False,
                        status_code=200,
                    )
                # Rapid revision → overwrite the latest row in place.
                _apply_scores(latest, scores)
                if aesthetic is not None:
                    latest.aesthetic = aesthetic
                if secondary_aesthetic is not None:
                    latest.secondary_aesthetic = secondary_aesthetic
                _absorb_questionnaire_row(user, game, latest)
                latest.save()
                return IngestionResult(
                    submission=latest,
                    is_duplicate=False,
                    is_updated=True,
                    is_created=False,
                    status_code=200,
                )

        # 2. First submission ever for this (user, game).
        if latest is None:
            record = UserGameScoreSubmission.objects.create(
                user=user,
                game=game,
                aesthetic=aesthetic,
                secondary_aesthetic=secondary_aesthetic,
                **scores,
            )
            _mark_attempt(cache_key, now, scores)
            return IngestionResult(
                submission=record,
                is_duplicate=False,
                is_updated=False,
                is_created=True,
                status_code=201,
            )

        # 3. Temporal evaluation anchored to the latest row's created_at.
        if now - latest.created_at < FIFTEEN_DAYS:
            _apply_scores(latest, scores)
            if aesthetic is not None:
                latest.aesthetic = aesthetic
            if secondary_aesthetic is not None:
                latest.secondary_aesthetic = secondary_aesthetic
            _absorb_questionnaire_row(user, game, latest)
            latest.save()
            _mark_attempt(cache_key, now, scores)
            return IngestionResult(
                submission=latest,
                is_duplicate=False,
                is_updated=True,
                is_created=False,
                status_code=200,
            )

        # 4. >= 15 days → branch into a new standalone row.
        record = UserGameScoreSubmission.objects.create(
            user=user,
            game=game,
            aesthetic=aesthetic,
            secondary_aesthetic=secondary_aesthetic,
            **scores,
        )
        # The branched-from row is retained as history, but an active
        # questionnaire ledger entry is superseded by the new manual score.
        if latest.source == UserGameScoreSubmission.SubmissionSource.QUESTIONNAIRE:
            _supersede_questionnaire_ledger(user, game)
        _mark_attempt(cache_key, now, scores)
        return IngestionResult(
            submission=record,
            is_duplicate=False,
            is_updated=False,
            is_created=True,
            status_code=201,
        )


def _mark_attempt(cache_key: str, timestamp, scores: dict[str, int]) -> None:
    cache.set(
        cache_key,
        {"timestamp": timestamp, "scores": scores},
        timeout=CACHE_TTL_SECONDS,
    )


# ---------------------------------------------------------------------------
# Editorial routing
# ---------------------------------------------------------------------------


def _route_to_editorial_submission(
    user,
    game: Game,
    scores: dict[str, int],
    aesthetic: str | None = None,
    secondary_aesthetic: str | None = None,
):
    challenge = ScoreDistribution(
        micro=scores["challenge_micro"],
        mystiko=scores["challenge_mystiko"],
        macro=scores["challenge_macro"],
    )
    reward = ScoreDistribution(
        micro=scores["reward_micro"],
        mystiko=scores["reward_mystiko"],
        macro=scores["reward_macro"],
    )

    with transaction.atomic():
        existing = (
            EditorialClassification.objects.select_for_update()
            .filter(game=game, submitted_by=user)
            .first()
        )
        if existing is not None:
            submission = update_submission(
                existing,
                updated_by=user,
                challenge=challenge,
                reward=reward,
                aesthetic=aesthetic,
                secondary_aesthetic=secondary_aesthetic,
            )
            return IngestionResult(
                submission=submission,
                is_duplicate=False,
                is_updated=True,
                is_created=False,
                status_code=200,
            )

        try:
            submission = create_submission(
                game=game,
                submitted_by=user,
                updated_by=user,
                challenge=challenge,
                reward=reward,
                aesthetic=aesthetic,
                secondary_aesthetic=secondary_aesthetic,
            )
        except EditorialSubmissionError:
            # Lost a concurrent create race → supersede the winner in place.
            submission = update_submission(
                EditorialClassification.objects.get(game=game, submitted_by=user),
                updated_by=user,
                challenge=challenge,
                reward=reward,
                aesthetic=aesthetic,
                secondary_aesthetic=secondary_aesthetic,
            )
            return IngestionResult(
                submission=submission,
                is_duplicate=False,
                is_updated=True,
                is_created=False,
                status_code=200,
            )

        return IngestionResult(
            submission=submission,
            is_duplicate=False,
            is_updated=False,
            is_created=True,
            status_code=201,
        )


__all__ = [
    "CACHE_ATTEMPT_KEY",
    "FIFTEEN_DAYS",
    "IngestionResult",
    "TRUE_AESTHETIC_VALUES",
    "TWO_MINUTES",
    "extract_aesthetic",
    "extract_score_dict",
    "extract_secondary_aesthetic",
    "ingest_score_submission",
    "is_editorial_submitter",
    "normalize_aesthetic",
    "scores_match_record",
]
