"""
Delta-based global recalculation engine — SBGC-174 (Epic SBGC-171).

Identifies published Games whose submissions changed since their most recent
completed calculation, then recalculates only those Games through the canonical
engine, finally emailing the triggering admin a completion report.

Adapted to this repository's persistence model: the "last completed run" for a
Game is its latest :class:`ClassificationSnapshot.calculated_at` (there is no
separate ``ClassificationRun`` table); the effective submission timestamp is
``updated_at`` on either :class:`EditorialClassification` or
:class:`UserGameScoreSubmission`.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Max
from django.utils import timezone
from games.models import Game

from classifications.calculations.constants import MASTER_VERSION
from classifications.models import (
    CalculationEpoch,
    ClassificationSnapshot,
    EditorialClassification,
    UserGameScoreSubmission,
)
from classifications.roles import EditorialRole
from classifications.services.calculations import run_game_calculation
from classifications.services.submissions import (
    EditorialRoleError,
    resolve_editorial_role,
)

logger = logging.getLogger(__name__)

_MIN_DATETIME = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class DeltaRunSummary:
    """Outcome of one global delta recalculation pass."""

    total_games_checked: int
    games_recalculated: list[str]
    duration_seconds: float
    triggered_by_username: str
    triggered_by_email: str


def can_trigger_delta_recalculation(user) -> bool:
    """Return True for Superusers and Moderators only.

    Uses the repository's authoritative editorial-role resolver (Superuser /
    Moderator / Community Leader) rather than a raw group-name match.  A
    conflicting group membership resolves to ``False``.
    """
    if getattr(user, "is_superuser", False):
        return True
    try:
        role = resolve_editorial_role(user)
    except EditorialRoleError:
        return False
    return role == EditorialRole.MODERATOR


def dispatch_delta_recalculation(user) -> None:
    """Start the CPU-heavy recalculation on a daemon thread (never blocks HTTP)."""
    threading.Thread(
        target=execute_delta_recalculation,
        args=(user,),
        daemon=True,
    ).start()


def find_stale_game_ids() -> list[int]:
    """Return published Game ids that need a recalculation.

    A Game is stale when it has no completed calculation, or when the latest
    editorial/community submission ``updated_at`` is strictly after its latest
    snapshot ``calculated_at``.
    """
    game_ids = list(Game.objects.publicly_listable().values_list("id", flat=True))
    if not game_ids:
        return []

    latest_snapshot = _max_by_game(ClassificationSnapshot, game_ids, "calculated_at")
    latest_editorial = _max_by_game(EditorialClassification, game_ids, "updated_at")
    latest_community = _max_by_game(UserGameScoreSubmission, game_ids, "updated_at")

    stale: set[int] = set()
    for game_id in game_ids:
        cutoff = latest_snapshot.get(game_id)
        has_editorial = game_id in latest_editorial
        has_community = game_id in latest_community
        if cutoff is None:
            # Never calculated: stale only when it actually has submissions.
            if has_editorial or has_community:
                stale.add(game_id)
            continue
        if latest_editorial.get(game_id, _MIN_DATETIME) > cutoff:
            stale.add(game_id)
            continue
        if latest_community.get(game_id, _MIN_DATETIME) > cutoff:
            stale.add(game_id)
    return sorted(stale)


def execute_delta_recalculation(admin_user) -> DeltaRunSummary:
    """Recalculate every stale Game and email the triggering admin a report."""
    started = timezone.now()
    total_checked = Game.objects.publicly_listable().count()
    stale_ids = find_stale_game_ids()

    cutoff = timezone.now()
    epoch = CalculationEpoch.objects.create(
        epoch_id=f"delta-{cutoff:%Y%m%d-%H%M%S-%f}",
        cutoff_at=cutoff,
        master_version=MASTER_VERSION,
        status=CalculationEpoch.Status.RUNNING,
    )

    recalculated: list[str] = []
    failed = 0
    for game_id in stale_ids:
        try:
            game = Game.objects.get(pk=game_id)
        except Game.DoesNotExist:
            continue
        try:
            run_game_calculation(
                game=game,
                epoch=epoch,
                attempt_number=1,
                cutoff_at=cutoff,
            )
        except Exception as exc:  # noqa: BLE001 — a single game must not abort the batch
            failed += 1
            logger.warning(
                "Delta recalculation failed for game %s: %s",
                game_id,
                exc,
            )
            continue
        recalculated.append(game.name)

    epoch.status = CalculationEpoch.Status.COMPLETED
    epoch.games_attempted = len(stale_ids)
    epoch.games_succeeded = len(recalculated)
    epoch.games_failed = failed
    epoch.completed_at = timezone.now()
    epoch.save(
        update_fields=[
            "status",
            "games_attempted",
            "games_succeeded",
            "games_failed",
            "completed_at",
        ]
    )

    duration = (timezone.now() - started).total_seconds()
    summary = DeltaRunSummary(
        total_games_checked=total_checked,
        games_recalculated=recalculated,
        duration_seconds=duration,
        triggered_by_username=admin_user.username,
        triggered_by_email=admin_user.email or "",
    )

    _send_completion_report(summary)
    return summary


def _max_by_game(model, game_ids: list[int], field: str) -> dict[int, datetime]:
    rows = (
        model.objects.filter(game_id__in=game_ids)
        .values("game_id")
        .annotate(latest=Max(field))
    )
    return {row["game_id"]: row["latest"] for row in rows}


def _send_completion_report(summary: DeltaRunSummary) -> None:
    email = summary.triggered_by_email
    if not email:
        return
    games = (
        "\n".join(f" - {name}" for name in summary.games_recalculated) or " - (none)"
    )
    send_mail(
        subject="[MyGameDNA] Score Delta Recalculation Complete",
        message=(
            f"Hello {summary.triggered_by_username},\n\n"
            f"Global score recalculation finished in "
            f"{summary.duration_seconds:.2f} seconds.\n"
            f"Total games evaluated: {summary.total_games_checked}\n"
            f"Games recalculated ({len(summary.games_recalculated)}):\n"
            f"{games}\n\n"
            "Regards,\nMyGameDNA Core Engine"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,
    )


__all__ = [
    "DeltaRunSummary",
    "can_trigger_delta_recalculation",
    "dispatch_delta_recalculation",
    "execute_delta_recalculation",
    "find_stale_game_ids",
]
