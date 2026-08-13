# Steam Import Workflow — SBGC-54

Canonical persistence boundary between SBGC-53's Steam endpoint adapters
and the `Game` model.

## Pipeline

```text
Steam App ID
  → SteamImportFoundation.prepare_candidate()   (network — no transaction)
  → SteamGamePersistenceService.persist()       (transaction — no network)
  → canonical Game row
```

Owned layers:

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Transport | `games/services/steam/client.py` | HTTP, retries, timeouts, error taxonomy (SBGC-42/168) |
| Adapter | `games/services/steam/adapters/app_details.py` | Store appdetails structural validation (SBGC-53) |
| Import foundation | `games/services/steam/import_foundation.py` | App-ID validation, fetch, candidate normalisation (SBGC-53) |
| Import orchestration | `games/services/imports/steam.py` | Lookup → persistence boundary (SBGC-54) |
| Persistence | `games/services/imports/steam.py` | Candidate → canonical `Game` row (SBGC-54) |

## Services

### `SteamGamePersistenceService.persist(candidate)`

Input: `SteamGameImportCandidate` (SBGC-53 DTO).  Output:
`SteamGameImportResult`.  **No network** — this layer never imports the
Steam transport, adapters, or HTTP machinery.

### `SteamGameImportService.import_app(app_id)`

Uses `SteamImportFoundation` for the network lookup, then delegates to
the persistence service.

## Transaction Boundary

Network work runs **before** any database transaction opens.  The
persistence service owns the only `transaction.atomic()` block in the
import path.  Tests prove `prepare_candidate()` never runs inside
`connection.in_atomic_block`.

## Result Statuses

`SteamGameImportStatus`:

| Status | Meaning | `game_id` |
|--------|---------|-----------|
| `CREATED` | New canonical Game persisted | required |
| `UPDATED` | Existing Steam Game refreshed | required |
| `UNCHANGED` | Existing Steam Game already matches | required |
| `UNAVAILABLE` | Steam reports `success=false` — no writes | `None` (enforced) |

`SteamGameImportResult` is an immutable dataclass enforcing these
invariants at construction.

## Field Ownership

Candidate → `Game` mapping:

| Game field | New import | Re-import |
|------------|------------|-----------|
| `source_type` | `steam` | untouched |
| `external_id` | `candidate.app_id` | untouched |
| `name` | `candidate.name` | updated when different |
| `content_type` | `candidate.content_type` (any canonical value, incl. `unknown`) | updated when different |
| `slug` | deterministic allocation (see below) | **preserved** |
| `listing_status` | default `draft` — imports never publish | **preserved** |
| `manual_description` / `manual_image_url` / `manual_website_url` | unset | **preserved** |
| `created_at` | set | **preserved** |
| `updated_at` | set | changes only when data changed |
| editorial classification | absent | **preserved** (parent, Challenge, Reward, notes, `updated_by`) |

**Steam-owned metadata is not persisted.**  `short_description`,
`header_image_url`, `website_url`, `is_free`, `developers`, and
`publishers` have no canonical `Game` fields yet.  They are neither
written into `manual_*` fields nor silently dropped into new schema —
image and metadata persistence belong to later tickets (SBGC-55/56).

## Identity

An existing Steam Game is matched **exclusively** through
`source_type=steam AND external_id=app_id`.  Name, slug, and title
similarity are never identity keys.  Manual Games are never merged,
converted, or modified by Steam imports.

## Slug Allocation

`build_steam_game_slug(name, app_id, ...)` — deterministic, no random
suffixes, never applied to existing Games:

1. `slugify(name)` — preferred when free;
2. `slugify(name)-steam-<app_id>` — when preferred is occupied (the
   app-ID suffix is never truncated away);
3. `steam-<app_id>` — fallback for blank slugified names (e.g.
   Unicode-only names) or when both candidates above are occupied.

Candidates are truncated to `Game.slug.max_length` (255).  If every
candidate is occupied the import raises `ValueError` — callers may
retry after resolving the collision; unrelated Games are never touched.

## Atomicity

All Game writes run inside one `transaction.atomic()` block:

- Validation failure → no new row / existing row unchanged.
- `ValidationError` and unexpected `IntegrityError` propagate — they are
  never swallowed as success.

## Concurrency

`game_unique_source_external_id` (a partial unique index on PostgreSQL)
is the authority for `(steam, app_id)` races.  When a concurrent import
wins, the loser's `IntegrityError` is caught **only when** the identity
row now exists; the loser then refreshes (or reports `UNCHANGED`) against
the winner's row.  One canonical Game survives; the caller always
receives a deterministic result.  Any other integrity failure propagates.

Verified on PostgreSQL 16 (`games/tests/test_import_concurrency.py`).

## Unavailable Apps

`LookupStatus.UNAVAILABLE` (`success=false`) returns
`SteamGameImportStatus.UNAVAILABLE` with `game_id=None`.  No writes.  An
existing Steam Game is never modified or deleted by an unavailable
lookup.

## Error Propagation

Transport and payload errors are never caught or downgraded:

```text
SteamMalformedPayloadError
SteamTimeoutError
SteamConnectionError
SteamAuthenticationError
SteamRateLimitedError
SteamUpstreamError
SteamInvalidResponseError
SteamResponseTooLargeError
```

Nothing is written when preparation fails.

## Not in Scope (SBGC-54)

- No public import API endpoint (Django Ninja)
- No Admin import action
- No management command
- No frontend import UI
- No Steam image fetching or CDN population
- No metadata refresh
- No bulk/multi-app lookup
- No live Steam calls — all tests use mocked foundation/adapters
