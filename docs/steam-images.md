# Steam Images — SBGC-55

Canonical handling of Steam header-image metadata.

## Architecture Decision: URL Persistence Only

SBGC-55 persists **validated remote URLs**.  No proxy, no download, no
binary storage:

```text
Steam appdetails header_image
  → validate_steam_image_url()   (pure, structural, no network)
  → Game.steam_image_url          (URL metadata only)
```

Rationale:

- `context.md` §14.3: load from Steam CDN URLs, never store image
  binaries.
- The frontend hotlinks Steam CDN URLs directly.
- No speculative media model, storage backend, thumbnail pipeline, or
  background jobs.

Any future download/proxy feature is a separate ticket with its own
transport controls and **must** go through `validate_steam_cdn_url()`
(see Host Policy below).

## Field Ownership

| Field | Owner | Meaning |
|-------|-------|---------|
| `steam_image_url` | Steam (import) | Validated header-image URL from import candidates.  Readonly in Admin. |
| `library_hero_url` | Steam (derived, SBGC-184) | Official Steam Library Hero URL for base Games.  Readonly in Admin. |
| `library_capsule_url` | Steam (derived, SBGC-184) | Official Steam Library Capsule (portrait key-art) URL for base Games.  Readonly in Admin. |
| `manual_image_url` | Manual/editorial | Owner-supplied image URL for manual records or editorial overrides. |

`steam_image_url` is **never** populated from manual/editorial data, and
`manual_image_url` is **never** populated from Steam.  The two fields are
independent.

`library_hero_url` and `library_capsule_url` are Steam-owned and derived
from the App ID for base Games (`content_type == game`) during import and
refresh; they are empty for Manual Games and non-game Steam content (see
SBGC-184 in `docs/frontend-architecture.md`).  The `header.jpg`
(`steam_image_url`) remains the canonical `image_url` for SEO/OG/Twitter and
catalogue fallback — the Library assets are an additive Game-detail
presentation layer, not a replacement.

For effective display, `Game.display_image_url` (SBGC-60) returns the manual
override when present, otherwise `steam_image_url`.  Manual asset validation
and clear/replace semantics live in `docs/manual-assets.md`.

## Canonical Validation

`validate_steam_image_url()` in `games/services/steam/cdn.py` — the
single validator used by both the SBGC-53 adapter and the SBGC-54 import
persistence layer:

- HTTPS only (case-insensitive scheme);
- no credentials/userinfo;
- nonempty hostname required;
- no custom ports;
- no IP literals (IPv4, IPv6, IPv4-mapped);
- no numeric-only hosts (decimal/hex/octal forms, e.g. `2130706433`);
- no `localhost` / `localhost.localdomain`;
- **no network access** — structural validation only.

Contract — strict SBGC-53 malformed-metadata semantics:

| Input | Result |
|-------|--------|
| `None` | `None` (no upstream image) |
| blank/whitespace string | `None` (absent-field equivalent) |
| valid HTTPS URL | returned as-is (outer whitespace stripped) |
| non-string value | raises `SteamMalformedPayloadError` |
| nonblank malformed string (HTTP, credentials, missing hostname, custom port, IP literal, numeric host, localhost) | raises `SteamMalformedPayloadError` |

`None` means exactly one thing: the upstream payload did not provide a
usable image field.  Malformed nonblank upstream metadata is an **error**
and is never silently normalized to absence — this preserves the
strict external-payload principle established in SBGC-53.

## Host Policy (CDN Allowlist)

The strict trusted-host gate `validate_steam_cdn_url()` (SBGC-42) still
has an **empty allowlist** — every URL is rejected until real hostnames
are configured.  SBGC-55 intentionally does **not** populate it:

- The repository contains no authoritative evidence of real Steam CDN
  hostnames (no constants, fixtures, or documentation references).
- Inventing hostnames from memory is forbidden.
- URL-metadata persistence does not fetch anything, so the empty
  allowlist costs nothing today.

**Architectural gap:** before any image fetch/proxy/download feature
ships, the allowlist must be populated from live verification or
authoritative Steam documentation, as immutable source-controlled
constants (no environment override).

### Metadata Validation ≠ Fetch Authorization

`validate_steam_image_url()` authorizes **storage/display metadata**
only.  A URL acceptable for metadata persistence is **not** automatically
authorized for backend CDN fetching.  Any future server-side image
retrieval must additionally pass `validate_steam_cdn_url()` against a
populated, evidence-based allowlist (SBGC-56 or a live-integration
ticket).

## Import Behavior

### New import

```text
candidate.header_image_url (valid) → Game.steam_image_url
candidate.header_image_url (None/blank) → "" (empty)
candidate.header_image_url (malformed) → SteamMalformedPayloadError, no row
```

New Games remain `draft` — image presence never publishes.

### Re-import

```text
valid URL, different from stored  → update, status UPDATED
valid URL, equal to stored        → status UNCHANGED
None / blank                      → preserve stored value, UNCHANGED
malformed nonblank candidate      → SteamMalformedPayloadError, no writes
```

Preserved on every re-import: slug, listing status, `manual_*` fields,
editorial classification (parent + Challenge + Reward + notes +
`updated_by`), `created_at`.

## Missing-Image Semantics (Contract for SBGC-56)

Chosen contract — **preserve on absence** (refresh-compatible):

- `steam_image_url == ""` means "no validated Steam image URL has ever
  been recorded".
- Upstream `None`/blank means the upstream payload did not provide a
  usable image field — a re-import **never clears** a previously stored
  URL.
- Malformed nonblank upstream metadata **raises before persistence** —
  it is not reclassified as absence and never clears or preserves
  silently.

SBGC-56 (metadata refresh) reuses this contract: only a validated
HTTPS URL updates the field; `None`/blank preserves it; malformed
nonblank metadata raises.  See `docs/steam-metadata-refresh.md`.

## Listing Behavior

Image presence is **not** a listing criterion:

- A published Game without an image remains publicly listable.
- An imported Draft with an image remains Draft.
- `UNKNOWN` content type remains excluded regardless of image.

`publicly_listable()` is unchanged.

## No-Network Guarantee

URL-only persistence performs **zero** image HTTP requests:

- no GET/HEAD of the image URL;
- no remote MIME inspection;
- no DNS resolution;
- no image bytes stored.

Tests patch the Steam transport constructor to raise while image-bearing
candidates persist successfully.

## Admin

`steam_image_url` is readonly in `GameAdmin` for all records — source-
owned metadata is not casually editable.  Manual/editorial imagery stays
on the editable `manual_image_url`.  No image preview rendering (not
required by SBGC-55).

## Not in Scope

```text
SBGC-56 metadata refresh
public import API
frontend image rendering / galleries / thumbnails / resizing
user uploads
generic media model
object storage
background jobs
live Steam verification
```

No live Steam image URL has been verified by a human.
