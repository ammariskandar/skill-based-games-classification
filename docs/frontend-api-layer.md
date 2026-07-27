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
  | { ok: true;  data: T; status: number }
  | { ok: false; error: ApiError; status?: number }
```

Callers narrow on `result.ok` — no manual HTTP status checking required.

## Error Categories

| Code               | Meaning                                  |
| ------------------ | ---------------------------------------- |
| `CONFIG_ERROR`     | `DJANGO_API_URL` not set or invalid path |
| `TIMEOUT`          | Request exceeded `timeoutMs` (default 8s) |
| `ABORTED`          | Caller cancelled via `AbortSignal`       |
| `NETWORK_ERROR`    | DNS failure, connection refused, etc.     |
| `HTTP_ERROR`       | Non-2xx response from Django             |
| `INVALID_RESPONSE` | Non-JSON body, empty response, parse error |
| `UNKNOWN_ERROR`    | Any unclassified failure                 |

Each `ApiError` has:
- `code` — machine-readable, stable
- `message` — human-readable, safe (no secrets, stack traces, raw HTML)
- `status?` — HTTP status when available
- `cause?` — diagnostic context (logging only, never displayed)

## Configuration

- Reads `DJANGO_API_URL` from the server environment (`import.meta.env.DJANGO_API_URL`).
- Validated at request time, not at module import — unrelated static pages build without a local `.env`.
- Accepts **relative paths only** (`/api/games`, `/api/search`). Absolute and protocol-relative URLs are rejected.

## Timeout

- Default: 8 seconds.
- Overridable per-request via `timeoutMs` option.
- Timeout and caller `AbortSignal` cancellation are cleanly distinguished.
- No automatic retries — write requests are never retried.

## No Runtime Schema Validation

TypeScript types (`ApiResult<SomeType>`) describe expected shapes at compile time. They do **not** validate untrusted JSON at runtime. Django is the authoritative source of truth for data shape and integrity. A runtime schema library (e.g. Zod) may be considered later if needed.

## Endpoint-Specific Types

No domain types (`Game`, `Classification`, `User`, `Ranking`) are defined yet. These will be added when real Django API contracts exist. The API layer remains generic until then.

## Route Integration

No Astro route currently imports the API layer. Route-to-API integration is deferred until stable Django endpoints exist. When routes do integrate:
- Call `getJSON<T>` or `postJSON<T>` from Astro frontmatter.
- Use `result.ok` to branch between data rendering and error states.
- Never display raw `ApiError.message` that may contain backend context directly in public UI without review.
