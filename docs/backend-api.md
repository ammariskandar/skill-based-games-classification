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
| Games             | `games/api.py`                  | Games            | Steam import + refresh (SBGC-57); public game detail (SBGC-71) |
| Classifications   | `classifications/api.py`        | Classifications   | No operations yet |

Routers own domain-specific endpoints.  Domain models and services are
implemented (SBGC-45 through SBGC-56).  SBGC-57 added authorized Steam
import and refresh mutations on the Games router:
`POST /api/v1/games/steam/import` and
`POST /api/v1/games/{game_id}/steam/refresh` — see `docs/steam-api.md`.
SBGC-71 added the public read endpoint `GET /api/v1/games/{slug}` — see the
Game detail section below.

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
`content_type`, `description` (manual/editorial description), `release_date`,
`developer`, `image_url` (canonical `display_image_url`), and
`metadata_updated_at`.  Steam Games additionally expose the optional
`library_hero_url` and `library_capsule_url` (both `null` for Manual Games and
for Steam content without Library artwork) for the SBGC-184 layered Game-detail
presentation.

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

- **Game detail delivered; catalogue/search/ranking reads deferred.** SBGC-71
  added `GET /api/v1/games/{slug}`.  Catalogue, search, and ranking read
  endpoints remain deferred to SBGC-10/SBGC-11.
- **No global authentication backend.** Session auth is opt-in per operation
  via `auth=django_auth`; there is no project-wide auth middleware.
- **Method-not-allowed returns HTML.** Documented framework limitation
  for Django Ninja 1.6.2.
- **CORS deny-by-default** — No browser-to-Django CORS configuration
  exists; architecture uses Astro SSR as intermediary.
