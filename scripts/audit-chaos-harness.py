#!/usr/bin/env python3
"""
Pre-deployment chaos verification harness — SBGC-17 readiness audit.

Standalone, self-cleaning.  Builds an isolated in-memory test database via
Django's creation API (never the developer's real database), runs adversarial
payload, injection, concurrency and state-machine scenarios against the real
Ninja API + service boundary, asserts the resilience invariants, and destroys
the database in a ``finally`` block.

Usage (from the repository root):

    apps/backend/.venv/bin/python scripts/audit-chaos-harness.py
    apps/backend/.venv/bin/python scripts/audit-chaos-harness.py --json

Exit code 0 when every scenario passes, 1 when any invariant fails.  The
harness never mutates production code or a real database.
"""

from __future__ import annotations

import json
import os
import random
import sys
import threading

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(REPO_ROOT, "apps", "backend")
sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
os.environ.setdefault("DJANGO_SKIP_DOTENV", "1")

import django  # noqa: E402

django.setup()

from classifications.models import UserGameScoreSubmission  # noqa: E402
from classifications.services.aesthetic_consensus import (  # noqa: E402
    resolve_aesthetic_consensus,
)
from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection, transaction  # noqa: E402
from django.test import Client, override_settings  # noqa: E402
from django.test.utils import (  # noqa: E402
    CaptureQueriesContext,
    setup_test_environment,
    teardown_test_environment,
)
from games.models import Game  # noqa: E402
from security.models import (  # noqa: E402
    ScheduledAccountDeletion,
    UserReport,
)
from security.services.reporting import schedule_permanent_ban  # noqa: E402

User = get_user_model()

SUBMIT_SCORE = "/api/v1/classifications/games/{slug}/submit-score"
QUESTIONNAIRE_SUBMIT = "/api/v1/questionnaire/{slug}/submit"
CATALOGUE = "/api/v1/games/"
SIMILAR = "/api/v1/games/{slug}/similar"
REPORT = "/api/v1/security/reports/user"

RESULTS: list[dict] = []

SQLI = "' OR '1'='1'; DROP TABLE games_game CASCADE; --"
XSS = "<script>alert(document.cookie)</script><img src=x onerror=alert(1)>"
CONTROL = "a\x00b\x01c\x1fd\x7f" + "\u202e" + "\u200d"
LONG_10K = "lorem ipsum " * 834  # ~10,008 chars

PROFILE = {"micro": 40, "mystiko": 30, "macro": 30}


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"scenario": name, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def envelope_ok(body: object) -> bool:
    """True when *body* matches the canonical ApiErrorDto envelope."""
    if not isinstance(body, dict) or not isinstance(body.get("error"), dict):
        return False
    error = body["error"]
    return (
        isinstance(error.get("code"), str)
        and isinstance(error.get("message"), str)
        and isinstance(error.get("details"), list)
    )


def make_game(slug: str, name: str) -> Game:
    return Game.objects.create(
        name=name,
        slug=slug,
        source_type="manual",
        content_type="game",
        listing_status="published",
    )


def make_user(username: str, **kwargs):
    return User.objects.create_user(
        username=username, password="pw-chaos-123", **kwargs
    )


# ---------------------------------------------------------------------------
# Scenario groups
# ---------------------------------------------------------------------------


def scenario_vector_fuzz(client: Client, slug: str, baseline: int) -> None:
    """Sum/range/NaN/float fuzzing must fail closed with zero rows written."""
    bad_bodies = {
        "sum-99": {
            "challenge": {"micro": 33, "mystiko": 33, "macro": 33},
            "reward": PROFILE,
        },
        "sum-101": {
            "challenge": {"micro": 34, "mystiko": 34, "macro": 33},
            "reward": PROFILE,
        },
        "negative": {
            "challenge": {"micro": -10, "mystiko": 60, "macro": 50},
            "reward": PROFILE,
        },
        "extreme-floats": {
            "challenge": {"micro": 33.333, "mystiko": 33.333, "macro": 33.334},
            "reward": PROFILE,
        },
        "non-numeric": {
            "challenge": {"micro": "x", "mystiko": 50, "macro": 50},
            "reward": PROFILE,
        },
        "nan": {
            "challenge": {"micro": float("nan"), "mystiko": 50, "macro": 50},
            "reward": PROFILE,
        },
        "missing-dim": {"challenge": {"micro": 50}, "reward": PROFILE},
    }
    failures = []
    for label, body in bad_bodies.items():
        # NaN is not valid JSON; send it as a raw string payload instead.
        if label == "nan":
            resp = client.post(
                SUBMIT_SCORE.format(slug=slug),
                data='{"challenge":{"micro":NaN,"mystiko":50,"macro":50},"reward":{"micro":40,"mystiko":30,"macro":30}}',
                content_type="application/json",
            )
        else:
            resp = client.post(
                SUBMIT_SCORE.format(slug=slug),
                data=json.dumps(body),
                content_type="application/json",
            )
        if resp.status_code != 422:
            failures.append(f"{label}->{resp.status_code}")
        elif not envelope_ok(_json(resp)):
            failures.append(f"{label}->non-envelope")
    after = UserGameScoreSubmission.objects.count()
    record(
        "vector fuzz: all invalid vectors rejected with 422 envelope",
        not failures and after == baseline,
        f"failures={failures} rows_before={baseline} rows_after={after}",
    )


