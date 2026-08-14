# Steam Live Integration Validation — SBGC-58

Controlled live validation of the authorized Steam import/refresh HTTP path
against the real Steam Store API.

## Environment

| Item | Value |
|------|-------|
| Date | 2026-08-15 |
| Settings | `config.settings.development` |
| Database | **local SQLite** (`apps/backend/db.sqlite3`) |
| Neon | **not used** |
| Render | **not used** |
| Live Steam | explicitly contacted via Postman → HTTP API |

## Tested Apps

| App ID | Game ID | Observed name | Observed Steam type | Mapped ContentType | Image host | Import | Re-import | Refresh |
|--------|---------|---------------|---------------------|--------------------|------------|--------|-----------|---------|
| 620 | 1 | Portal 2 | `game` | `game` | `shared.akamai.steamstatic.com` | re-import (pre-seeded row) | passed | passed |

The `620` record already existed in local SQLite as the seeded Portal 2
(`id=1`, `source_type=steam`), so the live import exercised the re-import
path rather than a fresh `CREATED` path. Import, re-import, and refresh all
passed.

## State preservation

The human confirmed the following were preserved across live refresh:

- canonical identity (`steam:620`, `id=1`)
- `slug` (`portal-2`)
- `listing_status`
- manual metadata (`manual_description`, `manual_image_url`,
  `manual_website_url`)
- editorial classification (Challenge + Reward profiles, notes, `updated_by`)

No unexpected `UPDATED` field was reported.

## Security

- Live import/refresh used the authorized path: session + CSRF +
  `is_staff`.
- Unauthorized rejection was verified in SBGC-57 Postman validation and
  remains covered by the automated `api/tests/test_steam_authorization.py`.
- No raw traceback, internal path, `urllib3` repr, raw Steam body, DB
  credential, or secret was observed in any response body.

## Payload compatibility

The live `620` payload was compatible with current adapter assumptions:

```text
root object → requested App ID key → success bool → data object → name → type
```

Optional fields observed live: `short_description`, `header_image`,
`website`, `is_free`, `developers`, `publishers`. These remain
intentionally unpersisted — no schema change was made.

## Image evidence

| App ID | Scheme | Hostname | Validator accepted | Persisted matches API |
|--------|--------|----------|--------------------|------------------------|
| 620 | `https` | `shared.akamai.steamstatic.com` | yes | yes |

> **Observed metadata host ≠ backend fetch authorization.** The backend CDN
> fetch allowlist was **not** modified, and no image was downloaded, proxied,
> or fetched.

## Limitations

- A fresh `CREATED` import was **not** directly observed via HTTP in this
  run because `620` was pre-seeded; the import exercised the re-import path.
- No non-Game (DLC/Demo) App ID was live-tested — no reliably-known stable
  fixture was identified, so that case is documented rather than guessed.
- `UNAVAILABLE` was not live-tested — it remains covered by deterministic
  mocked integration tests.
- Live request count was not tracked (skipped by user authority).
- Artificial failure modes (rate-limit, timeout, 5xx, malformed, oversized,
  bad content-type, redirect) were **not** live-tested; they belong to the
  controlled lower-layer transport/adapter test suites.

## Conclusion

The authorized application HTTP path was exercised end-to-end against the
live Steam Store API and successfully re-imported/refreshed the canonical
Portal 2 (`620`) record while preserving identity, slug, listing, manual
metadata, and editorial classification.

A fresh `CREATED` import and non-Game content-type mapping were not directly
re-verified live in this run and remain covered by deterministic tests.
