# Steam Metadata Refresh — SBGC-56

Manual metadata refresh for canonical Steam Games.

## Scope

SBGC-56 delivers:

- `SteamGameRefreshService` — the refresh application service;
- `Game.last_steam_refresh_at` — refresh tracking (NULL = never
  refreshed);
- a manual Django Admin action ("Refresh Steam metadata from Steam").

Not delivered (explicitly out of scope for SBGC-56): Ninja endpoints,
cron/Celery, background schedulers, bulk-refresh jobs, frontend UI.

Daily scheduled refresh on top of this same service is delivered by
**SBGC-183** — see [`docs/scheduled-steam-refresh.md`](scheduled-steam-refresh.md).

## Pipeline

```text
canonical Steam Game
  → eligibility + App-ID validation      (no network, no writes)
  → SteamImportFoundation.prepare_candidate()   (network, no transaction)
  → identity verification                (zero writes on mismatch)
  → transaction: shared field-mapping helper + save
  → SteamGameRefreshResult
```

The service reuses SBGC-54's `SteamGamePersistenceService` identity
lookup and the shared `_apply_steam_owned_updates()` helper — there is
exactly **one owner** of the Steam-owned field-mapping table for both
imports and refreshes.

## Eligibility

- Only `source_type == steam` Games may refresh (enforced through the
  shared `can_steam_refresh()` helper in `games/services/source_policy.py`,
  SBGC-61).
- A manual Game raises `SteamRefreshError` — no network call, no writes.
- The stored `external_id` is the **only** accepted App ID, validated
  through `SteamAppId`.  No replacement App IDs are accepted.

## Identity Invariant

The lookup result and the candidate must both carry the Game's stored
`external_id`.  Any mismatch raises `SteamRefreshError` with zero
writes.  `source_type`, `external_id`, and `id` can never be mutated by
refresh.

## Result

```python
SteamGameRefreshStatus: UPDATED | UNCHANGED | UNAVAILABLE

SteamGameRefreshResult(status, game_id, changed_fields=())
```

- `UPDATED` requires non-empty `changed_fields` (deterministic order:
  name, content_type, steam_image_url).
- `UNCHANGED` / `UNAVAILABLE` require empty `changed_fields`.
- Only Steam-owned field names are permitted in `changed_fields`.

## Fields Refreshed

| Field | Behavior |
|-------|----------|
| `name` | replaced when different |
| `content_type` | replaced when different (canonical value incl. `unknown`) |
| `steam_image_url` | SBGC-55 semantics: valid URL updates; `None`/blank preserves; malformed raises |
| `last_steam_refresh_at` | set on every successful verification (UPDATED and UNCHANGED) |

**Never refreshed:** slug, listing_status, `manual_*` metadata,
editorial classification (parent + Challenge + Reward + notes +
`updated_by`), `created_at`, `source_type`, `external_id`, `id`.

## DTO Fields Intentionally Not Persisted

The candidate DTO also carries `short_description`, `website_url`,
`is_free`, `developers`, and `publishers`.  SBGC-56 does **not** persist
these — the repository's recorded Jira scope covers safe field updates
of the fields above plus refresh tracking, and no Steam-owned schema
exists for them.  They are never written into `manual_*` fields.  A
future ticket that persists them must add explicit Steam-owned schema.

## Unavailable Apps

`LookupStatus.UNAVAILABLE` → `UNAVAILABLE` result.  The Game is
preserved completely: no deletion, archiving, metadata clearing,
listing-status change, classification change, or timestamp write.

## Error Propagation

Transport and adapter errors propagate unchanged:

```text
SteamMalformedPayloadError, SteamTimeoutError, SteamConnectionError,
SteamAuthenticationError, SteamRateLimitedError, SteamUpstreamError,
SteamInvalidResponseError, SteamResponseTooLargeError
```

Technical errors are never mapped to `UNAVAILABLE`.  Nothing is written
when preparation fails.

## Transaction Boundary

Network (`prepare_candidate`) runs strictly **before** any database
transaction opens.  Malformed candidate metadata raises before the
transaction as well.  The refresh transaction contains only field
mapping and one save (or, for `UNCHANGED`, a single queryset update).

## Unchanged Refresh & Timestamps

- `UNCHANGED`: no `Game.save()` — `updated_at` stays untouched.  The
  successful verification is still recorded via a queryset update of
  `last_steam_refresh_at` (queryset updates do not trigger
  `auto_now`).
- `UPDATED`: normal model save — `updated_at` changes and
  `last_steam_refresh_at` is set.
- `UNAVAILABLE` / errors: `last_steam_refresh_at` untouched.

## Listing Consequences

Refresh never changes `listing_status`.  If Steam reclassifies a
published GAME as DLC (or `unknown`), the record keeps `published` but
leaves `publicly_listable()` — publication is an editorial decision, not
derived from Steam.

## Concurrency

No locking or versioning was added.  Each refresh writes only
Steam-owned fields under a short transaction; concurrent
last-write-wins refreshes cannot violate the identity, slug, listing,
or classification invariants (none of those are written).  No
PostgreSQL-specific semantics were introduced.

## Admin Action

`GameAdmin` exposes "Refresh Steam metadata from Steam":

- manual Games are skipped **without** any network call;
- outcomes are summarized (updated/unchanged/unavailable/manual
  skipped);
- known Steam errors (`SteamRefreshError`, adapter errors, transport
  errors) are reported per game and the remaining games still refresh;
- unexpected exceptions propagate (fail loudly);
- the action performs real network calls in production — automated
  tests patch the composition factory (`games.admin._build_steam_refresh_service`).

## Scheduled refresh (SBGC-183)

The scheduled daily refresh uses the **same** `SteamGameRefreshService` through
the shared composition root `games/services/imports/factory.py`. The scheduler
never calls the Admin action; both depend on the refresh service. See
[`docs/scheduled-steam-refresh.md`](scheduled-steam-refresh.md) for the
scheduling, retry, audit, concurrency, and alerting contract.

## SBGC-57 Handoff

SBGC-57 added the authorized HTTP surface over both
`SteamGameRefreshService` and `SteamGameImportService`:

```text
POST /api/v1/games/steam/import
POST /api/v1/games/{game_id}/steam/refresh
```

See `docs/steam-api.md` and `docs/postman-steam-integration.md`.