def scenario_injection(client: Client) -> None:
    """SQLi / XSS / control-code / 10k payloads must never 500 or leak."""
    failures = []

    # Catalogue search (q): SQLi/XSS/control -> 200 (parameterised); >100 chars -> 422.
    for label, value in (("sqli", SQLI), ("xss", XSS), ("control", CONTROL)):
        resp = client.get(CATALOGUE, {"q": value})
        if resp.status_code != 200:
            failures.append(f"catalogue-q-{label}->{resp.status_code}")
    resp = client.get(CATALOGUE, {"q": LONG_10K})
    if resp.status_code != 422:
        failures.append(f"catalogue-q-long->{resp.status_code}")

    # Report free text: XSS and 10k must be rejected (422) with the envelope.
    for label, value in (("xss", XSS), ("long", LONG_10K)):
        resp = client.post(
            REPORT,
            data=json.dumps(
                {
                    "offending_username": "chaos-offender",
                    "reason_other": True,
                    "other_description": value,
                }
            ),
            content_type="application/json",
        )
        if resp.status_code != 422 or not envelope_ok(_json(resp)):
            failures.append(f"report-{label}->{resp.status_code}")

    # Control codes in a legitimate description are stripped, not stored raw.
    resp = client.post(
        REPORT,
        data=json.dumps(
            {
                "offending_username": "chaos-offender",
                "reason_other": True,
                "other_description": CONTROL,
            }
        ),
        content_type="application/json",
    )
    if resp.status_code == 200:
        row = UserReport.objects.filter(
            reporting_user__username="chaos-reporter"
        ).first()
        if row and any(ord(ch) < 0x20 for ch in row.other_description):
            failures.append("report-control-not-stripped")

    record(
        "injection fuzz: SQLi/XSS/control/10k handled without 500 or leak",
        not failures,
        f"failures={failures}",
    )


def scenario_moderation_sanitization(staff_client: Client) -> None:
    """ban_reason / bio injection must be sanitised or rejected, never executed."""
    report = UserReport.objects.create(
        offending_user=User.objects.get(username="chaos-offender"),
        reporting_user=User.objects.get(username="chaos-reporter"),
        reason_username=True,
    )
    resp = staff_client.post(
        f"/test-admin/security/userreport/{report.pk}/take-action/",
        {
            "intervention": "permaban",
            "confirm_phrase": "permaban",
            "ban_reason": XSS,
        },
    )
    # Angle brackets are hard-rejected → the form re-renders (200) and nothing
    # is scheduled; the raw markup must not appear as executed HTML.
    scheduled = ScheduledAccountDeletion.objects.filter(
        user__username="chaos-offender"
    ).exists()
    body_has_script = "<script>alert(document.cookie)</script>" in resp.content.decode(
        "utf-8", errors="replace"
    )
    record(
        "moderation: ban_reason markup rejected (no schedule, no raw script)",
        resp.status_code == 200 and not scheduled and not body_has_script,
        f"status={resp.status_code} scheduled={scheduled} raw_script={body_has_script}",
    )


def scenario_dedup_burst(auth_client: Client, slug: str) -> None:
    """Rapid identical submissions collapse to exactly one persisted row."""
    for _ in range(10):
        auth_client.post(
            SUBMIT_SCORE.format(slug=slug),
            data=json.dumps({"challenge": PROFILE, "reward": PROFILE}),
            content_type="application/json",
        )
    rows = UserGameScoreSubmission.objects.filter(
        user__username="chaos-submitter", game__slug=slug
    ).count()
    record(
        "dedup: 10 rapid identical submissions → 1 row",
        rows == 1,
        f"rows={rows}",
    )


