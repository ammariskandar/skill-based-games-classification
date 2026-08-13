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
| `manual_image_url` | Manual/editorial | Owner-supplied image URL for manual records or editorial overrides. |

`steam_image_url` is **never** populated from manual/editorial data, and
`manual_image_url` is **never** populated from Steam.  The two fields are
independent.

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

Contract:

| Input | Result |
|-------|--------|
| `None` | `None` (no upstream image) |
| non-string | raises `SteamMalformedPayloadError` |
| blank/whitespace | `None` |
| structurally invalid string | `None` (never persisted) |
| valid HTTPS URL | returned as-is (outer whitespace stripped) |

This mirrors the SBGC-53 adapter normalisation contract; the SBGC-55
hardening added IP-literal, numeric-host, localhost, port, and
credential rejection.

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

## Import Behavior

### New import

```text
candidate.header_image_url (valid) → Game.steam_image_url
candidate.header_image_url (None/blank/invalid) → "" (empty)
```

New Games remain `draft` — image presence never publishes.

### Re-import

```text
valid URL, different from stored  → update, status UPDATED
valid URL, equal to stored        → status UNCHANGED
None / blank / invalid            → preserve stored value, UNCHANGED
```

Preserved on every re-import: slug, listing status, `manual_*` fields,
editorial classification (parent + Challenge + Reward + notes +
`updated_by`), `created_at`.

## Missing-Image Semantics (Contract for SBGC-56)

Chosen contract — **preserve on ambiguous absence**:

- `steam_image_url == ""` means "no validated Steam image URL has ever
  been recorded".
- Upstream `None` is ambiguous (no image vs. malformed upstream value),
  so a re-import **never clears** a previously stored URL.

SBGC-56 (metadata refresh) must reuse this contract: only a validated
HTTPS URL updates the field; absence preserves it.

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
