# Steam API — SBGC-57

Authorized HTTP endpoints that expose the SBGC-54 Steam import service and the
SBGC-56 Steam metadata refresh service over Django Ninja.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/games/steam/import` | Import (or re-import) one Steam App ID |
| `POST` | `/api/v1/games/{game_id}/steam/refresh` | Refresh one canonical Steam Game from Steam |

Both are mounted on the existing Games router (`games/api.py`), which is
registered at `/games/` in `api/v1.py`. There is no unversioned route and no
duplicate router.

## Authorization

Both endpoints mutate canonical Games and may trigger outbound Steam calls, so
they require an **authenticated staff session**.

- Authentication: Django session authentication (`auth=django_auth`, Ninja's
  built-in `SessionAuth`).
- Authorization: `request.user.is_staff` enforced in the handler via
  `_require_staff`.

| Caller | Result |
|--------|--------|
| Anonymous | `401 AUTHENTICATION_ERROR` (automated tests, CSRF-isolated) |
| Authenticated non-staff | `403 AUTHORIZATION_ERROR` |
| Authenticated staff / superuser | authorized |

Service code remains authorization-free — authorization lives only at the HTTP
boundary.

> CSRF nuance: because Ninja checks CSRF **before** session authentication,
> an anonymous POST in the real HTTP flow (with CSRF enforced) surfaces as
> `403` with `CSRF check Failed`, not `401`. The `401` for anonymous is proven
> in the automated test suite using the Django test client (which bypasses
> CSRF by default), while a dedicated test proves CSRF → `403`. This is the
> framework's actual semantics and is preserved deliberately.

## CSRF

Django Ninja marks its views `csrf_exempt` at the Django middleware level, so
CSRF is enforced through Ninja's session-auth mechanism (`SessionAuth`, which
extends `APIKeyCookie` with `csrf=True`).

- No global CSRF disable.
- No endpoint-specific CSRF exemption.
- No bypass header.

A session-authenticated mutation request must send the `X-CSRFToken` header
with the current `csrftoken` cookie value. See
`docs/postman-steam-integration.md` for the full flow.

## Import request schema

```json
{ "app_id": "620" }
```

- `app_id` is a **string** (the domain `SteamAppId` contract is a decimal-digit
  string). Integers, booleans, `null`, arrays, and objects are rejected by the
  request schema (`422 VALIDATION_ERROR`).
- Extra/unknown fields are rejected (`ApiRequestSchema` uses `extra="forbid"`).
- Domain-level invalid App IDs (non-decimal strings) are rejected by
  `SteamImportFoundation` and mapped to `400 BAD_REQUEST`.

## Import response

```json
{
  "status": "created | updated | unchanged | unavailable",
  "app_id": "620",
  "game": { "...": "GameSummary" }
}
```

- `CREATED` → `201`; `UPDATED` / `UNCHANGED` / `UNAVAILABLE` → `200`.
- `game` is a `GameSummary` for `CREATED`/`UPDATED`/`UNCHANGED` and `null` for
  `UNAVAILABLE` (no Game is invented).

## Refresh request contract

The Game is identified by its internal primary key in the path. There is no
body and no App-ID override — the persisted `Game.external_id` is the only
Steam identity used.

```text
POST /api/v1/games/{game_id}/steam/refresh
```

The handler resolves the canonical Game (`404 NOT_FOUND` if missing), authorizes,
delegates to `SteamGameRefreshService.refresh(game)`, and maps the result.

## Refresh response

```json
{
  "status": "updated | unchanged | unavailable",
  "game": { "...": "GameSummary" },
  "changed_fields": ["name"]
}
```

`changed_fields` is empty for `unchanged`/`unavailable`. `GameSummary` includes
`last_steam_refresh_at`, which is set on successful (`updated`/`unchanged`)
verifications and unchanged on `unavailable`.

## GameSummary

A small reusable canonical Game summary exposed by the mutation endpoints:

```text
id, source_type, external_id, name, slug, content_type, listing_status,
steam_image_url, last_steam_refresh_at
```

Excluded deliberately:

- manual/editorial metadata (`manual_*`);
- unpersisted Steam DTO metadata (`short_description`, `website_url`,
  `is_free`, `developers`, `publishers`);
- internal ORM internals and raw Steam JSON.

## Service delegation

The HTTP layer stays thin. It does not own Steam payload parsing, `SteamClient`
usage, DTO construction, slug allocation, persistence, transaction policy,
image validation, or refresh mapping. Composition factories
(`_build_steam_import_service` / `_build_steam_refresh_service` in
`games/api.py`) build the existing services lazily; tests patch these factories.

```text
HTTP → Ninja schema → session auth (CSRF) → is_staff → thin handler
     → SteamGameImportService / SteamGameRefreshService → result → response schema
```

## Status / error mapping

| Condition | HTTP | `error.code` |
|-----------|------|--------------|
| Schema validation (missing/null/non-string/extra `app_id`) | 422 | `VALIDATION_ERROR` |
| Invalid Steam App ID string | 400 | `BAD_REQUEST` |
| Not authenticated | 401 | `AUTHENTICATION_ERROR` |
| Authenticated non-staff | 403 | `AUTHORIZATION_ERROR` |
| CSRF failure | 403 | framework mapping |
| Game not found (refresh) | 404 | `NOT_FOUND` |
| Manual Game / identity violation / missing row | 400 | `BAD_REQUEST` |
| Steam rate limited | 429 | `RATE_LIMITED` |
| Steam transport / data failure (timeout, connection, malformed, upstream, too large, auth, not found, redirect) | 503 | `SERVICE_UNAVAILABLE` |
| Unexpected failure | 500 | `INTERNAL_SERVER_ERROR` |

`Steam app unavailable` (`success=false`) is a **domain outcome** — it maps to
an import/refresh `status` of `unavailable`, never a `500`. Technical Steam
failures (timeout, malformed, rate limit, upstream) are never collapsed into
`unavailable`; they surface as the errors above.

Errors are mapped through the centralized `api/errors.py` infrastructure
(`ApiException` or the registered Steam error mapping in `games/api.py`), never
through endpoint-local JSON. Response payloads expose only `code`/`message`/
`details`; no tracebacks, Steam bodies, file paths, or secrets.

## OpenAPI

The endpoints appear in `/api/v1/openapi.json` with their methods, request
schemas (`SteamImportRequest`), response schemas (`SteamImportResponse`,
`SteamRefreshResponse`, `GameSummary`), and declared status codes including
`422`.

## Scope exclusions

No frontend UI, image fetching/proxy, scheduled refresh, background tasks,
bulk import/refresh, Steam search, developer/publisher normalization, or
production deployment. Listing/classification behavior is unchanged.

## SBGC-58 handoff

SBGC-58 performs the controlled live Steam end-to-end validation through:

```text
Postman → authorized HTTP API → Steam service → Steam → persistence → API response
```