def scenario_aesthetic_tie_concurrency() -> None:
    """Concurrent conflicting votes resolve without deadlock and floor safely."""
    clear_majority = (
        [("SENSORY", "CHALLENGE")] * 20
        + [("FANTASY", "NARRATIVE")] * 12
        + [("FANTASY", "SENSORY")] * 10
        + [("NARRATIVE", "FANTASY")] * 8
    )
    outcomes: list[tuple[str, str, int, int, bool]] = []
    errors: list[str] = []

    def worker(seed: int) -> None:
        try:
            result = resolve_aesthetic_consensus(
                clear_majority, base_confidence=4.0, rng=random.Random(seed)
            )
            outcomes.append(
                (
                    result.primary,
                    result.secondary,
                    result.penalty,
                    result.confidence,
                    result.is_tie,
                )
            )
        except Exception as exc:  # noqa: BLE001 - recording the failure is the point
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker, args=(seed,)) for seed in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # A clear plurality (20 of 50) must win deterministically under concurrency.
    assert_ok = (
        not errors
        and len(outcomes) == 8
        and all(o[:2] == ("SENSORY", "CHALLENGE") for o in outcomes)
        and all(not o[4] for o in outcomes)
        and all(0 <= o[3] <= 100 for o in outcomes)
    )
    record(
        "aesthetic consensus: concurrent clear plurality, no deadlock",
        assert_ok,
        f"errors={errors} outcomes={len(outcomes)} "
        f"winner={outcomes[0][:2] if outcomes else 'n/a'}",
    )

    # Contested 4-way election (13/13/12/12): top-vote tie across two leaders.
    contested = [
        ("SENSORY", "CHALLENGE"),
        ("FANTASY", "NARRATIVE"),
        ("FANTASY", "SENSORY"),
        ("NARRATIVE", "FANTASY"),
    ]
    contested_votes = [contested[i % 4] for i in range(50)]
    tie = resolve_aesthetic_consensus(
        contested_votes, base_confidence=50.0, rng=random.Random(7)
    )
    leaders = {(p.primary, p.secondary) for p in tie.tied_pairs}
    record(
        "aesthetic consensus: contested 4-way election picks tied leader",
        tie.is_tie
        and tie.penalty in (0, 1, 5, 10)
        and (tie.primary, tie.secondary) in leaders
        and tie.confidence == max(0, 50 - tie.penalty),
        f"is_tie={tie.is_tie} penalty={tie.penalty} "
        f"winner={(tie.primary, tie.secondary)} leaders={sorted(leaders)}",
    )
    # Same seed → same winner (no hidden nondeterminism / shared global state).
    repeat = resolve_aesthetic_consensus(
        contested_votes, base_confidence=50.0, rng=random.Random(7)
    )
    record(
        "aesthetic consensus: identical seed yields identical winner",
        (repeat.primary, repeat.secondary) == (tie.primary, tie.secondary),
        f"first={(tie.primary, tie.secondary)} "
        f"second={(repeat.primary, repeat.secondary)}",
    )

    # Explicit 1v1 total-disagreement tie applies exactly -10%.
    duel = resolve_aesthetic_consensus(
        [("SENSORY", "CHALLENGE"), ("FANTASY", "NARRATIVE")],
        base_confidence=50.0,
        rng=random.Random(0),
    )
    record(
        "aesthetic consensus: 1v1 total-disagreement tie applies -10%",
        duel.is_tie and duel.penalty == 10 and duel.confidence == 40,
        f"is_tie={duel.is_tie} penalty={duel.penalty} confidence={duel.confidence}",
    )
    floored = resolve_aesthetic_consensus(
        [("SENSORY", "CHALLENGE"), ("FANTASY", "NARRATIVE")],
        base_confidence=4.0,
        rng=random.Random(0),
    )
    record(
        "aesthetic consensus: penalty clamps at 0 (4% - 10% = 0%)",
        floored.confidence == 0,
        f"confidence={floored.confidence}",
    )


