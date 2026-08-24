# Frontend API Layer

Server-side API client for communicating with the Django backend from Astro SSR routes.

## Architecture

```
Browser  →  Astro SSR (server)  →  Django API
                ↑
        API layer lives here
```

- Astro server routes (frontmatter, API endpoints) consume Django through this shared client.
- Ordinary browser code does **not** call Django directly by default.
- The API layer owns base URL configuration, timeout, transport, and normalized error handling.
- `DJANGO_API_URL` is read from the server environment only — it is **never** prefixed with `PUBLIC_` and never exposed to browser bundles.

## Source Layout

```
apps/frontend/src/lib/server/api/
├── client.ts    # fetch-based transport, getJSON, postJSON
├── errors.ts    # Normalized error factory
├── types.ts     # ApiResult<T>, ApiError, request options
├── games.ts     # getGameDetail / getHomepageCarousel / getGameCatalogue + DTO types + error classes
└── index.ts     # Public re-exports
```

## Generic Result Contract

Every API call returns `ApiResult<T>`:

```typescript
type ApiResult<T> =
  | { ok: true;  data: T; status: number }   // success with data
  | { ok: true;  status: 204 }               // success, no content
  | { ok: false; error: ApiError; status?: number }  // failure
```

204 responses are `ApiNoContent` — no `data` field exists. Callers must check `"data" in result` before accessing `result.data` when 204 is possible. Callers narrow on `result.ok` — no manual HTTP status checking required.

## DJANGO_API_URL Contract

- **Required.** Must be a valid absolute HTTP or HTTPS URL.
- **Origin-only.** No path, query string, fragment, username, or password.
- Validated at request time (not module import) — static pages build without a local `.env`.
- Invalid values produce `CONFIG_ERROR`, not `NETWORK_ERROR`.

## URL Construction

- Callers supply **relative API paths only** (`/api/games`, `/api/search`).
- Rejected: empty strings, paths without leading `/`, protocol-relative URLs (`//evil.com`), absolute URLs, scheme-prefixed URLs, fragments.
- Path traversal outside the base origin is rejected (`new URL("../outside", base)` is checked).
- Query parameters are constructed via `URLSearchParams`.
- Paths containing existing `?` are handled with `&` joiner.

## Redirect Policy

Redirects are **rejected**. The client uses `redirect: "manual"` — 301, 302, 303, 307, and 308 responses are classified as `REDIRECT` errors. The redirect response body is consumed before the error is returned. POST bodies are never silently redirected to GET.

## Timeout & Cancellation

- Default timeout: 8 seconds. Overridable via `timeoutMs` (must be a positive integer).
- Timeout is active through the **entire operation lifetime**: fetch → response headers → body reading → JSON parsing.
- Cleanup (timer clearing, listener removal) runs after every return or throw path.
- Pre-aborted caller `AbortSignal` returns `ABORTED` immediately before fetch.
- Caller abort and internal timeout are cleanly distinguished via flags, not fragile signal-state checks.
- No automatic retries. Write requests are never retried.

## Response Body Cleanup

Every response path **consumes or cancels its body**:
- Successful JSON → parsed
- Non-JSON success → body drained, `INVALID_RESPONSE` returned
- Non-2xx → body drained, `HTTP_ERROR` returned
- Redirect → body drained, `REDIRECT` returned
- 204 → body drained, `ApiNoContent` returned
- Empty body → `INVALID_RESPONSE` returned
- Body-read failure → `INVALID_RESPONSE` (or `TIMEOUT`/`ABORTED` if cancelled during read)

No path relies on garbage collection for connection cleanup.

## Media Type Validation

Response `Content-Type` is parsed case-insensitively. Accepted: `application/json` and `application/*+json`. Parameters (e.g. `charset`) are stripped before matching. Non-JSON responses (HTML, text) are drained and classified as `INVALID_RESPONSE`.

## Headers

