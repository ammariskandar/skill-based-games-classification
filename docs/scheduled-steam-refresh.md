# Scheduled Steam Metadata Refresh — SBGC-183

Daily scheduled Steam metadata refresh with a per-Game retry budget,
failure-only retries, a DB-backed current-run audit, concurrency
protection, and a single final-failure operator alert.

This is the **final job/scheduler ticket** in epic SBGC-8. It orchestrates the
existing `SteamGameRefreshService` — it does **not** reimplement Steam refresh
or Steam transport, and it does not touch classification mathematics.

## Architecture

```text
Render Cron (deployment-owned)
  → python manage.py run_scheduled_steam_refresh
      → ScheduledSteamRefreshService
          → SteamGameRefreshService   (canonical refresh, per Game)
          → SteamRefreshRun / SteamRefreshGameAttempt   (DB audit)
          → resolve_refresh_recipients + send_mail      (final alert only)
```

The scheduler depends on the same `SteamGameRefreshService` that the Admin
"Refresh Steam metadata" action uses. It **never** calls a `ModelAdmin` action
and **never** talks to `SteamClient` directly.

## Scheduler technology decision

Chosen: **Render Cron Job → Django management command** (the lightest viable
option for a Render-deployed Django app).

The decision ladder was evaluated in order:

1. **Render Cron → management command** — chosen. One process, no extra
   infrastructure.
2. system cron → management command — acceptable but Render has no persistent
   cron shell.
3. APScheduler in-process — adds a long-running scheduler loop inside web
   workers, which is exactly what this ticket avoids.
4. Celery Beat + workers — distributed task infrastructure, unnecessary at this
   scale.

No Celery, no Redis, no APScheduler.

### Long-lived vs multi-invocation

A **single long-lived command** is used: one process establishes the run and
then sleeps 360s / 360s / 10800s between attempts. This is deliberately chosen
for simplicity — retry state lives in the current process's pending list and in
the DB audit, not in a cross-invocation scheduler.

The trade-off is documented as-is: Render's free/standard cron jobs must be
allowed to live up to ~3h12m for the final attempt. If a deployment cannot run
a job that long, the alternative (persist pending state and start later attempts
separately) is a follow-up, not part of SBGC-183.

## Timezone

`TIME_ZONE = "UTC"` and `USE_TZ = True`. The product contract says "approximately
00:00 system/application time"; with the default settings this is **00:00 UTC**.
Render Cron must be configured with the matching timezone; if a different local
hour is required, the production cron schedule and/or `TIME_ZONE` must be aligned
explicitly. The precise local hour is not a product-critical requirement.

## Eligibility (Steam-only)

Only `source_type == steam` Games are selected. The selection uses the canonical
`Game.objects.filter(source_type=SourceType.STEAM)` path; manual Games never
reach `SteamGameRefreshService`. `selected_count` reflects eligible Steam Games
only.

## Retry timeline (frozen contract)

| Attempt | Offset from run start | Wait before attempt |
|---------|-----------------------|---------------------|
| 1       | T+0                   | —                   |
| 2       | T+6m                  | 360s                |
| 3       | T+12m                 | 360s                |
| 4       | T+3h12m               | 10800s              |

`WAIT_SECONDS = (360, 360, 10800)` — the waits **before** attempts 2, 3, and 4.
There is **no fifth attempt**.

### Per-Game budget and failure-only retries

Each selected Steam Game has its own budget of up to four attempts in today's
run. The pending population is rebuilt each round from **failures only**:

- Attempt 1: all eligible Steam Games.
- Attempt 2: Attempt-1 failures only.
- Attempt 3: Attempt-2 failures only.
- Attempt 4: Attempt-3 failures only.

Success removes a Game permanently from today's pending population. If a Game
succeeds on attempt 2, it is never refreshed again that day.

## Refresh result → scheduler result

`SteamGameRefreshService.refresh()` returns one of three statuses; the scheduler
maps them:

| Refresh status | Scheduler outcome | Retry? |
|----------------|-------------------|--------|
| `UPDATED`      | success           | no     |
| `UNCHANGED`    | success           | no     |
| `UNAVAILABLE`  | unavailable (retryable) | yes |

`UNAVAILABLE` is a **retryable attempt, not a scheduler success** — it is not
silently counted as success merely because it is represented as a status.

Exceptions are all retryable failures with a safe error category recorded:

- `SteamRefreshError` → `STEAM_REFRESH_ERROR`
- `SteamError` (transport/adapter) → its `code`/`message`
- any other unexpected exception → `INTERNAL_ERROR` with a truncated,
  secret-free summary

No raw Steam payload, traceback, or secret is persisted or alerted.

## Audit artifact (DB-backed)

Two minimal models persist the current run:

- `SteamRefreshRun` — `scheduled_at`, `started_at`, `finished_at`, `status`
  (`running`/`completed`/`failed`), `selected_count`, `successful_count`,
  `failed_count`, `alert_sent`.
- `SteamRefreshGameAttempt` — per-Game/per-attempt `attempt_number`,
  `timestamp`, `outcome` (`success`/`unavailable`/`failed`), `error_code`,
  `error_summary`.

Never stored: Steam API key, SMTP credentials, `DATABASE_URL`, raw Steam
payloads, or full traceback dumps.

### Atomic replacement

Only one daily run is retained. Establishing today's run creates the new run
and deletes prior runs **inside one transaction**, so a failed initialization
never erases the previous audit. Attempts 1–4 remain together under the same
run; attempt 2 never replaces attempt 1.

### Concurrency protection

Only one active (`status=running`) run may exist. This is enforced by a partial
unique constraint (`steam_refresh_run_single_active_uniq`) plus an
`IntegrityError` catch, so a duplicate or overlapping invocation (duplicate
cron trigger, manual run during an active run) exits cleanly without processing
the population twice.

