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
| Metadata refresh | `games/services/imports/steam.py` | Existing Steam Game → verified metadata update (SBGC-56) |

## Services

### `SteamGamePersistenceService.persist(candidate)`

Input: `SteamGameImportCandidate` (SBGC-53 DTO).  Output:
`SteamGameImportResult`.  **No network** — this layer never imports the
Steam transport, adapters, or HTTP machinery.

### `SteamGameImportService.import_app(app_id)`

Uses `SteamImportFoundation` for the network lookup, then delegates to
the persistence service.

### `SteamGameRefreshService.refresh(game)` — SBGC-56

Refreshes an existing Steam Game: eligibility, network lookup outside
any transaction, identity verification, then the shared
`_apply_steam_owned_updates()` mapping.  See
`docs/steam-metadata-refresh.md`.

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
| `steam_image_url` | validated `candidate.header_image_url`, else empty | updated only by a validated URL; `None`/blank preserves; malformed raises (SBGC-55) |
| `slug` | deterministic allocation (see below) | **preserved** |
| `listing_status` | default `draft` — imports never publish | **preserved** |
| `description` / `developer` / `release_date` | populated (SBGC-188) | refresh honours per-field override flags |
| `manual_image_url` / `manual_website_url` | unset | **preserved** |
| `created_at` | set | **preserved** |
| `updated_at` | set | changes only when data changed |
| editorial classification | absent | **preserved** (parent, Challenge, Reward, notes, `updated_by`) |

**Steam-owned metadata beyond description/developer/release_date and the image
URL is not persisted.** `website_url`, `is_free`, and `publishers` have no
canonical `Game` fields yet.  They are neither written into manual fields nor
silently dropped into new schema.  Image handling is documented in
`docs/steam-images.md`.

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

Two distinct races are handled, both verified on PostgreSQL 16
(`games/tests/test_import_concurrency.py`):

### Identity race — same App ID

`game_unique_source_external_id` (a partial unique index on PostgreSQL)
is the authority for `(steam, app_id)` races.  When a concurrent import
wins, the loser's `IntegrityError` is caught **only when** the identity
row now exists; the loser then refreshes (or reports `UNCHANGED`)
against the winner's row.  One canonical Game survives; the caller
always receives a deterministic result.

### Slug race — distinct App IDs, same name

Two imports with different App IDs and the same name may compute the
same preferred slug before either INSERTs.  The loser's INSERT fails on
the unique slug index.  Recovery is attempted **only** when:

1. no identity row exists (not an identity race), and
2. the computed slug is now occupied (not an unrelated failure).

Then the slug is recomputed deterministically (preferred → suffixed →
fallback) and the INSERT retried **once**.  Both canonical identities
persist exactly once, e.g. `A → same-name` and `B → same-name-steam-<B>`
(or the inverse).

Any other integrity failure — no identity row and no occupied slug —
propagates unchanged.

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

- No Admin import action
- No management command
- No frontend import UI
- No Steam image fetching or CDN population
- No metadata refresh
- No bulk/multi-app lookup
- No live Steam calls — all tests use mocked foundation/adapters

## SBGC-57 API surface

The authorized HTTP import endpoint (`POST /api/v1/games/steam/import`)
wraps `SteamGameImportService.import_app` — see `docs/steam-api.md`.
