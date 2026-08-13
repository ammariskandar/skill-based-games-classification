"""
Concurrent Steam import race verification — SBGC-54.

PostgreSQL-only.  Two verified races:

1. Same App ID — the partial unique index on ``(source_type, external_id)``
   is the authority; the loser recovers the winner's row instead of
   duplicating it.
2. Distinct App IDs with the same name — both imports compute the same
   preferred slug; the loser's INSERT fails on the unique slug index, and
   the persistence layer recomputes a deterministic suffixed slug and
   retries once.  Both canonical identities must persist exactly once.

Skips on SQLite — the default lane cannot prove concurrent uniqueness.
"""

from __future__ import annotations

import threading
from unittest import SkipTest, mock

from django.db import connections
from django.test import TransactionTestCase

import games.services.imports.steam as steam_module
from games.models import Game, SourceType
from games.services.imports.steam import (
    SteamGameImportResult,
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


class DistinctAppIdSlugRaceTests(TransactionTestCase):
    """Two different App IDs with the same name must both persist.

    Both imports compute the preferred slug ``same-name`` before either
    INSERTs (rendezvous guarantee).  One wins the unique slug index; the
    loser's INSERT raises ``IntegrityError``, its identity row does not
    exist (different App ID), but the computed slug is now occupied — so
    the persistence layer recomputes a deterministic suffixed slug and
    retries once.  Expected final state:

        A → same-name
        B → same-name-steam-<B>

    (or the inverse, depending on which import wins the race).
    """

    @classmethod
    def setUpClass(cls):
        from django.db import connection

        if connection.vendor != "postgresql":
            raise SkipTest(
                "Concurrent import tests require PostgreSQL. "
                "Use --settings=config.settings.postgresql_test."
            )
        super().setUpClass()

    def test_same_name_distinct_app_ids_both_persist(self):
        name = "Same Name"
        candidate_a = SteamGameImportCandidate(
            app_id="777001", name=name, content_type="game"
        )
        candidate_b = SteamGameImportCandidate(
            app_id="777002", name=name, content_type="game"
        )

        # Rendezvous: both threads must have computed their first slug
        # (the shared preferred slug) before either INSERTs.  An Event +
        # Semaphore releases exactly once for the two first allocations;
        # any retry allocation passes immediately.
        arrived = threading.Semaphore(0)
        release = threading.Event()
        original_slug = steam_module.build_steam_game_slug

        def synchronized_slug(*args, **kwargs):
            result = original_slug(*args, **kwargs)
            arrived.release()
            release.wait(timeout=15)
            return result

        results: dict[str, SteamGameImportResult] = {}
        errors: list[BaseException] = []

        def worker(key: str, candidate: SteamGameImportCandidate) -> None:
            try:
                service = SteamGamePersistenceService()
                results[key] = service.persist(candidate)
            except BaseException as exc:  # noqa: BLE001 — captured for assertion
                errors.append(exc)
            finally:
                # Django connections are thread-local — each worker must
                # close its own, or the test-DB teardown fails with
                # "database is being accessed by other users".
                connections.close_all()

        t1 = threading.Thread(target=worker, args=("A", candidate_a))
        t2 = threading.Thread(target=worker, args=("B", candidate_b))

        try:
            with mock.patch.object(
                steam_module, "build_steam_game_slug", synchronized_slug
            ):
                t1.start()
                t2.start()
                # Wait until both threads computed their first slug, then
                # release them to race on the unique slug index.
                arrived.acquire(timeout=30)
                arrived.acquire(timeout=30)
                release.set()
                t1.join(timeout=30)
                t2.join(timeout=30)
        finally:
            connections.close_all()

        self.assertFalse(t1.is_alive(), "first import thread did not finish")
        self.assertFalse(t2.is_alive(), "second import thread did not finish")
        self.assertEqual([], errors)
        self.assertEqual(2, len(results))

        # Both canonical Steam identities persisted exactly once.
        rows = Game.objects.filter(
            source_type=SourceType.STEAM,
            external_id__in=["777001", "777002"],
        )
        self.assertEqual(2, rows.count())
        by_app_id = {row.external_id: row for row in rows}
        self.assertEqual(set(by_app_id), {"777001", "777002"})

        # Both slugs unique; one preferred, one deterministic suffixed.
        slugs = [row.slug for row in rows]
        self.assertEqual(len(set(slugs)), 2)
        self.assertIn("same-name", slugs)
        suffixed = [s for s in slugs if s != "same-name"]
        self.assertEqual(len(suffixed), 1)
        self.assertTrue(suffixed[0].startswith("same-name-steam-"))

        # Both results are CREATED — no import failed permanently.
        for result in results.values():
            self.assertEqual(result.status, SteamGameImportStatus.CREATED)
