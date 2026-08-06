# Steam Endpoint Adapters — SBGC-53

Typed endpoint adapters built on the existing hardened `SteamClient` transport.
Converts raw Steam Store API responses into validated application DTOs.

## Architecture

```
Steam Store API
  → SteamClient.get_json()             (existing transport — SBGC-42/168)
  → SteamAppDetailsAdapter.fetch()     (adapter — SBGC-53)
  → SteamImportFoundation.prepare_candidate()  (service — SBGC-53)
  → SteamGameImportCandidate           (DTO)
  → (future: Game persistence)
```

## Package Structure

```
games/services/steam/
  adapters/
    __init__.py              # SteamAdapterError, SteamMalformedPayloadError, etc.
    app_details.py           # SteamAppDetailsAdapter
  dto.py                     # SteamAppId, SteamAppDetails, SteamGameImportCandidate
  mapping.py                 # map_steam_product_type()
  import_foundation.py       # SteamImportFoundation
```

## SteamAppId

Immutable validated value type.  Value is a decimal-digit string only.
Rejects: blank, whitespace, non-digit, signs, float/exponent, Boolean,
None, `int`, excessive length, zero.

## Lookup Outcomes

| Status | Meaning |
|--------|---------|
| `FOUND` | Valid app details returned, import candidate produced |
| `UNAVAILABLE` | `success=false` — the App ID exists but is unavailable |
| `UNSUPPORTED` | Malformed response or unrecognised payload structure |

Transport exceptions (timeout, connection, rate limit, upstream, etc.)
propagate unchanged — not mapped to lookup statuses.

## Product-Type Mapping

| Steam Type | Normalized |
|-----------|-----------|
| `game` | `game` |
| `dlc` | `dlc` |
| `demo` | `demo` |
| `software` | `software` |
| `music` | `soundtrack` |
| `soundtrack` | `soundtrack` |
| unrecognised nonblank | `unknown` |
| blank / non-string | raises `ValueError` (malformed) |

Unknown types are never mapped to `game`.

## Response Validation

The adapter validates every structural layer:

1. Root is a JSON object
2. Root contains the requested App ID as key
3. Wrapper is a dict
4. `success` is a strict `bool`
5. On `success=true`, `data` is a dict
6. `name` and `type` are non-blank strings
7. Optional fields use type-safe extraction

Violations raise `SteamMalformedPayloadError` or `SteamMissingRequiredFieldError`.

## URL Validation

- **Header image:** HTTPS only, no credentials, no IP literals.
  Null/blank/non-string → `None`.
- **Website:** HTTP or HTTPS, no credentials. Null/blank/non-string → `None`.
  Unsafe schemes rejected.

No image download or CDN fetching is performed.

## No Persistence

The adapter and import foundation do not:
- Import the `Game` ORM model
- Create or update database rows
- Generate slugs
- Select listing status
- Create classifications
- Open transactions

## Transport Ownership

All networking, retries, timeouts, response-size limits, and error
classification are owned by `SteamClient` (SBGC-42/168).  The adapters
never instantiate `requests.Session`, `urllib3.Retry`, or make direct
HTTP calls.

## Import Foundation

`SteamImportFoundation.prepare_candidate(app_id)` combines:
1. `SteamAppId` validation
2. `SteamAppDetailsAdapter.fetch()`
3. `SteamGameImportCandidate` production

It catches adapter-level `STEAM_APP_UNAVAILABLE` → `UNAVAILABLE`
and other adapter errors → `UNSUPPORTED`.  Transport exceptions
propagate unchanged.

## Tests

70 isolated tests across 4 modules — all use `SimpleTestCase`, mocked
`SteamClient.get_json()`, no database, no network.

## Limitations

- No API endpoints consume these adapters yet
- No Game persistence
- No bulk/multi-app lookup
- No metadata refresh or caching
- No Steam Web API Key required for the Store appdetails endpoint
- Image CDN validation not yet applied (CDN allowlist is empty)
