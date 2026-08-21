"""
Scheduled Steam metadata refresh orchestration — SBGC-183.

Owns the daily run: Steam-only selection, per-Game retry budget, failure-only
retries, current-run audit, concurrency protection, and the final operator
alert.  Actual Game refresh is delegated to ``SteamGameRefreshService`` — this
module never talks to ``SteamClient`` directly.
"""

from __future__ import annotations

import logging
import time as _time
from collections.abc import Callable
from typing import Protocol

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from games.models import (
    Game,
    SourceType,
    SteamRefreshGameAttempt,
    SteamRefreshRun,
)
from games.services.imports.steam import (
    SteamGameRefreshResult,
    SteamGameRefreshStatus,
    SteamRefreshError,
)
from games.services.steam.errors import SteamError

logger = logging.getLogger(__name__)

# Frozen retry timing: waits before attempts 2, 3, and 4.
WAIT_SECONDS = (360, 360, 10800)

_Outcome = SteamRefreshGameAttempt.Outcome
_RunStatus = SteamRefreshRun.Status

_SafeWait = Callable[[float], None]


class RefreshService(Protocol):
    """Structural interface for the Steam refresh service the scheduler drives.

    The scheduler only needs ``refresh(game) -> SteamGameRefreshResult``, so it
    depends on this narrow seam rather than the concrete
    ``SteamGameRefreshService``.  This keeps orchestration testable with a fake
    without any cast or subclass.
    """

    def refresh(self, game: Game) -> SteamGameRefreshResult: ...