Headers are merged via the `Headers` constructor for case-insensitive semantics. Defaults: `Accept: application/json`. `Content-Type: application/json` is added only when a request body is present and the caller hasn't set a Content-Type. Caller headers override defaults.

## Request Body Serialization

Body serialization (`JSON.stringify`) runs **before** the network attempt. Cyclic values, BigInt, or other serialization failures produce `REQUEST_SERIALIZATION` errors — they are never classified as network errors.

## Error Categories

| Code                   | Meaning                                     |
| ---------------------- | ------------------------------------------- |
| `CONFIG_ERROR`         | Invalid `DJANGO_API_URL`, path, or timeout value |
| `REQUEST_SERIALIZATION`| Failed to `JSON.stringify` the request body |
| `TIMEOUT`              | Operation exceeded `timeoutMs` (including body read) |
| `ABORTED`              | Caller cancelled via `AbortSignal`          |
| `NETWORK_ERROR`        | DNS failure, connection refused, TLS error   |
| `REDIRECT`             | Server returned 3xx — not followed          |
| `HTTP_ERROR`           | Non-2xx, non-3xx response from Django       |
| `INVALID_RESPONSE`     | Non-JSON body, empty body, parse error, body-read failure |
| `UNKNOWN_ERROR`        | Final fallback for genuinely unclassified failures |

Each `ApiError` has:
- `code` — machine-readable, stable
- `message` — human-readable, safe (no secrets, stack traces, raw HTML)
- `cause?` — diagnostic context (logging only, **never displayed to users**). Present only for internal exceptions (network errors, JSON parse failures, body serialization). It **never** contains raw backend response bodies, HTML, debug output, or stack traces.

The `status` field lives on `ApiFailure`, not `ApiError` — it is set by the transport layer when the server responded.

## No Runtime Schema Validation

TypeScript types describe expected shapes at compile time. They do **not** validate untrusted JSON at runtime. Django is the authoritative source of truth.

## Endpoint-Specific Types

`games.ts` defines the SBGC-71 game-detail DTO types (`GameDetailResponse`, `GameDetailGame`, `GameFinalClassification`, `ClassificationProfile`, `GameSource`, `ClassificationRegime`) and two typed errors: `GameNotFoundError` (Django 404) and `BackendApiError` (any other failure). It also defines the SBGC-189 homepage carousel boundary (`getHomepageCarousel`, `HomepageCarouselCard`), the SBGC-76/SBGC-79 catalogue boundary (`getGameCatalogue`, `GameCatalogueResponse`, `GameCatalogueItem`, `GameCatalogueClassification`, `GameCatalogueQuery`, plus the SBGC-79 `CatalogueSort`/`CatalogueProfile`/`CatalogueDominant` identifiers), and the SBGC-78 search-index boundary (`getGameSearchIndex`, `GameSearchIndexItem`, `GameSearchIndexResponse`).

## Route Integration

The `/games/[slug]` route (SBGC-72) imports `getGameDetail()` from this layer:
- Call it from Astro frontmatter (server-side).
- Catch `GameNotFoundError` to render a real 404 (rewrite to `404.astro` with a 404 status).
- Catch every other failure (`BackendApiError` — timeout, network, Django 5xx, malformed/empty response) and render a friendly service-failure state with a real 500 status. Never a 404, and never a 200 "error page".
- Unhandled render errors fall through to the native `500.astro` error page.
- Never display raw `ApiError` content that may contain backend context directly in public UI.

### Catalogue route (SBGC-77/SBGC-78/SBGC-79)

The `/catalogue` route imports `getGameCatalogue()` from this layer:
- Call it from Astro frontmatter (server-side) with the parsed query state —
  `{ page, q, source, classified, sort, profile, dominant, coverlessLast }`.
  The page-size default (24) stays with Django; `q` is the SBGC-78 name search;
  `source`/`classified`/`sort`/`profile`/`dominant`/`coverlessLast` are the
  SBGC-79 filters/sort.  `coverlessLast` is only sent when explicitly `false`
  (the backend defaults to true).
