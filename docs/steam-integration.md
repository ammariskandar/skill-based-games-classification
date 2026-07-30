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

Steam API and Store origins are **fixed trusted constants** — not
configurable via environment variables:

| Constant | Value |
|----------|-------|
| `api_origin` | `https://api.steampowered.com` |
| `store_origin` | `https://store.steampowered.com` |

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
- **Total:** `max_retries` (default 2, max 3 total attempts)
- **Methods:** GET and HEAD only
- **Statuses:** 429, 500, 502, 503, 504
- **Never retried:** 401, 403, ordinary 4xx, configuration errors, JSON/schema failures
- **Redirects:** disabled (`redirect=0`, `allow_redirects=False`)
- **Other:** 0 (no retry on unlisted statuses)
- `Retry-After` header respected; backoff bounded; no delay beyond 5 seconds

## Response Handling

- `Content-Length` inspected before body read; enforced during streaming read
- Default 2 MiB limit — raises `SteamResponseTooLargeError`
- Accepted media types: `application/json`, `application/*+json` (with optional parameters)
- JSON root must be an object (`dict`) — arrays, scalars, and null rejected
- Redirects (3xx) raise `SteamRedirectError` — never followed

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
- No credentials, custom ports, fragments, IP literals, localhost
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

## Future Work

- Concrete Steam API endpoint adapters (e.g., `GetAppList`, `GetSchemaForGame`)
- Metadata import workflow and management command
- CDN host allowlist populated with actual Steam CDN hosts
- Domain model persistence
- Public Django Ninja routes consuming Steam data

## Dependency Installation

```bash
flatpak-spawn --host apps/backend/.venv/bin/python -m pip install "requests==2.32.5"
```
