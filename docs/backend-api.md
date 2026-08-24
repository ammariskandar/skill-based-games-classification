# Backend API

Django Ninja API for the MyGameDNA skill-based games classification platform.

## API Version

| Attribute       | Value             |
| --------------- | ----------------- |
| Product name    | MyGameDNA API     |
| Version         | 1.0.0             |
| URL prefix      | `/api/v1/`        |
| OpenAPI schema  | `/api/v1/openapi.json` |
| Interactive docs| `/api/v1/docs` (development only) |

One `NinjaAPI` instance is created per major API version. The current v1
instance lives at `api/v1.py`.

## Architecture

```
Browser  →  Astro SSR  →  frontend transport  →  /api/v1/  →  Django Ninja
```

- **One server API path.** Browser code never calls Django directly.
- **One `NinjaAPI` per major version.** New major versions create a new instance;
  minor additions extend the existing routers.

## Router Ownership

| Router            | Module                          | Tag              | Status            |
| ----------------- | ------------------------------- | ---------------- | ----------------- |
| System            | `api/system.py`                 | System           | `GET /` active    |
| Games             | `games/api.py`                  | Games            | Steam import + refresh (SBGC-57); public game detail (SBGC-71); homepage carousel (SBGC-189) |
| Classifications   | `classifications/api.py`        | Classifications   | No operations yet |

Routers own domain-specific endpoints.  Domain models and services are
implemented (SBGC-45 through SBGC-56).  SBGC-57 added authorized Steam
import and refresh mutations on the Games router:
`POST /api/v1/games/steam/import` and
`POST /api/v1/games/{game_id}/steam/refresh` — see `docs/steam-api.md`.
SBGC-71 added the public read endpoint `GET /api/v1/games/{slug}` — see the
Game detail section below. SBGC-189 added `GET /api/v1/games/homepage` for the
homepage Steam carousel — see the Homepage Carousel section below.

## Request Schemas

All request schemas inherit from `ApiRequestSchema`, which configures
Pydantic v2 to **reject unknown/extra fields** (`extra="forbid"`).
Misspelled or unsupported keys produce a `VALIDATION_ERROR` rather than
being silently ignored.

## Response Schemas

Every endpoint explicitly declares its response schema. No endpoint returns
untyped `dict` or raw Django models. Use `ninja.Schema` subclasses, not
`ModelSchema`, until database models exist.

### Standard Error Responses

All endpoint operations must include standard error-response declarations:

```python
from api.errors import STANDARD_ERROR_RESPONSES

@router.get("/path", response={200: SomeSchema, **STANDARD_ERROR_RESPONSES})
```

`STANDARD_ERROR_RESPONSES` maps Django Ninja's grouped `codes_4xx` and
`codes_5xx` status-code sets (`frozenset` objects from `ninja.responses`)
to `ApiErrorResponse`, producing correct OpenAPI error documentation with
concrete HTTP status codes (400, 401, 403, 404, 500, 503, etc.) rather than
invalid group keys "4" and "5" — SBGC-167.

**Note:** Django Ninja's `codes_4xx` does **not** include 422 (Unprocessable
Entity).  Endpoints that return explicit 422 responses must declare it
separately alongside `STANDARD_ERROR_RESPONSES`:

```python
@router.get("/endpoint", response={
    200: SuccessSchema,
    **STANDARD_ERROR_RESPONSES,
    422: ApiErrorResponse,
})
```

The explicit int key `422` does not collide with the `codes_4xx` frozenset
key — they are distinct dictionary keys.  Framework validation-error handlers
return 422 directly through the Ninja exception-handler path and do not rely
on the operation response declaration.

### Response Status Codes

Use `Status(status, body)` from `ninja` for explicit non-default statuses.
Do not use the deprecated `(status, body)` tuple syntax.

## Game Catalogue — `GET /api/v1/games/`

Returns a deterministic, paginated list of publicly-listed base Games
(`content_type == game AND listing_status == published`).  It is **read-only**:
it never contacts Steam, never probes images, and never recalculates
classification.  Draft/archived and non-game content (DLC, demo, software,
soundtrack, unknown) are excluded from both `results` and `count`.

### Query parameters

