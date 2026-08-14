# Steam Integration

External-service foundation for the Steam Web API — SBGC-42.

## Architecture

```
steam_client_config_from_settings()  (config/steam.py)
  └── reads raw Django settings → SteamClientConfig

SteamClient (games/services/steam/client.py)
  └── requests.Session (HTTPS + Retry adapter)
       └── https://api.steampowered.com  (fixed, not configurable)

Steam CDN (games/services/steam/cdn.py)
  └── validate_steam_cdn_url() — pure function, no network calls
```

The Steam client lives under `games/services/steam/` — owned by the
`games` Django application.  Future domain endpoints and import workflows
will use this client.

## Environment Configuration

Environment variables are read through the repository's existing
`django-environ` mechanism in `config/settings/base.py` (shared defaults)
and consumed by `steam_client_config_from_settings()` in `config/steam.py`.

- **`config/settings/base.py`** — reads raw string values from `.env` with
  documented defaults.  All seven `STEAM_*` variables are optional.
- **`config/steam.py`** — the single factory that parses, normalises, and
  validates raw settings into a `SteamClientConfig`.  This is the only
  point where Django settings cross into the Steam transport model.
- **`config/settings/test.py`** — overrides all Steam settings with
  deterministic values; never reads the developer's `.env` Steam key.

Configuration is **lazy** — `steam_client_config_from_settings()` is
not called during settings import.  No `SteamClient` is instantiated
and no network request is made until the application explicitly builds
a client and calls a method.

## Package Structure

```
config/
└── steam.py          # steam_client_config_from_settings() — SBGC-42

games/services/steam/
├── __init__.py    # Public re-exports
├── config.py      # SteamClientConfig (immutable dataclass)
├── client.py      # SteamClient (synchronous, injectable)
├── cdn.py         # validate_steam_cdn_url()
└── errors.py      # Service-specific exception taxonomy
```

## Trusted Origins

Steam API and Store origins are **immutable code constants** in
`games.services.steam.constants` — not configurable via dataclass,
Django settings, or environment variables:

| Constant | Value |
|----------|-------|
| `STEAM_WEB_API_ORIGIN` | `https://api.steampowered.com` |
| `STEAM_STORE_API_ORIGIN` | `https://store.steampowered.com` |

