"""
Concurrent Steam import race verification — SBGC-54.

PostgreSQL-only: two parallel imports of the same App ID must produce
exactly one canonical Game row.  The partial unique index on
``(source_type, external_id)`` is the authority; the loser recovers the
winner's row instead of duplicating it.

Skips on SQLite — the default lane cannot prove concurrent uniqueness.
"""

from __future__ import annotations

import threading
from unittest import SkipTest, mock

from django.db import connections
from django.test import TransactionTestCase

from games.models import Game, SourceType
from games.services.imports.steam import (
    SteamGameImportStatus,
    SteamGamePersistenceService,
)
from games.services.steam.dto import SteamGameImportCandidate


class ConcurrentSteamImportTests(TransactionTestCase):
    """Two racing imports produce one canonical Game row."""

    @classmethod
    def setUpClass(cls):
        from django.db import connection

        if connection.vendor != "postgresql":
            raise SkipTest(
                "Concurrent import tests require PostgreSQL. "
                "Use --settings=config.settings.postgresql_test."
            )
        super().setUpClass()

    def test_parallel_imports_produce_single_canonical_row(self):
        app_id = "999888777"
        candidate = SteamGameImportCandidate(
            app_id=app_id,
            name="Concurrent Import",
            content_type="game",
        )

        # Both threads must pass the pre-create identity check before
        # either inserts — otherwise the test cannot exercise the race.
        barrier = threading.Barrier(2)
        original_create = SteamGamePersistenceService._create_new

        def synchronized_create(self, candidate, app_id):
            barrier.wait(timeout=15)
            return original_create(self, candidate, app_id)

        results: list = []
        errors: list[BaseException] = []

        def worker() -> None:
            try:
                service = SteamGamePersistenceService()
                results.append(service.persist(candidate))
            except BaseException as exc:  # noqa: BLE001 — captured for assertion
                errors.append(exc)
            finally:
                # Django connections are thread-local — each worker must
                # close its own, or the test-DB teardown fails with
                # "database is being accessed by other users".
                connections.close_all()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)

        try:
            with mock.patch.object(
                SteamGamePersistenceService, "_create_new", synchronized_create
            ):
                t1.start()
                t2.start()
                t1.join(timeout=30)
                t2.join(timeout=30)
        finally:
            connections.close_all()

        self.assertFalse(t1.is_alive(), "first import thread did not finish")
        self.assertFalse(t2.is_alive(), "second import thread did not finish")
        self.assertEqual([], errors)
        self.assertEqual(2, len(results))

        statuses = {result.status for result in results}
        self.assertIn(SteamGameImportStatus.CREATED, statuses)
        self.assertTrue(
            statuses
            & {
                SteamGameImportStatus.UPDATED,
                SteamGameImportStatus.UNCHANGED,
            },
            f"expected a recovery status alongside CREATED, got {statuses}",
        )

        rows = Game.objects.filter(
            source_type=SourceType.STEAM,
            external_id=app_id,
        )
        self.assertEqual(1, rows.count())
        self.assertEqual({result.game_id for result in results}, {rows.get().pk})
