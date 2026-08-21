"""
Scheduled Steam metadata refresh orchestration tests — SBGC-183.
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
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
from games.services.scheduled_refresh import (
    ScheduledSteamRefreshService,
    resolve_refresh_recipients,
)


class _FakeWait:
    def __init__(self):
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class _FakeRefreshService:
    """Configurable fake refresh service — records calls and returns results."""

    def __init__(self, *, results_by_pk=None, error_by_pk=None):
        self.results_by_pk = results_by_pk or {}
        self.error_by_pk = error_by_pk or {}
        self.call_counts: dict[int, int] = {}

    def refresh(self, game):
        self.call_counts[game.pk] = self.call_counts.get(game.pk, 0) + 1
        if game.pk in self.error_by_pk:
            raise self.error_by_pk[game.pk]
        status = self.results_by_pk.get(game.pk, SteamGameRefreshStatus.UNCHANGED)
        changed = ("name",) if status == SteamGameRefreshStatus.UPDATED else ()
        return SteamGameRefreshResult(
            status=status, game_id=game.pk, changed_fields=changed
        )


class _ScriptedRefreshService:
    """Fake that consumes a per-Game script of results/exceptions in order."""

    def __init__(self):
        self.scripts: dict[int, list] = {}
        self.call_counts: dict[int, int] = {}

    def set_script(self, game, steps):
        self.scripts[game.pk] = list(steps)

    def refresh(self, game):
        self.call_counts[game.pk] = self.call_counts.get(game.pk, 0) + 1
        steps = self.scripts.get(game.pk)
        if steps:
            step = steps.pop(0)
            if isinstance(step, Exception):
                raise step
            return step
        return SteamGameRefreshResult(
            status=SteamGameRefreshStatus.UNCHANGED, game_id=game.pk
        )


class ScheduledSteamRefreshTests(TestCase):
    def _steam(self, name, external_id):
        return Game.objects.create(
            source_type=SourceType.STEAM,
            external_id=external_id,
            name=name,
            slug=name.lower().replace(" ", "-"),
        )

    def _run(self, refresh_service, wait) -> SteamRefreshRun:
        service = ScheduledSteamRefreshService(refresh_service, wait=wait)
        run = service.run(scheduled_at=timezone.now())
        assert run is not None
        return run

    def test_all_success_single_attempt_no_email(self):
        a = self._steam("A", "1")
        b = self._steam("B", "2")
        fake = _FakeRefreshService(
            results_by_pk={
                a.pk: SteamGameRefreshStatus.UNCHANGED,
                b.pk: SteamGameRefreshStatus.UPDATED,
            }
        )
        wait = _FakeWait()

        run = self._run(fake, wait)

        self.assertIsNotNone(run)
        self.assertEqual(run.status, SteamRefreshRun.Status.COMPLETED)
        self.assertEqual(run.selected_count, 2)
        self.assertEqual(run.successful_count, 2)
        self.assertEqual(run.failed_count, 0)
        self.assertEqual(fake.call_counts, {a.pk: 1, b.pk: 1})
        self.assertEqual(wait.delays, [])
        self.assertEqual(len(mail.outbox), 0)

    def test_partial_retry_retries_only_failures(self):
        a = self._steam("A", "1")
        b = self._steam("B", "2")
        c = self._steam("C", "3")
        fake = _ScriptedRefreshService()
        fake.set_script(
            a,
            [
                SteamGameRefreshResult(
                    status=SteamGameRefreshStatus.UNCHANGED, game_id=a.pk
                )
            ],
        )
        fake.set_script(
            b,
            [
                SteamRefreshError("boom b"),
                SteamGameRefreshResult(
                    status=SteamGameRefreshStatus.UNCHANGED, game_id=b.pk
                ),
            ],
        )
        fake.set_script(
            c,
            [
                SteamRefreshError("boom c"),
                SteamRefreshError("boom c"),
                SteamGameRefreshResult(
                    status=SteamGameRefreshStatus.UNCHANGED, game_id=c.pk
                ),
            ],
        )
        wait = _FakeWait()

        run = self._run(fake, wait)

        self.assertEqual(run.status, SteamRefreshRun.Status.COMPLETED)
        self.assertEqual(fake.call_counts, {a.pk: 1, b.pk: 2, c.pk: 3})
        self.assertEqual(wait.delays, [360, 360])
        self.assertEqual(len(mail.outbox), 0)

    def test_final_failure_sends_one_email_with_exact_delays(self):
        c = self._steam("C", "3")
        fake = _FakeRefreshService(error_by_pk={c.pk: SteamRefreshError("persistent")})
        wait = _FakeWait()

        User.objects.create_superuser(
            username="s", email="op@example.com", password="pw"
        )

        run = self._run(fake, wait)

        self.assertEqual(run.status, SteamRefreshRun.Status.FAILED)
        self.assertEqual(fake.call_counts[c.pk], 4)
        self.assertEqual(wait.delays, [360, 360, 10800])
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(run.alert_sent)

    def test_manual_game_never_refreshed_or_selected(self):
        steam = self._steam("Steam", "1")
        manual = Game.objects.create(
            source_type=SourceType.MANUAL, name="Manual", slug="manual"
        )
        fake = _FakeRefreshService(
            results_by_pk={steam.pk: SteamGameRefreshStatus.UNCHANGED}
        )
        wait = _FakeWait()

        run = self._run(fake, wait)

        self.assertEqual(run.selected_count, 1)
        self.assertNotIn(manual.pk, fake.call_counts)
        self.assertEqual(fake.call_counts, {steam.pk: 1})

    def test_same_day_attempts_retained(self):
        c = self._steam("C", "3")
        fake = _FakeRefreshService(error_by_pk={c.pk: SteamRefreshError("persistent")})
        wait = _FakeWait()

        run = self._run(fake, wait)

        self.assertEqual(SteamRefreshGameAttempt.objects.filter(run=run).count(), 4)

    def test_next_day_replaces_previous_run(self):
        c = self._steam("C", "3")
        fake = _FakeRefreshService(
            results_by_pk={c.pk: SteamGameRefreshStatus.UNCHANGED}
        )
        self._run(fake, _FakeWait())
        self.assertEqual(SteamRefreshRun.objects.count(), 1)

        # Second run replaces the first.
        self._run(fake, _FakeWait())
        self.assertEqual(SteamRefreshRun.objects.count(), 1)

    def test_concurrent_run_skipped(self):
        SteamRefreshRun.objects.create(
            scheduled_at=timezone.now(), status=SteamRefreshRun.Status.RUNNING
        )
        fake = _FakeRefreshService()
        service = ScheduledSteamRefreshService(fake, wait=_FakeWait())
        run = service.run(scheduled_at=timezone.now())
        self.assertIsNone(run)
        self.assertEqual(SteamRefreshRun.objects.count(), 1)
        self.assertEqual(fake.call_counts, {})

    def test_stale_previous_day_running_run_is_recovered(self):
        c = self._steam("C", "3")
        SteamRefreshRun.objects.create(
            scheduled_at=timezone.now() - timedelta(days=1),
            status=SteamRefreshRun.Status.RUNNING,
        )
        fake = _FakeRefreshService(
            results_by_pk={c.pk: SteamGameRefreshStatus.UNCHANGED}
        )

        run = self._run(fake, _FakeWait())

        self.assertEqual(run.status, SteamRefreshRun.Status.COMPLETED)
        self.assertEqual(SteamRefreshRun.objects.count(), 1)
        self.assertEqual(SteamRefreshRun.objects.get().pk, run.pk)
        self.assertEqual(fake.call_counts, {c.pk: 1})

    def test_email_failure_preserves_failed_audit(self):
        c = self._steam("C", "3")
        fake = _FakeRefreshService(error_by_pk={c.pk: SteamRefreshError("persistent")})
        User.objects.create_superuser(
            username="s", email="op@example.com", password="pw"
        )

        with mock.patch(
            "games.services.scheduled_refresh.send_mail",
            side_effect=RuntimeError("smtp down"),
        ):
            run = self._run(fake, _FakeWait())

        self.assertEqual(run.status, SteamRefreshRun.Status.FAILED)
        self.assertFalse(run.alert_sent)
        self.assertEqual(SteamRefreshGameAttempt.objects.filter(run=run).count(), 4)


class RecipientResolutionTests(TestCase):
    @override_settings(STEAM_REFRESH_FALLBACK_EMAILS="")
    def test_active_superusers_used(self):
        User.objects.create_superuser(
            username="a", email="a@example.com", password="pw", is_active=True
        )
        self.assertEqual(resolve_refresh_recipients(), ["a@example.com"])

    @override_settings(STEAM_REFRESH_FALLBACK_EMAILS="")
    def test_inactive_and_blank_ignored(self):
        User.objects.create_superuser(
            username="a", email="a@example.com", password="pw", is_active=False
        )
        User.objects.create_superuser(username="b", email="", password="pw")
        self.assertEqual(resolve_refresh_recipients(), [])

    @override_settings(STEAM_REFRESH_FALLBACK_EMAILS="fallback@example.com")
    def test_fallback_used_when_no_superuser(self):
        self.assertEqual(resolve_refresh_recipients(), ["fallback@example.com"])

    @override_settings(STEAM_REFRESH_FALLBACK_EMAILS="fallback@example.com")
    def test_fallback_not_added_when_superuser_exists(self):
        User.objects.create_superuser(
            username="a", email="a@example.com", password="pw"
        )
        self.assertEqual(resolve_refresh_recipients(), ["a@example.com"])

    @override_settings(
        STEAM_REFRESH_FALLBACK_EMAILS="fallback@example.com, fallback@example.com"
    )
    def test_duplicates_removed(self):
        self.assertEqual(resolve_refresh_recipients(), ["fallback@example.com"])


class ManagementCommandTests(TestCase):
    def test_command_delegates_to_service(self):
        from io import StringIO

        from django.core.management import call_command

        fake = _FakeRefreshService()
        with mock.patch(
            "games.management.commands.run_scheduled_steam_refresh.build_steam_refresh_service",
            return_value=fake,
        ):
            out = StringIO()
            call_command("run_scheduled_steam_refresh", stdout=out)

        self.assertIn("Steam refresh run finished", out.getvalue())