A `running` run counts as **active only for its own local day**. A `running`
run whose `scheduled_at` falls on an earlier day is treated as stale (see
below) and does not block today's invocation.

### Stale run recovery

A run can remain `running` if the command is terminated before finalization
(Render cancelling/restarting the Cron job, a crash, host/service termination,
or a SIGTERM during a wait or a Steam request).  Without recovery, that row
would make every future run believe another scheduler process is still alive.

To keep the design operationally boring, a deterministic day-boundary policy is
used:

- A `running` run from a **previous day** is **stale** — the process that
  created it is no longer legitimately running today.  When today's scheduled
  invocation starts, the stale run is retired to a terminal `failed` state and
  then removed by the normal "only the current run is retained" replacement.
- A `running` run from **today** is a genuinely active run — a second
  invocation exits cleanly and processes nothing.

This guarantees tomorrow's ordinary daily run is always possible after an
abnormal termination.  Same-day recovery of an interrupted run is deliberately
not attempted automatically: if the process dies mid-day, a manual same-day
re-run is blocked until the next day (a documented limitation, not speculative
machinery).

### Transaction boundaries

No transaction is held open across Steam requests, waits, or email delivery.
Short transactions are used only for creating/updating run state, retiring a
stale run, and attempt audit writes.  A failed creation never erases the
previous audit because the retire-then-create-then-delete sequence runs inside
a single `transaction.atomic()` block.

## Final alert condition

An email is sent **only** when one or more Games remain unsuccessful **after
their fourth attempt** in today's run. No alert is sent after attempts 1, 2, or
3, and no alert is sent if all failures later recover. At most **one** summary
email is sent per daily run.

## Recipient resolution

`resolve_refresh_recipients()` resolves, in strict priority order:

1. valid, active Django Superuser emails (validated and deduplicated);
2. otherwise `STEAM_REFRESH_FALLBACK_EMAILS` (comma-separated, validated,
   deduplicated).

Fallback is **not additive** — when a valid active Superuser email exists, the
fallback addresses are **not** also emailed. Blank, invalid, and inactive
Superusers are ignored.

## Email implementation

`send_mail()` with the configured `DEFAULT_FROM_EMAIL` and standard
`EMAIL_*` settings is used for a plain-text operational alert. No SMTP
credentials are hardcoded.

The final email summarizes: scheduled run, selected count, success count, final
failure count, failed Game names / local IDs / Steam IDs, and the final-attempt
timestamp. No raw response payloads, secrets, or giant tracebacks.

## Email failure

The final run state is persisted **before** notification. If notification
fails, the run audit is preserved with `alert_sent = False`, a safe
notification-failure message is logged, Steam is not retried again, and there is
no recursive send. The management command reports the notification problem
honestly.

## Management command

```bash
python manage.py run_scheduled_steam_refresh
```

The command is a thin entry point: it constructs the canonical refresh service
via `build_steam_refresh_service()` and delegates to
`ScheduledSteamRefreshService`. No domain logic lives in the command.

If another run is already active, the command prints a warning and exits
cleanly (status `None`).

## Admin audit visibility

`SteamRefreshRun` and `SteamRefreshGameAttempt` are registered in Django Admin
as **read-only** surfaces:

- run: scheduled/status/counts/finished/alert-sent;
- attempts: run, game, attempt number, outcome, error code, timestamp.

`has_add_permission`, `has_change_permission`, and `has_delete_permission` all
return `False`. There is no rerun button. Raw data is not dumped.

## Deployment status

**Application job implemented** — the management command and orchestration
service are complete and tested.

**Production scheduler not provisioned** — no Render Cron was created. Rendering
the daily trigger (schedule/timezone → `run_scheduled_steam_refresh`) is
deployment-owned work and is **not** performed by this ticket. Do not claim a
production cron exists until it is actually provisioned.

## Configuration

- `STEAM_REFRESH_FALLBACK_EMAILS` — comma-separated fallback recipients, used
  only when no valid active Superuser email exists.
- `DEFAULT_FROM_EMAIL` — sender address for operational alert emails.

Both are safe/empty by default in `.env.example`; no personal email addresses
are committed.

## Testing

`games/tests/test_scheduled_refresh.py` covers the orchestration contract with
fake refresh services and a fake wait callable (no real minutes/hours, no live
Steam):

- all-success (single attempt, no email);
- partial retry (failure-only population);
- final failure (exact delays `[360, 360, 10800]`, one email);
- manual exclusion;
- same-day attempt retention;
- next-day atomic replacement;
- concurrent-run skip;
- stale previous-day `running` run recovery;
- email-failure audit preservation;
- recipient resolution (active/inactive/blank/invalid/duplicates/fallback);
- management-command delegation.

The wait abstraction records requested delays and returns immediately; the
scripted refresh fake drives per-Game per-attempt outcomes. No `time.sleep`
runs in tests.

### PostgreSQL concurrency verification

`games/tests/test_scheduled_refresh_pg.py` proves the current-run acquisition
path on a real PostgreSQL instance (the partial unique index and
`IntegrityError` recovery are the production concurrency guard):

- simultaneous acquisition — two contenders race on `SteamRefreshRun.objects.create`;
  exactly one wins, the loser returns cleanly and refreshes nothing;
- genuine active run — a same-day `running` run blocks a duplicate invocation
  and preserves the retained previous audit;
- subsequent run — after normal finalization, a later run establishes cleanly;
- stale recovery — a previous-day `running` run is retired and today's run
  establishes without being blocked.

Verified on PostgreSQL 16 (disposable Podman container), plus
`config.tests.test_pg_migrations` confirms migration `games.0008` applies and
reverses cleanly. No Neon is used.