| Parameter | Type | Default | Meaning |
|-----------|------|---------|---------|
| `q` | string | — | case-insensitive `name` substring search (trimmed; whitespace-only is no filter) |
| `source` | `steam` / `manual` | — | restrict to one source; omitted means both |
| `classified` | boolean | — | `true` = has a current published READY classification; `false` = no displayable scores |
| `sort` | `name_asc` / `name_desc` / `recent` / `micro` / `mystiko` / `macro` | `name_asc` | primary sort (see below) |
| `profile` | `challenge` / `reward` | `challenge` | explicit profile for `micro`/`mystiko`/`macro` sort and the `dominant` filter |
| `dominant` | `micro` / `mystiko` / `macro` | — | dominant-category filter against the published current READY snapshot (strictly-highest wins; top-score ties match none) |
| `coverless_last` | boolean | `true` | outer partition before pagination: Games without an effective Capsule go after Games with one |
| `page` | positive int | `1` | 1-based page number |
| `page_size` | positive int | `24` | results per page (max `100`) |

Filters are AND-composed.  `classified=true` means the Game currently has a
current `ClassificationSnapshot` with `status == READY` (including a stale
READY result retained after an engine/system failure); every other state —
`NO_SNAPSHOT`, a current non-READY domain status, etc. — is `classified=false`.
This matches the published-read semantics of the Game-detail endpoint and is
driven by persisted state, never by a recalculation.

### Primary sort

`sort` selects the primary order; deterministic tie-breakers always apply.

- `name_asc` (default) → `name ASC, id ASC`.
- `name_desc` → `name DESC, id ASC`.
- `recent` → `created_at DESC, name ASC, id ASC` (`recent` keys off
  `Game.created_at`, **not** `release_date`).
- `micro` / `mystiko` / `macro` → the selected `profile`'s published current
  READY unified-integer score, highest first; Games without a usable READY
  score sort after scored Games, then `name ASC, id ASC`.

Score sorting reads `ClassificationSnapshot.unified_integer_{challenge,reward}`
(canonical order `[micro, macro, mystiko]`) from the current READY snapshot only
— never the editorial submission tables, never raw Method 1/2/3 results.

### Dominant-category filter

`dominant` filters against the selected `profile`'s published current READY
snapshot.  Dominance is **strictly highest** (the canonical
`classifications.skills.dominant_skill_category` rule): a top-score tie has no
dominant category and therefore matches no `micro`/`mystiko`/`macro` filter.

### Cover-last partition

When `coverless_last=true` (the default), Games with an effective Capsule URL
(Steam manual-override-else-Library-Capsule; Manual manual Capsule — SBGC-190)
come before Games without one, **before** the count/pagination slice, so the
policy is globally correct across pages.  This outer partition is applied on top
of whichever primary sort is selected.  A general/header image is **not** a
Capsule.  `coverless_last=false` removes the partition and lets the primary sort
govern the whole population.

### Response envelope

```json
{
  "count": 42,
  "page": 1,
  "page_size": 24,
  "total_pages": 2,
  "results": [
    {
      "slug": "hades",
      "name": "Hades",
      "source": "steam",
      "image_url": "https://...",
      "library_capsule_url": "https://...",
      "classification": {
        "status": "READY",
        "challenge": {"micro": 51, "macro": 31, "mystiko": 18},
        "reward": {"micro": 17, "macro": 29, "mystiko": 54},
        "confidence_level": 85.5,
        "confidence_label": "High",
        "is_stale": false
      }
    }
  ]
}
```

`count` is the filtered count; `total_pages` is `0` when `count` is `0`.
Ordering is deterministic: the default primary sort is `name ASC, id ASC`;
skill sorts order by the published READY score descending with unscored Games
last; and `coverless_last=true` applies a cover-last outer partition before
pagination.  A page beyond the final page returns `200` with `results: []`.
`image_url` and `library_capsule_url` are effective values (manual override
first, Steam fallback — SBGC-190); the frontend never resolves override
precedence.  `classification` is `null` when the Game has no displayable scores
(no fake zero vectors).

## Public Game Detail — `GET /api/v1/games/{slug}`

Returns the normalized public identity and persisted metadata for one
publicly-listed base Game, plus its currently persisted Final Classification
(if any).  It is a **read-only** endpoint: it never contacts Steam, never
refreshes metadata, and never recalculates classification.

### Public eligibility

A Game resolves only when it is **publicly listable** — the canonical
`Game.objects.publicly_listable()` policy:

```text
content_type == game AND listing_status == published
```

Steam and Manual Games are both canonical Games and share this endpoint.
Slug is the lookup key (`Game.slug` is globally unique).

### 404 behavior

Unknown slug, hidden/draft, archived, and non-game content (dlc, demo,
software, soundtrack, unknown) all return identically:

```json
404 GAME_NOT_FOUND
```

A hidden record is indistinguishable from a missing one publicly.