class ScheduledSteamRefreshService:
    """Run one daily scheduled Steam metadata refresh."""

    def __init__(
        self,
        refresh_service: RefreshService,
        *,
        wait: _SafeWait = _time.sleep,
    ) -> None:
        self._refresh_service = refresh_service
        self._wait = wait

    def run(self, scheduled_at=None) -> SteamRefreshRun | None:
        """Establish today's run, run up to four attempts, then finalize.

        Returns ``None`` when another run is already active (clean skip), so a
        duplicate or overlapping invocation never processes the population
        twice.
        """
        scheduled_at = scheduled_at or timezone.now()
        run = self._establish_run(scheduled_at)
        if run is None:
            return None

        games = list(Game.objects.filter(source_type=SourceType.STEAM).order_by("id"))
        run.selected_count = len(games)
        run.save(update_fields=["selected_count"])

        pending = games
        successful = 0
        for attempt_number in range(1, 5):
            if attempt_number > 1:
                self._wait(WAIT_SECONDS[attempt_number - 2])

            next_pending: list[Game] = []
            for game in pending:
                if self._refresh_one(run, game, attempt_number) is _Outcome.SUCCESS:
                    successful += 1
                else:
                    next_pending.append(game)
            pending = next_pending
            if not pending:
                break

        failed = len(pending)
        run.successful_count = successful
        run.failed_count = failed
        run.status = _RunStatus.FAILED if failed else _RunStatus.COMPLETED
        run.finished_at = timezone.now()
        run.save(
            update_fields=[
                "successful_count",
                "failed_count",
                "status",
                "finished_at",
            ]
        )

        # Persist the final run state before attempting notification, so a
        # notification failure never loses the audit.
        if failed:
            self._send_final_alert(run, pending)

        return run

    # -- run lifecycle ---------------------------------------------------------

    def _establish_run(self, scheduled_at) -> SteamRefreshRun | None:
        """Create today's run and retire the previous run atomically."""
        with transaction.atomic():
            if SteamRefreshRun.objects.filter(status=_RunStatus.RUNNING).exists():
                return None
            try:
                run = SteamRefreshRun.objects.create(
                    scheduled_at=scheduled_at,
                    status=_RunStatus.RUNNING,
                )
            except IntegrityError:
                # Another invocation created a run concurrently.
                return None
            # Only the new run is retained; previous runs (and their attempts)
            # are removed.  The transaction ensures a failed creation never
            # erases yesterday's audit.
            SteamRefreshRun.objects.exclude(pk=run.pk).delete()
            return run

    # -- per-Game attempt ------------------------------------------------------

    def _refresh_one(self, run, game, attempt_number) -> str:
        try:
            result = self._refresh_service.refresh(game)
        except SteamRefreshError as exc:
            self._record(
                run,
                game,
                attempt_number,
                _Outcome.FAILED,
                "STEAM_REFRESH_ERROR",
                str(exc),
            )
            return _Outcome.FAILED
        except SteamError as exc:
            self._record(
                run, game, attempt_number, _Outcome.FAILED, exc.code, exc.message
            )
            return _Outcome.FAILED
        except Exception as exc:  # noqa: BLE001 — scheduler boundary
            self._record(
                run,
                game,
                attempt_number,
                _Outcome.FAILED,
                "INTERNAL_ERROR",
                _safe_summary(exc),
            )
            return _Outcome.FAILED

        if result.status in (
            SteamGameRefreshStatus.UPDATED,
            SteamGameRefreshStatus.UNCHANGED,
        ):
            self._record(run, game, attempt_number, _Outcome.SUCCESS, "", "")
            return _Outcome.SUCCESS

        # UNAVAILABLE is a retryable attempt, not a scheduler success.
        self._record(run, game, attempt_number, _Outcome.UNAVAILABLE, "", "")
        return _Outcome.UNAVAILABLE

    def _record(self, run, game, attempt_number, outcome, error_code, error_summary):
        SteamRefreshGameAttempt.objects.create(
            run=run,
            game=game,
            attempt_number=attempt_number,
            outcome=outcome,
            error_code=error_code,
            error_summary=error_summary[:255],
        )

    # -- notification ----------------------------------------------------------

    def _send_final_alert(self, run, failed_games) -> None:
        recipients = resolve_refresh_recipients()
        if not recipients:
            logger.warning(
                "Steam refresh run %s finished with failures but no recipients "
                "could be resolved.",
                run.pk,
            )
            return

        subject = f"Steam metadata refresh: {len(failed_games)} game(s) failed"
        body = _build_alert_body(run, failed_games)
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                recipients,
                fail_silently=False,
            )
        except Exception as exc:  # noqa: BLE001 — notification boundary
            logger.error(
                "Steam refresh notification failed for run %s: %s",
                run.pk,
                exc,
            )
            run.alert_sent = False
        else:
            run.alert_sent = True
        run.save(update_fields=["alert_sent"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_summary(exc: Exception) -> str:
    """A short, secret-free error summary (no traceback, no raw payload)."""
    text = str(exc) or exc.__class__.__name__
    return text[:255]


def _is_valid_email(value: str) -> bool:
    try:
        validate_email(value)
    except ValidationError:
        return False
    return True


def resolve_refresh_recipients() -> list[str]:
    """Resolve alert recipients: active Superuser emails, else fallback config."""
    emails: set[str] = set()
    for raw in User.objects.filter(is_superuser=True, is_active=True).values_list(
        "email", flat=True
    ):
        email = (raw or "").strip()
        if email and _is_valid_email(email):
            emails.add(email)

    if emails:
        return sorted(emails)

    fallback = settings.STEAM_REFRESH_FALLBACK_EMAILS or ""
    fallback_emails = {
        email.strip()
        for email in fallback.split(",")
        if email.strip() and _is_valid_email(email.strip())
    }
    return sorted(fallback_emails)


def _build_alert_body(run: SteamRefreshRun, failed_games: list[Game]) -> str:
    lines = [
        "Scheduled Steam metadata refresh — final failure summary.",
        f"Scheduled at: {run.scheduled_at.isoformat()}",
        f"Selected: {run.selected_count}",
        f"Succeeded: {run.successful_count}",
        f"Final failures: {len(failed_games)}",
        "",
        "Failed games:",
    ]
    for game in failed_games:
        lines.append(f"- {game.name} (id={game.pk}, steam:{game.external_id})")
    lines.append("")
    lines.append(f"Final attempt completed at: {run.finished_at.isoformat()}")
    return "\n".join(lines)


__all__ = [
    "ScheduledSteamRefreshService",
    "WAIT_SECONDS",
    "resolve_refresh_recipients",
]
