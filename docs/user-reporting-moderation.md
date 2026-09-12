# User Reporting & Moderation — SBGC-223

Client-side and backend machinery for reporting an account, triaging the report
in the Django Admin security desk, and the forced-remediation lockouts that
follow a moderation decision.

## Architecture

```
/profile/[username]  "Report User"  ->  ReportUserModal.astro
      |                                      |
      |  POST /api/reports/user  (Astro BFF) |
      v                                      v
security.services.reporting  <-  POST /api/v1/security/reports/user
      |
      +-- coalesce (reporter, offender) to one open report
      +-- anti-brigading burst detector
      +-- repeat-offender snapshot
      v
Django Admin "Security" desk  ->  Dismiss | Username | Bio | Permaban
      |
      v
ModerationEnforcementMiddleware  ->  /remediate/username  or  forced Edit Profile
      |
      v
process_scheduled_account_deletions (T + 3 hours)
```

## Domain model (`security/models.py`)

`UserReport` stores one community report.  `ReportReason` holds the four
checkbox categories (`offensive_username`, `offensive_name`, `offensive_bio`,
`other`); `ReportStatus` is the lifecycle:

| Status | Meaning |
| --- | --- |
| `pending_review` | Filed, awaiting a moderator. |
| `pending_username_change` | Lockout: the offender must pick a new username. |
| `pending_bio_change` | Lockout: the offender must edit their name/bio. |
| `scheduled_for_deletion` | Permaban confirmed; hard purge runs at T + 3 hours. |
| `resolved` | Remediation completed. |
| `dismissed` | Reviewed, no penalty. |

`OPEN_REPORT_STATUSES` is the coalescing set; `LOCKOUT_REPORT_STATUSES` drives
the middleware.  `ScheduledAccountDeletion` snapshots the email/username and the
purge timestamp so the ban can execute and email the offender after their
account row is locked.

## Ingestion heuristics (`security/services/reporting.py`)

- **Coalescing** — `submit_user_report()` holds at most one open report per
  `(reporter, offender)` pair.  Repeat filings merge their reason flags and
  description in place and return `(report, created=False)`.
- **Anti-brigading** — when an offender accumulates ≥ 100 reports in a rolling
  15-minute window, `_flag_brigading()` marks every open report in that window
  `possible_brigading=True`.  Evaluated only at ingestion time.
- **Repeat offender** — `is_repeat_offender()` is true when the offender already
  has a `dismissed` or `resolved` report; the result is snapshotted onto
  `repeat_offender_at_submission`.
- **Sanitisation** — `sanitize_plain_text()` strips ASCII control codes, rejects
  `<` / `>`, trims, and caps at 250 characters.
- **Guards** — a user cannot report themselves and staff accounts cannot be
  reported.

## Moderation actions

`dismiss_report`, `enforce_username_change`, `enforce_bio_change`, and
`schedule_permanent_ban` all log `actioned_by` / `actioned_at` and the staff
reason.  The permaban path additionally revokes every live session, sets
`is_active=False`, creates the `ScheduledAccountDeletion` row, and emails the
offender immediately.

The Admin desk (`security/admin.py`, reachable by superusers, moderators, and
community leaders) shows the offending-user link to the public profile, reason
badges, repeat-offender and brigading indicators, a dismiss bulk action, and the
`take-action` page.  The ban form requires the exact confirmation phrase
`permaban`; anything else re-renders the form with an error and schedules
nothing.

## Lockout & remediation

`ModerationEnforcementMiddleware` sets `request.moderation_lockout` for every
authenticated request and refuses `/api/*` calls outside the allow-list with a
structured `403 MODERATION_LOCKOUT`.  Staff and superusers bypass enforcement.

- `pending_username_change` may reach the auth router and
  `/api/v1/security/remediate/*` only.
- `pending_bio_change` additionally permits `/api/v1/users/*`.

The Astro perimeter mirrors this: `src/middleware.ts` reads
`GET /api/v1/security/lockout` and routes via `moderationRedirect()`
(`lib/server/moderation-routing.ts`).  A username lockout is redirected to
`/remediate/username`; a bio lockout to the viewer's own profile, where
`EditProfileModal` opens automatically, cannot be dismissed (Escape suppressed,
close/cancel removed), and keeps Save disabled until a real
first/last-name/bio delta is entered.  A successful save resolves the report
server-side and the page reloads into the normal state.

## Scheduled purge

`python manage.py process_scheduled_account_deletions` is intended to run every
five minutes.  For each due, unexecuted `ScheduledAccountDeletion` it emails
every reporter a thank-you notice, cascades `user.delete()` (purging profile,
submissions, and the schedule row), and marks the schedule executed.

## Frontend surfaces

- `ReportUserModal.astro` — four-category checkboxes, an "Other" textarea that
  unlocks on demand (250-character counter, angle brackets stripped), submit
  gated on at least one reason, and a success panel.  Unauthenticated viewers
  get an inline login toast instead of the dialog.
- `pages/api/reports/user.ts` — same-origin BFF; strips the upstream body to
  `{ success, message }`.
- `pages/remediate/username.astro` — locked sign-up variant (banner, read-only
  email, mandatory password rotation, no verify-email, no login link).

## Tests

- Backend: `security/tests/test_moderation.py` (ingestion API, dedup, brigading,
  repeat offender, sanitisation, lockout middleware, remediation service + API,
  Admin desk rendering, and the purge command).
- Frontend: `src/lib/server/moderation-routing.test.ts` (Vitest) and
  `tests/browser/report-user.spec.ts` (Playwright).