Production environment variables cannot redirect API-key-bearing requests
to arbitrary origins.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STEAM_WEB_API_KEY` | *(empty)* | Steam Web API key. Optional at startup; required only for authenticated methods. |
| `STEAM_CONNECT_TIMEOUT_SECONDS` | `3.05` | Connection timeout (0 < t ≤ 30) |
| `STEAM_READ_TIMEOUT_SECONDS` | `10` | Read timeout (0 < t ≤ 60) |
| `STEAM_MAX_RETRIES` | `2` | Retry count (0–3) for idempotent GET/HEAD |
| `STEAM_RETRY_BACKOFF_SECONDS` | `0.25` | urllib3 Retry backoff factor |
| `STEAM_RETRY_SLEEP_MAX_SECONDS` | `5` | Ceiling for exponential backoff and Retry-After sleep (integer, 0–10; urllib3 `retry_after_max` is typed `int`) |
| `STEAM_MAX_RESPONSE_BYTES` | `2097152` | Response body size limit (2 MiB) |
| `STEAM_CDN_ALLOWED_HOSTS` | *(empty)* | Comma-separated trusted CDN hostnames |

## API Key Handling

- Sent only through the `x-webapi-key` request header.
- Never added to the query string.
- Never included in exception messages, logs, repr output, or test output.
- Stripped of outer whitespace; blank treated as absent.
- Required only when `requires_api_key=True` is passed.

## Timeout and Retry Policy

Every request uses `timeout=(connect_timeout, read_timeout)` — never `None`.

Retries (via urllib3 `Retry`):
- **Maximum attempts:** `1 + max_retries` (default 3). The urllib3 `total`
  counter is the master cap — individual connect/read/status counters share it.
- **Methods:** GET and HEAD only
- **Statuses:** 429, 500, 502, 503, 504
- **Never retried:** 401, 403, ordinary 4xx, configuration errors, JSON/schema failures
- **Redirects:** disabled (`redirect=0`, `allow_redirects=False`, `raise_on_redirect=False`)
- **Other:** 0 (no retry on unlisted statuses)
- **Backoff cap:** `backoff_max = retry_sleep_max_seconds` (default 5.0 s).
  Exponential backoff cannot exceed this ceiling.
- **Retry-After cap:** `retry_after_max = retry_sleep_max_seconds` (default 5.0 s).
  Server-supplied `Retry-After` values above the cap are reduced to this ceiling.
- **Configured operation budget:**
  `maximum_attempts × (connect_timeout + read_timeout)
   + max_retries × retry_sleep_max_seconds`
  Default 49.15 s; hard ceiling 120 s. This is a budget ceiling, not a
  strict wall-clock deadline — DNS, TLS, scheduling, and library overhead
  can add elapsed time.
  Configurations exceeding the ceiling are rejected at construction.

## Response Handling

### Status-first error processing

For non-2xx responses the status is classified **before** any body parsing:

1. classify status → `SteamAuthenticationError`, `SteamRateLimitedError`,
   `SteamNotFoundError`, `SteamUpstreamError`, or `SteamRedirectError`;
2. bounded-drain the error body (1 MiB limit) for connection hygiene;
3. close the response;
4. raise the originally classified exception.

An oversized, malformed, or wrong-media error body never masks the
status-based error classification.  Raw upstream body content never
appears in exceptions or logs.

### Success responses

1. `Content-Length` prechecked against `max_response_bytes`
2. Body streamed under the byte limit with `iter_content()`
3. Chunks accumulated in a list and joined once with `b"".join(chunks)`
4. `Content-Type` validated against `application/json` or
   `application/<subtype>+json` (with optional parameters)
5. JSON decoded; root must be an object (`dict`) — arrays, scalars,
   and null rejected

- Default 2 MiB limit — raises `SteamResponseTooLargeError`
- Redirects (3xx) raise `SteamRedirectError` — never followed
- Missing `Content-Type` or wrong media type raises `SteamInvalidResponseError`

## Error Taxonomy

```
SteamError
├── SteamConfigurationError    # Invalid config or missing required key
├── SteamRequestError          # Network-level (connect, timeout, redirect)
│   ├── SteamConnectionError   # DNS, connection-refused, TLS
│   ├── SteamTimeoutError      # Connect or read timeout
│   └── SteamRedirectError     # Unexpected 3xx
├── SteamResponseError         # Response-level
│   ├── SteamAuthenticationError  # 401 / 403
│   ├── SteamRateLimitedError     # 429 (includes retry_after)
│   ├── SteamNotFoundError        # 404
│   ├── SteamUpstreamError        # 5xx or unmapped 4xx
│   └── SteamInvalidResponseError # Bad content-type, malformed JSON, wrong root
└── SteamResponseTooLargeError # Exceeded max_response_bytes
```

All exceptions carry safe `code` and `message` only. Never: API key,
request URL, raw response body, upstream HTML, full response headers.

## CDN Trust Model

`validate_steam_cdn_url()` enforces:
- HTTPS only
- Exact hostname match against configured allowlist (no wildcard/suffix matching)
- No credentials, custom ports, fragments
- No IP literals (IPv4, IPv6, IPv4-mapped, link-local, loopback, private)
- No numeric-only host representations (decimal/hex/octal IP forms —
  e.g. `2130706433`, `0x7f000001`, `017700000001`)
- No `localhost` or `localhost.localdomain`
- Nonempty meaningful path required
- Empty allowlist rejects all CDN URLs

The function never downloads, caches, or proxies image binaries.

## Testing

All tests use injected fake `requests.Session` mocks — **no real network
calls**.  Retry policy is verified through adapter inspection; response
handling through mock responses.

Environment-configuration tests in `config/tests/test_steam.py` verify
that raw Django settings are correctly parsed, validated, and normalised
into `SteamClientConfig` — including defaults, overrides, malformed-value
rejection, blank-key normalisation, CDN-host parsing, and test-settings
isolation from the developer's `.env`.

## Completed Work (SBGC-53 / SBGC-54 / SBGC-55 / SBGC-56)

- Steam Store endpoint adapters — `SteamAppDetailsAdapter` for the Store
  appdetails endpoint, validating every structural layer of the response.
- Import-foundation DTOs — `SteamImportFoundation.prepare_candidate()`
  produces normalised `SteamGameImportCandidate` DTOs from app details.
- Product-type mapping — `map_steam_product_type()` maps raw Steam types
  to canonical `ContentType` values (game/dlc/demo/software/soundtrack/unknown).
- Steam persistence — `SteamGameImportService` / `SteamGamePersistenceService`
  create and refresh canonical `Game` rows from import candidates (SBGC-54).
  See `docs/steam-import-workflow.md`.
- Steam image metadata — validated header-image URLs persist to
  `Game.steam_image_url` (URL-only, no fetch/proxy/download) (SBGC-55).
  See `docs/steam-images.md`.
- Metadata refresh — `SteamGameRefreshService`, `Game.last_steam_refresh_at`,
  and a manual Admin refresh action (SBGC-56).
  See `docs/steam-metadata-refresh.md`.

## Future Work

- Persist the remaining DTO metadata (`short_description`, `website_url`,
  `is_free`, `developers`, `publishers`) into explicit Steam-owned schema
- CDN host allowlist populated from authoritative evidence of real Steam
  CDN hostnames (live verification or Steam documentation) — required
  before any image fetch/proxy feature.
- Public Django Ninja routes consuming Steam data
- Bulk/multi-app lookup and management commands
