"""
PostgreSQL concurrency verification for the scheduled Steam refresh run — SBGC-183.

Proves the current-run acquisition path behaves correctly when two
invocations race, and that a stale ``running`` run cannot permanently block a
future run.  The single-active guarantee is the partial unique index
``steam_refresh_run_single_active_uniq`` plus the ``IntegrityError`` recovery
in ``ScheduledSteamRefreshService._establish_run``.

Skips on SQLite — the default lane cannot prove concurrent uniqueness.
"""

from __future__ import annotations

import threading
from datetime import timedelta
from unittest import SkipTest, mock

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone

from games.models import Game, SourceType, SteamRefreshRun
from games.services.imports.steam import (
    SteamGameRefreshResult,
    SteamGameRefreshStatus,
)
from games.services.scheduled_refresh import ScheduledSteamRefreshService


class _FakeRefresh:
    """Counts refresh calls and always returns UNCHANGED (success)."""

    def __init__(self):
        self.calls: list[int] = []

    def refresh(self, game):
        self.calls.append(game.pk)
        return SteamGameRefreshResult(
            status=SteamGameRefreshStatus.UNCHANGED, game_id=game.pk
        )


class _FakeWait:
    def __call__(self, seconds: float) -> None:
        pass


class ScheduledRefreshConcurrencyTests(TransactionTestCase):
    """Concurrency and stale-run behavior on a real PostgreSQL instance."""

    @classmethod
    def setUpClass(cls):
        from django.db import connection

        if connection.vendor != "postgresql":
            raise SkipTest(
                "Scheduled-refresh concurrency tests require PostgreSQL. "
                "Use --settings=config.settings.postgresql_test."
            )
        super().setUpClass()

    def _steam(self, name: str, external_id: str) -> Game:
        return Game.objects.create(
            source_type=SourceType.STEAM,
            external_id=external_id,
            name=name,
            slug=name.lower().replace(" ", "-"),
        )

    # ------------------------------------------------------------------
    # Scenario A — simultaneous acquisition
    # ------------------------------------------------------------------

    def test_simultaneous_establishment_single_active_run(self):
        game = self._steam("Race Game", "999111")

        # Force both contenders to reach the INSERT at the same moment.
        barrier = threading.Barrier(2)
        original_create = SteamRefreshRun.objects.create

        def synchronized_create(*args, **kwargs):
            barrier.wait(timeout=15)
            return original_create(*args, **kwargs)

        fake = _FakeRefresh()
        results: list = []
        errors: list[BaseException] = []

        def worker() -> None:
            try:
                service = ScheduledSteamRefreshService(fake, wait=_FakeWait())
                results.append(service.run(scheduled_at=timezone.now()))
            except BaseException as exc:  # noqa: BLE001 — captured for assertion
                errors.append(exc)
            finally:
                connections.close_all()

        try:
            with mock.patch.object(
                SteamRefreshRun.objects, "create", synchronized_create
            ):
                t1 = threading.Thread(target=worker)
                t2 = threading.Thread(target=worker)
                t1.start()
                t2.start()
                t1.join(timeout=30)
                t2.join(timeout=30)
        finally:
            connections.close_all()

        self.assertFalse(t1.is_alive(), "first contender did not finish")
        self.assertFalse(t2.is_alive(), "second contender did not finish")
        self.assertEqual([], errors)

        runs = [r for r in results if r is not None]
        self.assertEqual(1, len(runs), "exactly one contender must win")
        self.assertEqual(1, SteamRefreshRun.objects.count())
        run = SteamRefreshRun.objects.get()
        self.assertEqual(run.status, SteamRefreshRun.Status.COMPLETED)
        self.assertEqual(run.selected_count, 1)
        self.assertEqual(run.successful_count, 1)
        self.assertEqual(run.failed_count, 0)
        # The loser never refreshed the population.
        self.assertEqual(fake.calls, [game.pk])

    # ------------------------------------------------------------------
    # Scenario B — genuine active run blocks; audit preserved
    # ------------------------------------------------------------------

    def test_genuine_active_run_blocks_and_preserves_previous_audit(self):
        previous = SteamRefreshRun.objects.create(
            scheduled_at=timezone.now() - timedelta(days=1),
            status=SteamRefreshRun.Status.COMPLETED,
        )
        active = SteamRefreshRun.objects.create(
            scheduled_at=timezone.now(),
            status=SteamRefreshRun.Status.RUNNING,
        )

        fake = _FakeRefresh()
        service = ScheduledSteamRefreshService(fake, wait=_FakeWait())
        result = service.run(scheduled_at=timezone.now())

        self.assertIsNone(result)
        self.assertEqual(fake.calls, [])
        # Both the retained previous audit and the active run survive.
        self.assertTrue(SteamRefreshRun.objects.filter(pk=previous.pk).exists())
        self.assertTrue(SteamRefreshRun.objects.filter(pk=active.pk).exists())
        self.assertEqual(
            SteamRefreshRun.objects.filter(
                status=SteamRefreshRun.Status.RUNNING
            ).count(),
            1,
        )

    # ------------------------------------------------------------------
    # Scenario C — a later legitimate run after normal finalization
    # ------------------------------------------------------------------

    def test_subsequent_run_after_finalization(self):
        game = self._steam("Next Run", "999222")
        SteamRefreshRun.objects.create(
            scheduled_at=timezone.now() - timedelta(days=1),
            status=SteamRefreshRun.Status.COMPLETED,
        )

        fake = _FakeRefresh()
        service = ScheduledSteamRefreshService(fake, wait=_FakeWait())
        run = service.run(scheduled_at=timezone.now())

        assert run is not None
        self.assertEqual(run.status, SteamRefreshRun.Status.COMPLETED)
        self.assertEqual(SteamRefreshRun.objects.count(), 1)
        self.assertEqual(SteamRefreshRun.objects.get().pk, run.pk)
        self.assertEqual(fake.calls, [game.pk])

    # ------------------------------------------------------------------
    # Stale previous-day running run recovery
    # ------------------------------------------------------------------

    def test_stale_previous_day_running_run_recovered(self):
        game = self._steam("Stale Recovery", "999333")
        stale = SteamRefreshRun.objects.create(
            scheduled_at=timezone.now() - timedelta(days=1),
            status=SteamRefreshRun.Status.RUNNING,
        )

        fake = _FakeRefresh()
        service = ScheduledSteamRefreshService(fake, wait=_FakeWait())
        run = service.run(scheduled_at=timezone.now())

        assert run is not None
        self.assertEqual(run.status, SteamRefreshRun.Status.COMPLETED)
        self.assertEqual(SteamRefreshRun.objects.count(), 1)
        self.assertEqual(SteamRefreshRun.objects.get().pk, run.pk)
        self.assertFalse(SteamRefreshRun.objects.filter(pk=stale.pk).exists())
        self.assertEqual(fake.calls, [game.pk])
