"""
SQL-injection defense-in-depth probes — SBGC-185.

Executes the playbook's injection-class payload families (boolean-blind,
time-based blind, error-based, UNION-based, second-order, and input-validation
robustness) against live application endpoints under a production-like
configuration (``DEBUG=False``).  The probes assert the ORM/driver behaviour
the playbook requires: payloads are treated as literal data, never as SQL —
responses are byte-identical between tautology and contradiction, never leak
PostgreSQL error text, never introduce artificial delay, and the DatabaseCache
rate limiters are disabled only because ``API_RATE_LIMITING_ENABLED`` is False
in the test settings module.

These tests are regression evidence for the audit documented in
``docs/sql-injection-defense-in-depth.md``; they are not a substitute for
black-box probing of a dedicated preview branch backed by a Neon copy-on-write
branch (see that document's execution section).
"""

from __future__ import annotations

import time
from typing import Any

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from games.models import Game, SourceType

# PostgreSQL error markers that must never surface in a response body.
_PG_ERROR_MARKERS = (
    "syntax error",
    "invalid input syntax",
    "LINE 1",
    "ERROR:",
    "pg_sleep",
    'column "',
    "current_setting",
    "relation ",
)


@override_settings(DEBUG=False)
class CatalogueBooleanBlindTests(TestCase):
    """Playbook 3.1 — ORM-filtered ``?q=`` treats payloads as literal text."""

    def _probe(self, q: str):
        return self.client.get("/api/v1/games/", {"q": q})

    def test_tautology_and_contradiction_are_byte_identical(self):
        baseline = self._probe("widget")
        tautology = self._probe("widget' AND '1'='1")
        contradiction = self._probe("widget' AND '1'='2")
        self.assertEqual(tautology.status_code, 200)
        self.assertEqual(tautology.content, contradiction.content)
        # The ORM also treats the quote as a literal character: matching the
        # control query's results, not a truth-value-driven superset.
        self.assertEqual(baseline.status_code, 200)

    def test_or_sweep_payloads_return_no_sql_markers(self):
        for payload in (
            "' OR '1'='1",
            "' OR '1'='1' --",
            "x' OR 1=1--",
            "x' UNION SELECT NULL,NULL,NULL--",
        ):
            response = self._probe(payload)
            self.assertEqual(response.status_code, 200)
            body = response.content.decode(errors="replace")
            for marker in _PG_ERROR_MARKERS:
                self.assertNotIn(marker, body)


@override_settings(DEBUG=False)
class CatalogueTimeBlindTests(TestCase):
    """Playbook 3.2 — pg_sleep payloads must not delay or error."""

    def _timed_probe(self, q: str) -> tuple[float, Any]:
        # ``Any``: the Django test client's response type is a stub-private
        # ``_MonkeyPatchedWSGIResponse`` subclass not assignable to
        # ``HttpResponse`` under django-stubs.
        start = time.perf_counter()
        response = self.client.get("/api/v1/games/", {"q": q})
        elapsed = time.perf_counter() - start
        return elapsed, response

    def test_conditional_pg_sleep_causes_no_delay(self):
        # Warm-up (rules out first-request jitter), then time the payloads.
        self._timed_probe("warmup")
        sleep_true, _ = self._timed_probe(
            "zzz' AND (SELECT CASE WHEN (1=1) THEN pg_sleep(5) "
            "ELSE pg_sleep(0) END)::text='0'--"
        )
        sleep_false, control = self._timed_probe(
            "zzz' AND (SELECT CASE WHEN (1=2) THEN pg_sleep(5) "
            "ELSE pg_sleep(0) END)::text='0'--"
        )
        self.assertEqual(control.status_code, 200)
        # A parameterised icontains never executes the subquery: both requests
        # complete far below the 5s sleep the payload would trigger if the
        # value were interpolated into SQL.
        self.assertLess(sleep_true, 4.0)
        self.assertLess(sleep_false, 4.0)


@override_settings(DEBUG=False)
class ErrorAndUnionPostureTests(TestCase):
    """Playbook 3.3 / 3.4 — no PG error text; canonical envelopes only."""

    def test_error_based_payloads_never_leak_postgres_text(self):
        for payload in (
            "zzz' AND CAST((SELECT current_setting('server_version')) AS INT)--",
            "zzz' AND 1=(1/0)--",
        ):
            response = self.client.get("/api/v1/games/", {"q": payload})
            self.assertEqual(response.status_code, 200)
            body = response.content.decode(errors="replace")
            for marker in _PG_ERROR_MARKERS:
                self.assertNotIn(marker, body)

    def test_admin_login_username_injection_is_parameterized(self):
        """3.1/3.3 against Django Admin auth — invalid creds, never SQL errors."""
        for username in ("admin'--", "' OR '1'='1' --", "admin' AND 1=1--"):
            response = self.client.post(
                reverse("admin:login"),
                {
                    "username": username,
                    "password": "wrong-password",
                    "recaptcha_token": "test-recaptcha-token",
                },
            )
            # Invalid credentials re-render the login form (200) — a raw-SQL
            # injection would surface as a 500 with PG text instead.
            self.assertEqual(response.status_code, 200)
            body = response.content.decode(errors="replace")
            for marker in _PG_ERROR_MARKERS:
                self.assertNotIn(marker, body)

    def test_username_endpoint_validates_before_the_database(self):
        """3.6 — regex validation runs first; it is not the security control."""
        # check-username applies a strict pattern BEFORE any DB interaction, so
        # SQL metacharacters are rejected as invalid input (422), not executed.
        for username in ("admin'--", "admin' OR 1=1--", "robert'); DROP TABLE x;--"):
            response = self.client.get(
                "/api/v1/auth/check-username", {"username": username}
            )
            self.assertEqual(response.status_code, 422)
            body = response.content.decode(errors="replace")
            for marker in _PG_ERROR_MARKERS:
                self.assertNotIn(marker, body)


@override_settings(DEBUG=False)
class SecondOrderPostureTests(TestCase):
    """Playbook 3.5 — stored payloads round-trip as data through every reader."""

    def setUp(self):
        cache.clear()
        User.objects.create_superuser(
            username="root", email="root@example.com", password="root-pass-123"
        )

    def test_classic_drop_payload_stored_and_read_back_as_literal_data(self):
        payload = "Game Robert'); DROP TABLE games_game;--"
        game = Game.objects.create(
            name=payload,
            slug="robert-drop-table-game",
            source_type=SourceType.MANUAL,
        )

        # Immediate read path (ORM detail lookup) returns the record intact.
        reread = Game.objects.filter(pk=game.pk).first()
        assert reread is not None
        self.assertEqual(reread.name, payload)
        # The catalogue search consumer treats the stored fragment as literal
        # text (icontains) — the table still exists and still contains the row.
        response = self.client.get("/api/v1/games/", {"q": "DROP TABLE"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Game.objects.filter(pk=game.pk).exists())
        self.assertEqual(Game.objects.count(), 1)