- The endpoint is mounted at `/api/v1/games/` **with the trailing slash**; the client path preserves it.
- Any failure (timeout, network, Django 5xx, malformed/empty response) throws `BackendApiError` and renders a real HTTP 500 service-failure state — never an empty-catalogue state, never a 200 error page.
- A valid-but-empty result (`count === 0`) and a valid page-beyond-the-end (`count > 0`, `results: []`) are ordinary 200 responses rendered as distinct truthful empty states, not errors. The full query state is preserved across pagination and recovery links via `catalogueHref`/`catalogueHrefFromState` (`src/lib/catalogue-presentation.ts`).

### Search index (SBGC-78)

`getGameSearchIndex()` fetches the complete compact public index from Django
(`GET /api/v1/games/search-index`) — used only by the server-side Astro proxy
route `/api/search-index`. The **browser** never calls Django directly; the
client-side loader `src/lib/game-search-index.ts` fetches `/api/search-index`
and layers a memory cache, a versioned `sessionStorage` cache (15-minute TTL),
and a single in-flight Promise (so background preload and explicit Search open
never issue a duplicate request).

### Game-detail state matrix (SBGC-74)

| Upstream outcome | `getGameDetail` result | Page result |
| --- | --- | --- |
| Django 404 `GAME_NOT_FOUND` (unknown/hidden/draft/archived/non-game) | throws `GameNotFoundError` | HTTP 404 + `404.astro` |
| Django 5xx | throws `BackendApiError` (`HTTP_ERROR`) | HTTP 500 + service-failure state |
| Timeout | throws `BackendApiError` (`TIMEOUT`) | HTTP 500 + service-failure state |
| Network failure | throws `BackendApiError` (`NETWORK_ERROR`) | HTTP 500 + service-failure state |
| Malformed/empty response | throws `BackendApiError` (`INVALID_RESPONSE`) | HTTP 500 + service-failure state |
| 200 valid Game | returns `GameDetailResponse` | HTTP 200 + Game page |

- `classification: null` and legitimate non-ready classifications are **not errors**: they render the ordinary Game page at HTTP 200 with the unavailable/non-ready state.
- Stale classification renders the persisted scores plus a stale qualifier at HTTP 200.
- Service failure offers a plain `<a href={Astro.url.pathname}>Try again</a>` — no automatic retry, no backoff, no polling.

## Behavioural Tests

Transport hardening is complete (SBGC-160). Behavioural proof is provided by the Vitest transport test suite (SBGC-161) in `src/lib/server/api/__tests__/`. Tests use Vitest in Node environment with mocked `globalThis.fetch` — no real network requests are made. Covered behaviours: configuration validation, URL and path handling, redirect rejection, request serialization, headers, successful responses, 204 No Content, non-success HTTP statuses, media type handling, malformed JSON, timeout, caller cancellation, and no-retry guarantees. Run with `npm run test:frontend`.

## Human verification (SBGC-72)

Completed on the local dev servers (Django `runserver` + Astro `dev`). All three
checks passed: `/games/portal-2` returned a server-rendered 200 with the correct
Game and image; `/games/chess` (Manual, no classification) returned a valid 200
with no fabricated scores; and `/games/definitely-not-a-game` returned a real 404
via the custom not-found page with no backend JSON exposed.

## Human verification (SBGC-74)

Completed on the local dev servers (Django `runserver` + Astro `dev`). All four
checks passed: unknown/hidden slug → real 404 (no internal JSON, hidden and
unknown indistinguishable); backend unavailable → real 500 with a friendly retry
state (no stack trace/backend URL, restored after restarting Django + Retry);
missing-image/sparse/null/non-ready/stale fixtures → no broken image, modal omits
missing rows, no fake zeros, stale qualified; extreme/long fixtures + repeated
Game-Information open/close/Escape + resize/desktop/mobile/200% zoom → no
overflow/stuck dialog/client exception. A follow-up long-Game-name overflow in
the Editorial Classification admin was also fixed and re-verified.