def scenario_moderation_race(staff_client: Client, slug: str) -> None:
    """A permaban revokes sessions and locks the account against concurrent API use."""
    offender = User.objects.get(username="chaos-offender")
    report = UserReport.objects.filter(offending_user=offender).first()
    if report is None:
        report = UserReport.objects.create(
            offending_user=offender,
            reporting_user=User.objects.get(username="chaos-reporter"),
            reason_username=True,
        )
    schedule_permanent_ban(
        report, actor=staff_session_user(staff_client), ban_reason="chaos audit"
    )

    offender.refresh_from_db()
    # A session created *after* the ban must be refused by the middleware.
    locked_client = Client()
    locked_client.force_login(offender)
    me_resp = locked_client.patch(
        "/api/v1/users/me",
        data=json.dumps({"first_name": "x", "last_name": "y", "bio": ""}),
        content_type="application/json",
    )
    submit_resp = locked_client.post(
        SUBMIT_SCORE.format(slug=slug),
        data=json.dumps({"challenge": PROFILE, "reward": PROFILE}),
        content_type="application/json",
    )
    lockout_resp = locked_client.get("/api/v1/security/lockout")

    ok = (
        not offender.is_active
        and me_resp.status_code in (401, 403)
        and submit_resp.status_code in (401, 403)
        and lockout_resp.status_code in (401, 403)
        and (me_resp.status_code == 401 or envelope_ok(_json(me_resp)))
    )
    record(
        "moderation race: permaban locks account, API returns 401/403",
        ok,
        f"is_active={offender.is_active} me={me_resp.status_code} "
        f"submit={submit_resp.status_code} lockout={lockout_resp.status_code}",
    )


def scenario_transaction_rollback(slug: str) -> None:
    """An aborted atomic block leaves zero persisted artifacts."""
    before = UserGameScoreSubmission.objects.count()
    try:
        with transaction.atomic():
            UserGameScoreSubmission.objects.create(
                user=User.objects.get(username="chaos-submitter"),
                game=Game.objects.get(slug=slug),
                challenge_micro=40,
                challenge_mystiko=30,
                challenge_macro=30,
                reward_micro=40,
                reward_mystiko=30,
                reward_macro=30,
            )
            raise RuntimeError("chaos rollback")
    except RuntimeError:
        pass
    after = UserGameScoreSubmission.objects.count()
    record(
        "atomic rollback: aborted transaction leaves zero pollution",
        before == after,
        f"before={before} after={after}",
    )


def scenario_error_envelopes(anon_client: Client, slug: str) -> None:
    """Every 4xx must use the canonical envelope with a details array."""
    probes = [
        ("catalogue page=0", "get", CATALOGUE, {"page": 0}),
        ("catalogue page_size=101", "get", CATALOGUE, {"page_size": 101}),
        ("catalogue sort=invalid", "get", CATALOGUE, {"sort": "invalid_col"}),
        ("similar limit=0", "get", SIMILAR.format(slug=slug), {"limit": 0}),
        ("similar limit=25", "get", SIMILAR.format(slug=slug), {"limit": 25}),
        ("rankings profile=invalid", "get", "/api/v1/rankings/", {"profile": "nope"}),
        ("detail unknown slug", "get", "/api/v1/games/chaos-no-such-game", None),
        (
            "submit-score unauthenticated",
            "post",
            SUBMIT_SCORE.format(slug=slug),
            {"challenge": PROFILE, "reward": PROFILE},
        ),
    ]
    failures = []
    for label, method, path, payload in probes:
        if method == "get":
            resp = anon_client.get(path, payload or {})
        else:
            resp = anon_client.post(
                path, data=json.dumps(payload), content_type="application/json"
            )
        body = _json(resp)
        if resp.status_code < 400 or resp.status_code >= 500:
            failures.append(f"{label}->{resp.status_code}")
        elif not envelope_ok(body):
            failures.append(f"{label}->non-envelope")
        elif resp.status_code == 422 and not body["error"]["details"]:
            failures.append(f"{label}->empty-details")
    record(
        "error envelope: all probed 4xx match {error:{code,message,details[]}}",
        not failures,
        f"failures={failures}",
    )


def scenario_query_profile(client: Client, slug: str) -> None:
    """Hot public endpoints must stay within their query budgets (no N+1)."""
    existing = set(Game.objects.values_list("slug", flat=True))
    for index in range(24):
        bulk_slug = f"chaos-bulk-{index}"
        if bulk_slug not in existing:
            make_game(bulk_slug, f"Chaos Bulk {index}")

    measured: dict[str, int] = {}
    with CaptureQueriesContext(connection) as ctx:
        client.get(CATALOGUE, {"page_size": 24})
    measured["catalogue"] = len(ctx)
    with CaptureQueriesContext(connection) as ctx:
        client.get("/api/v1/rankings/", {"page_size": 50})
    measured["rankings"] = len(ctx)
    with CaptureQueriesContext(connection) as ctx:
        client.get(f"/api/v1/games/{slug}")
    measured["detail"] = len(ctx)
    with CaptureQueriesContext(connection) as ctx:
        client.get(SIMILAR.format(slug=slug))
    measured["similar"] = len(ctx)

    targets = {"catalogue": 4, "rankings": 3, "detail": 3, "similar": 2}
    breaches = {k: measured[k] for k in targets if measured[k] > targets[k]}
    record(
        "query profile: catalogue<=4 ranking<=3 detail<=3 similar<=2 SQL queries",
        not breaches,
        f"measured={measured} targets={targets}",
    )


