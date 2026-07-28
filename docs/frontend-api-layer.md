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

No domain types (`Game`, `Classification`, `User`, `Ranking`) are defined yet. These will be added when real Django API contracts exist.

## Route Integration

No Astro route currently imports the API layer. When routes do integrate:
- Call `getJSON<T>` or `postJSON<T>` from Astro frontmatter.
- Use `result.ok` to branch between data rendering and error states.
- Never display raw `ApiError` content that may contain backend context directly in public UI.

## Behavioural Tests

Transport hardening is complete (SBGC-160). Behavioural proof is provided by the Vitest transport test suite (SBGC-161) in `src/lib/server/api/__tests__/`. Tests use Vitest in Node environment with mocked `globalThis.fetch` — no real network requests are made. Covered behaviours: configuration validation, URL and path handling, redirect rejection, request serialization, headers, successful responses, 204 No Content, non-success HTTP statuses, media type handling, malformed JSON, timeout, caller cancellation, and no-retry guarantees. Run with `npm run test:frontend`.