### Game payload

The `game` object exposes the public subset: `id`, `slug`, `name`, `source`
(`steam` / `manual`), `external_id` (Steam App ID, or `null` for Manual),
`content_type`, `description` (Steam-populated for Steam Games unless
overridden in Admin; manual for Manual Games), `release_date`, `developer`,
`image_url`, and `metadata_updated_at`.

The three artwork fields are **effective** values (SBGC-190) — Django resolves
manual-override precedence, so the frontend never does `manual ?? steam`:

- `image_url` — effective general/header image (`manual_image_url` overrides
  `steam_image_url` for Steam Games);
- `library_hero_url` — effective Hero (`manual_hero_url` overrides the Steam
  Library Hero);
- `library_capsule_url` — effective Capsule (`manual_capsule_url` overrides the
  Steam Library Capsule).

These are `null` when no effective value exists (for example, a Manual Game
with no manual Hero/Capsule, or a Steam Game with neither Steam nor manual
Library artwork).

### Classification payload

`classification` is `null` when no Final Classification record exists.
Otherwise it exposes the persisted current published result:

- `status` — the canonical calculation status (`READY`, `NO_SUBMISSIONS`,
  `INSUFFICIENT_ANCHOR`, …);
- `regime` — `provisional`, `unified`, or `none`;
- `challenge` / `reward` — `{micro, macro, mystiko}` when published, `null`
  when the status is a legitimate non-ready domain outcome;
- `confidence_level` / `confidence_label`;
- `submission_count`, `calculation_version`, `calculated_at`, `is_stale`.

No scores are fabricated for non-ready statuses, and a non-ready result is
returned as-is (never converted to `404` and never replaced by a stale score).

### Human verification

Completed on local SQLite (no live Steam, no engine run). All three checks
passed: a public classified Game returned 200 with normalized fields and the
persisted READY Challenge/Reward + confidence; a public Game without
classification returned `classification: null` (no fake zeros); and
hidden/non-game/unknown slugs returned `404 GAME_NOT_FOUND` with no
hidden-record disclosure.

## Game Search Index — `GET /api/v1/games/search-index`

Returns the **complete** compact public Game search index used by the frontend
header autocomplete (SBGC-78). It is **read-only**: it never contacts Steam,
never probes images, and never recalculates classification.

### Eligibility & ordering

A Game is included only when it is **publicly listable** — the canonical
`Game.objects.publicly_listable()` policy (`content_type == game AND
listing_status == published`). Both Steam and Manual Games are included;
draft/archived and non-game content (dlc, demo, software, soundtrack, unknown)
are excluded. A Game with no Capsule is still included (the autocomplete falls
back to a placeholder). Ordering is deterministic (`name ASC, id ASC`).

### Response

```json
{
  "games": [
    {
      "slug": "hades",
      "name": "Hades",
      "capsule_url": "https://...",
      "image_url": "https://..."
    }
  ]
}
```

- `capsule_url` — effective Capsule (`manual_capsule_url` overrides the Steam
  Library Capsule — SBGC-190), or `null` when absent;
- `image_url` — effective general image (thumbnail fallback), or `null` when
  absent.

Only the fields needed to render a suggestion are returned — no classification,
description, Hero, raw source fields, or override provenance.

## Homepage Carousel — `GET /api/v1/games/homepage`

Returns up to 10 randomly selected Games for the homepage Steam carousel. It is
**read-only**: it never contacts Steam and never recalculates classification.

### Eligibility

A Game is eligible only when it is:

```text
publicly_listable AND source_type == steam AND library_capsule_url != ""
```

`publicly_listable` is the canonical `content_type == game AND listing_status
== published` policy. Manual Games, non-game Steam content, hidden/draft/
archived Games, and Steam Games without a Library Capsule are excluded.

### Selection

Selection is a single `ORDER BY RANDOM()` limited to 10 rows. Random ordering
happens per request; if fewer than 10 eligible Games exist, the available count
is returned.

### Response

```json
{
  "games": [
    { "slug": "hades", "name": "Hades", "library_capsule_url": "https://..." }
  ]
}
```

Only the carousel card fields are returned — `slug`, `name`,
`library_capsule_url`. No classification objects are included.