def scenario_rate_limit(client: Client) -> None:
    """A read burst must trip the throttle with a standard 429 envelope."""
    from django.core.cache import cache

    cache.clear()
    responses = []
    with override_settings(API_RATE_LIMITING_ENABLED=True):
        for _ in range(135):
            responses.append(client.get(CATALOGUE))
    limited = [r for r in responses if r.status_code == 429]
    envelope = envelope_ok(_json(limited[0])) if limited else False
    record(
        "rate limit: 135-request burst yields 429 RATE_LIMITED with envelope",
        bool(limited) and envelope and limited[0].status_code == 429,
        f"429_count={len(limited)} envelope={envelope}",
    )


def scenario_security_headers(anon: Client) -> None:
    """Response headers and the obfuscated admin perimeter must hold."""
    resp = anon.get(CATALOGUE)
    headers = {key.lower(): value for key, value in resp.headers.items()}
    expected = {
        "x-content-type-options": "nosniff",
        "referrer-policy": "strict-origin-when-cross-origin",
        "x-frame-options": "SAMEORIGIN",
    }
    mismatches = {
        k: headers.get(k)
        for k, v in expected.items()
        if (headers.get(k) or "").lower() != v.lower()
    }
    record(
        "security headers: nosniff / strict-origin referrer / frame protection present",
        not mismatches,
        f"mismatches={mismatches}",
    )

    admin_default = anon.get("/admin/login/")
    admin_alt = anon.get("/admin/")
    record(
        "admin perimeter: default /admin/ and /admin/login/ return 404",
        admin_default.status_code == 404 and admin_alt.status_code == 404,
        f"login={admin_default.status_code} root={admin_alt.status_code}",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json(resp) -> object:
    try:
        return json.loads(resp.content)
    except Exception:  # noqa: BLE001
        return None


def staff_session_user(staff_client: Client):
    """Resolve the user behind a staff test client (force_login keeps it in-session)."""
    return User.objects.get(username="chaos-moderator")


def seed_fixtures() -> None:
    make_game("chaos-game-1", "Chaos Game One")
    make_game("chaos-game-2", "Chaos Game Two")
    make_user("chaos-submitter")
    make_user("chaos-reporter")
    make_user("chaos-offender")
    User.objects.create_superuser(
        username="chaos-moderator", email="mod@example.com", password="pw-chaos-123"
    )


def run() -> int:
    setup_test_environment()
    old_config = connection.creation.create_test_db(verbosity=0, autoclobber=True)
    try:
        seed_fixtures()

        submitter = Client()
        submitter.force_login(User.objects.get(username="chaos-submitter"))
        reporter = Client()
        reporter.force_login(User.objects.get(username="chaos-reporter"))
        staff = Client()
        staff.force_login(User.objects.get(username="chaos-moderator"))
        anon = Client()

        slug = "chaos-game-1"
        baseline = UserGameScoreSubmission.objects.count()

        scenario_vector_fuzz(submitter, slug, baseline)
        scenario_query_profile(anon, slug)
        scenario_injection(reporter)
        scenario_moderation_sanitization(staff)
        scenario_dedup_burst(submitter, slug)
        scenario_aesthetic_tie_concurrency()
        scenario_moderation_race(staff, slug)
        scenario_transaction_rollback(slug)
        scenario_error_envelopes(anon, slug)
        scenario_security_headers(anon)
        scenario_rate_limit(anon)
    finally:
        connection.creation.destroy_test_db(old_config, verbosity=0)
        teardown_test_environment()

    failures = [r for r in RESULTS if not r["ok"]]
    passed = len(RESULTS) - len(failures)
    print("\n" + "=" * 64)
    print(f"Chaos harness complete: {passed}/{len(RESULTS)} scenarios passed")
    print("=" * 64)
    return 1 if failures else 0


if __name__ == "__main__":
    code = run()
    if "--json" in sys.argv:
        print(
            json.dumps(
                {
                    "scenarios": RESULTS,
                    "failures": len([r for r in RESULTS if not r["ok"]]),
                },
                indent=2,
            )
        )
    sys.exit(code)
