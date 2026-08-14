"""
Admin Steam refresh action tests — SBGC-56.

The refresh action must skip manual games without any network work,
count outcomes, and report per-game known errors.  The composition
factory is patched with a fake service — no network in tests.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from games.models import Game, SourceType
from games.services.imports.steam import (
    SteamGameRefreshResult,
    SteamGameRefreshStatus,
    SteamRefreshError,
)


class _FakeRefreshService:
    """Configurable fake — call log + preset results/errors per game."""

    def __init__(self, results_by_pk=None, error_by_pk=None):
        self.results_by_pk = results_by_pk or {}
        self.error_by_pk = error_by_pk or {}
        self.calls: list[int] = []

    def refresh(self, game):
        self.calls.append(game.pk)
        if game.pk in self.error_by_pk:
            raise self.error_by_pk[game.pk]
        status = self.results_by_pk.get(game.pk, SteamGameRefreshStatus.UNCHANGED)
        changed = ("name",) if status == SteamGameRefreshStatus.UPDATED else ()
        return SteamGameRefreshResult(
            status=status,
            game_id=game.pk,
            changed_fields=changed,
        )


class AdminRefreshActionTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin-refresh", password="pw"
        )
        self.client.force_login(self.superuser)
        self.steam_game = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Portal 2",
            slug="portal-2",
        )
        self.steam_game_2 = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="440",
            name="TF2",
            slug="tf2",
        )
        self.manual_game = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Chess",
            slug="chess",
        )
        self.url = reverse("admin:games_game_changelist")

    def _post_action(self, game_pks):
        return self.client.post(
            self.url,
            {
                "action": "refresh_from_steam",
                "_selected_action": [str(pk) for pk in game_pks],
                "index": "0",
            },
            follow=True,
        )

    def test_action_registered(self):
        from games.admin import GameAdmin

        self.assertIn("refresh_from_steam", GameAdmin.actions or ())

    def test_mixed_selection_skips_manual_without_service_calls(self):
        fake = _FakeRefreshService(
            results_by_pk={
                self.steam_game.pk: SteamGameRefreshStatus.UPDATED,
            }
        )
        with mock.patch("games.admin._build_steam_refresh_service", return_value=fake):
            response = self._post_action([self.steam_game.pk, self.manual_game.pk])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake.calls, [self.steam_game.pk])
        self.assertContains(response, "1 updated")
        self.assertContains(response, "1 manual skipped")
        self.manual_game.refresh_from_db()
        self.assertIsNone(self.manual_game.last_steam_refresh_at)

    def test_manual_only_selection_warns_without_service(self):
        fake = _FakeRefreshService()
        with mock.patch("games.admin._build_steam_refresh_service", return_value=fake):
            response = self._post_action([self.manual_game.pk])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake.calls, [])
        self.assertContains(response, "manual games cannot refresh")

    def test_outcome_counts(self):
        fake = _FakeRefreshService(
            results_by_pk={
                self.steam_game.pk: SteamGameRefreshStatus.UPDATED,
                self.steam_game_2.pk: SteamGameRefreshStatus.UNAVAILABLE,
            }
        )
        with mock.patch("games.admin._build_steam_refresh_service", return_value=fake):
            response = self._post_action([self.steam_game.pk, self.steam_game_2.pk])

        self.assertContains(response, "1 updated")
        self.assertContains(response, "1 unavailable")

    def test_per_game_error_reported_and_others_continue(self):
        fake = _FakeRefreshService(
            results_by_pk={self.steam_game.pk: SteamGameRefreshStatus.UNCHANGED},
            error_by_pk={self.steam_game_2.pk: SteamRefreshError("bad app id")},
        )
        with mock.patch("games.admin._build_steam_refresh_service", return_value=fake):
            response = self._post_action([self.steam_game.pk, self.steam_game_2.pk])

        self.assertEqual(fake.calls, [self.steam_game.pk, self.steam_game_2.pk])
        self.assertContains(response, "1 unchanged")
        self.assertContains(response, "1 failed")

    def test_success_message_when_no_errors(self):
        fake = _FakeRefreshService(
            results_by_pk={self.steam_game.pk: SteamGameRefreshStatus.UNCHANGED}
        )
        with mock.patch("games.admin._build_steam_refresh_service", return_value=fake):
            response = self._post_action([self.steam_game.pk])

        self.assertContains(response, "1 unchanged")
        self.assertNotContains(response, "failed")
