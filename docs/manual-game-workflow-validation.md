# Manual Game Workflow Validation — SBGC-62

Verification evidence for manual (non-Steam) Game workflows implemented in
SBGC-59/60/61.

## Environment

- Automated tests: in-memory SQLite (`config.settings.test`).
- Local development DB: SQLite (`apps/backend/db.sqlite3`).
- No Neon, no Render, no production/shared DB, no Steam network.
- Human Admin validation: **complete and passed**.

## Automated workflow evidence

`apps/backend/games/tests/test_manual_workflows.py` combines the service and
Admin boundaries:

| Workflow | Result |
|----------|--------|
| Full create (name, slug, content_type, listing, release_date, developer, description, image, website) | passed |
| Full edit (name, listing, release_date, developer, description, image) with slug/identity/Steam-field preservation | passed |
| Asset replace → clear → invalid-replacement-preserves-state | passed |
| Manual Steam refresh rejected before any network call | passed |
| Draft → Published listing transition | passed |
| Published non-Game excluded from public listing | passed |
| Duplicate name allowed; duplicate slug rejected | passed |
| Editorial classification preserved across manual edit | passed |
| Admin create → Admin edit workflow | passed |
| Admin invalid input (blank name, invalid image URL) rejected with no partial persistence | passed |
| Service create/edit never touches SteamClient | passed |

## Human validation result

All 19 checks passed.  Listing and refresh checks were **not** directly
observable through the Admin UI, so they were verified through the canonical
queryset/service/source-policy scripts — this is valid acceptance evidence.

| # | Check | Method | Result |
|---|-------|--------|--------|
| 1 | Create manual Game | Admin UI | pass |
| 2 | Verify source identity | Admin UI | pass |
| 3 | Normal manual editing | Admin UI | pass |
| 4 | Explicit slug editing | Admin UI | pass |
| 5 | Duplicate slug rejection | Admin UI | pass |
| 6 | Required name validation | Admin UI | pass |
| 7 | Manual image URL replacement | Admin UI | pass |
| 8 | Restore valid manual image | Admin UI | pass |
| 9 | Invalid asset validation | Admin UI | pass |
| 10 | Draft manual Game excluded from `publicly_listable()` | Django shell/query script | pass |
| 11 | Published manual Game included in `publicly_listable()` | Django shell/query script | pass |
| 12 | Published manual non-Game excluded | Django shell/query script | pass |
| 13 | Archived manual Game excluded | Django shell/query script | pass |
| 14 | Temporary editorial classification creation | Admin UI | pass |
| 15 | Game edit after classification preserves classification | Admin UI | pass |
| 16 | Source-specific Admin field behavior | Admin UI | pass |
| 17 | Steam manual-image override/fallback behavior | Admin/query | pass |
| 18 | Manual Game Steam-refresh rejection | source-policy/service script | pass |
| 19 | No raw traceback during final workflow validation | Admin UI | pass |

Do not use Neon; do not contact Steam.

## Blockers resolved

- **Human-validation environment blocker:** local development SQLite schema
  was stale and had not applied the SBGC-59 Game metadata migration
  (`games.0006_game_developer_game_release_date`).  This was not a
  production-code defect.  Resolved by applying existing migrations to the
  local SQLite database only (`migrate games --settings=config.settings.development`).
  Verified `release_date` and `developer` columns now exist and `showmigrations`
  reports `0006` applied.  No Neon/production DB was touched.

## Manual input formats

Manual Game `release_date` accepts exactly:

```text
YYYY-MM-DD   (2026-08-16)
DD-MM-YYYY   (16-08-2026)
DD/MM/YYYY   (16/08/2026)
YYYY/MM/DD   (2026/08/16)
```

All four normalize to the same calendar `date`.  Other formats are rejected
by normal form validation.

## User-facing help text

Jira keys, ticket numbers, branch names, and implementation-history wording
were removed from manual Game Admin/model help text.  `release_date` help
now documents accepted date formats; `developer`, `steam_image_url`, and
`last_steam_refresh_at` use concise domain-facing wording only.

## Limitations

- Manual delete/soft-delete/archive/restore are **not** implemented and are
  explicitly out of SBGC-62 scope; deletion is owned by **SBGC-182 — Game
  Deletion Workflow**.
- "Hide" is covered by `listing_status` draft/archived semantics, not a
  separate flag.

## Discovered follow-up work (not SBGC-62 blockers)

- **SBGC-182 — Game Deletion Workflow** (SBGC-6 epic): owns deliberate
  deletion semantics (hard delete vs alternatives, cascade behavior,
  classification relationships, source behavior, confirmation/safety UX,
  referential integrity, listing/publication implications, manual/Steam
  parity).  This is the remaining task needed to close SBGC-6 after
  SBGC-62.
- **SBGC-183 — Implement Scheduled Steam Metadata Refresh** (SBGC-8 —
  Django Admin Configuration & Jobs/Schedulers): discovered future-work gap
  for a daily scheduled Steam-only refresh with bounded retries, current-run
  audit artifact, and operator failure notification.  Not a blocker to
  SBGC-62 or SBGC-6.
