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
None, ``int``, excessive length, zero.

## Lookup Outcomes

| Status | Meaning |
|--------|---------|
| `FOUND` | Valid app details returned, import candidate produced |
| `UNAVAILABLE` | ``success=false`` — the App ID exists but is unavailable |

Malformed payloads, missing required fields, and transport exceptions
all propagate to the caller as typed exceptions — they are never
classified as lookup statuses.

## Product-Type Mapping

``map_steam_product_type()`` returns values from ``ContentType``
(the canonical ``games.models.ContentType`` enum).  Unknown Steam
types map to ``ContentType.UNKNOWN`` — never to ``ContentType.GAME``.

| Steam Type | Normalized |
|-----------|------------|
| ``game`` | ``ContentType.GAME`` |
| ``dlc`` | ``ContentType.DLC`` |
| ``demo`` | ``ContentType.DEMO`` |
| ``software`` | ``ContentType.SOFTWARE`` |
| ``music`` | ``ContentType.SOUNDTRACK`` |
| ``soundtrack`` | ``ContentType.SOUNDTRACK`` |
| unrecognised nonblank | ``ContentType.UNKNOWN`` |
| blank / non-string | raises ``ValueError`` (malformed) |

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

- **Header image:** Must be a string or null.  Non-string types raise
  ``SteamMalformedPayloadError``.  HTTPS only, no credentials, no IP
  literals.  Null/blank → ``None``.
- **Website:** Must be a string or null.  Non-string types raise
  ``SteamMalformedPayloadError``.  HTTP or HTTPS, no credentials.
  Null/blank → ``None``.  Unsafe schemes rejected.

No image download or CDN fetching is performed.

## Transport Ownership

All networking, retries, timeouts, response-size limits, and error
classification are owned by ``SteamClient`` (SBGC-42/168).  The adapters
never instantiate ``requests.Session``, ``urllib3.Retry``, or make
direct HTTP calls.

Store endpoint adapters call ``SteamClient.get_store_api_json()``;
Web API callers use ``SteamClient.get_web_api_json()``.  The origins
are closed — callers select from the ``SteamEndpointOrigin`` enum;
arbitrary URL strings are never accepted.

Tests prove no module outside the package ``__init__`` can construct
a ``SteamClient`` with an arbitrary origin.

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

It catches adapter-level `STEAM_APP_UNAVAILABLE` → `UNAVAILABLE`.
Other adapter errors (malformed payloads, missing fields, invalid
App IDs) and transport exceptions (timeout, connection, etc.)
propagate unchanged to the caller.

## Tests

78 isolated tests across 4 modules — all use ``SimpleTestCase``, mocked
``SteamClient``, no database, no network.

| Module | Tests |
|--------|-------|
| ``test_dto.py`` | 19 |
| ``test_mapping.py`` | 16 |
| ``test_app_details_adapter.py`` | 29 |
| ``test_import_foundation.py`` | 14 |

## Limitations

- No API endpoints consume these adapters yet
- No Game persistence
- No bulk/multi-app lookup
- No metadata refresh or caching
- No Steam Web API Key required for the Store appdetails endpoint
- Image CDN validation not yet applied (CDN allowlist is empty)
