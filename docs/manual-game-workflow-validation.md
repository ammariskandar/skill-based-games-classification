# Manual Game Workflow Validation — SBGC-62

Verification evidence for manual (non-Steam) Game workflows implemented in
SBGC-59/60/61.

## Environment

- Automated tests: in-memory SQLite (`config.settings.test`).
- Local development DB: SQLite (`apps/backend/db.sqlite3`).
- No Neon, no Render, no production/shared DB, no Steam network.
- Human Admin validation: pending at the time of writing.

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

## Human validation checklist

1. Start the local development server against local SQLite.
2. Log into the configured Django Admin.
3. Create a temporary manual Game.
4. Enter name, slug, content type, listing status, release date, developer,
   description, valid HTTPS image URL, and website URL.
5. Save and confirm source is Manual and external ID is empty.
6. Edit name and confirm slug stays unchanged unless explicitly edited.
7. Replace then clear the manual image URL.
8. Enter an invalid image URL and confirm a validation error (no traceback).
9. Confirm source/external ID are readonly.
10. If a classification exists, edit metadata and confirm scores/notes remain
    unchanged.
11. Set a manual GAME to Published and confirm it is publicly listable.
12. Confirm a Published manual non-Game remains excluded.
13. Confirm no raw traceback.

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