Every error response follows this structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": [
      {
        "location": ["body", "field"],
        "message": "Field required",
        "type": "missing"
      }
    ]
  }
}
```

- **`code`** — machine-readable uppercase snake_case identifier.
- **`message`** — safe human-readable description. Never contains stack
  traces, exception class names, input values, or internal paths.
- **`details`** — always an array (empty `[]` when no per-field detail
  exists).

### Machine Codes

| Code                    | HTTP | Source                                    |
| ----------------------- | ---- | ----------------------------------------- |
| `VALIDATION_ERROR`      | 422  | Schema validation failure                 |
| `AUTHENTICATION_ERROR`  | 401  | Missing or invalid credentials            |
| `AUTHORIZATION_ERROR`   | 403  | Insufficient permissions                  |
| `NOT_FOUND`             | 404  | Resource not found                        |
| `GAME_NOT_FOUND`        | 404  | Public game not found (hidden/non-game/unknown) |
| `BAD_REQUEST`           | 400  | Generic client error                      |
| `METHOD_NOT_ALLOWED`    | 405  | HTTP method not supported                 |
| `CONFLICT`              | 409  | Resource conflict                         |
| `RATE_LIMITED`          | 429  | Too many requests                         |
| `SERVICE_UNAVAILABLE`   | 503  | Upstream or transient failure             |
| `HTTP_ERROR`            | 4xx/5xx | Unmapped HTTP error                  |
| `INTERNAL_SERVER_ERROR` | 500  | Unexpected exception                      |

Project code can raise `ApiException` with any custom code and status.

## Exception Handling

Exception handlers are registered once per `NinjaAPI` instance via
`api.errors.register_handlers()`. All handlers produce the standard
error envelope.

### Validation Errors

`ninja.errors.ValidationError` → 422 `VALIDATION_ERROR`. Details are
sanitised: only `location`, `message`, and `type` are returned. Input
values, Pydantic context, and documentation URLs are stripped.

### Authentication / Authorization

- `AuthenticationError` → 401 `AUTHENTICATION_ERROR`
- `AuthorizationError` → 403 `AUTHORIZATION_ERROR`

Generic safe messages are returned.  No global authentication backend or
middleware is configured; the SBGC-57 Steam mutation endpoints opt in to
Django session authentication via Ninja's `auth=django_auth` (session + CSRF)
and enforce `is_staff` authorization in the handler.

### Http404

Django's `Http404` → 404 `NOT_FOUND`. The requested path is not echoed.

### HttpError

`ninja.errors.HttpError` status codes are mapped to the corresponding
machine code. Unmapped 4xx/5xx statuses fall back to `HTTP_ERROR`.

### Unexpected Exceptions

All unhandled exceptions produce 500 `INTERNAL_SERVER_ERROR`. The full
exception and traceback are logged server-side. Exception class names,
messages, and stack traces are never returned to the client.

### Project ApiException

`api.errors.ApiException` allows endpoint code to raise deliberate,
safe errors with a custom code, message, status, and optional details.

## Unknown-Route Fallback

Requests to `/api/v1/<unknown>` return a standardised 404 envelope:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "API resource not found.",
    "details": []
  }
}
```

The submitted path is not echoed in the response.

## Method-Not-Allowed Behavior

HTTP method mismatches (e.g., `POST /api/v1/`) are handled by Django's
built-in URL routing layer before Ninja's dispatcher runs. The response
is Django's default 405 HTML page, not the standard JSON error envelope.

This is a documented framework limitation for Django Ninja 1.6.2. It is
not addressed through private Ninja internals or broad middleware.

## Interactive Documentation

- **Development:** Swagger UI is available at `/api/v1/docs` using
  self-hosted static assets from the `ninja` Django app. No external
  CDN dependencies.
- **Production:** Interactive docs are disabled (`docs_url=None`).
  The OpenAPI schema remains available at `/api/v1/openapi.json`.

Controlled by `NINJA_API_DOCS_ENABLED` in the settings module:
- `config.settings.development` → `True`
- `config.settings.production` → `False`
- `config.settings.base` → `False` (safe default)

## OpenAPI Schema

Available at `/api/v1/openapi.json` in both development and production.
Contains all registered endpoints, request/response schemas, tags,
and standard error-response declarations.

## Limitations

- **Rankings reads deferred.** Game detail (SBGC-71), homepage (SBGC-189),
  catalogue (SBGC-76/79), and search index (SBGC-78) reads are delivered.
  The rankings read endpoints remain deferred to SBGC-11.
- **No global authentication backend.** Session auth is opt-in per operation
  via `auth=django_auth`; there is no project-wide auth middleware.
- **Method-not-allowed returns HTML.** Documented framework limitation
  for Django Ninja 1.6.2.
- **CORS deny-by-default** — No browser-to-Django CORS configuration
  exists; architecture uses Astro SSR as intermediary.
