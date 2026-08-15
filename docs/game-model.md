# Game Model — SBGC-45

Canonical product identity and editorial state.  Owned by the `games` app.

## Ownership

The `Game` model is the single source of truth for product identity in
MyGameDNA.  It is **not** raw Steam JSON, an import job, a transport
response, or a cache.

## Internal primary key

A Django `BigAutoField` (`id`) is the universal primary key.  Steam App
ID, external ID, slug, and name are never primary keys.  This allows
duplicate names, slug changes, and manual records without identity
collisions.

## Source type and external ID

| Source | `source_type` | `external_id` |
|--------|---------------|---------------|
| Steam  | `"steam"`     | Non-null, nonempty decimal string (e.g. `"730"`) |
| Manual | `"manual"`    | `NULL` |

- `external_id` is a `CharField(max_length=64)`, not an integer — no
  arithmetic is performed on it.
- Steam external IDs must consist only of decimal digits (`str.isdigit()`).
- The combination `(source_type, external_id)` is unique when
  `external_id IS NOT NULL` (conditional unique constraint).
- Multiple manual records with `NULL` external IDs are allowed.

## Name and slug

- `name` — required, `max_length=255`, duplicates allowed.  Whitespace-only
  names are rejected in `clean()`.
- `slug` — required, `unique=True`, `max_length=255`.  Explicit at creation;
  **not** regenerated on name changes.  Admin `prepopulated_fields` is an
  editing convenience only.

## Content type

Normalized application classification (not raw Steam metadata):

- `game` (default)
- `dlc`
- `demo`
- `software`
- `soundtrack`
- `unknown`

## Listing status

Editorial state, never derived from Steam or external metadata:

- `draft` (default)
- `published`
- `archived`

No overlapping booleans (`is_active`, `is_visible`, `is_published`,
`deleted`).

## Manual metadata

Optional application-owned editorial fields available for all source types:

- `release_date` — `DateField(null=True, blank=True)` — manual editorial
  release date (SBGC-59).  Never populated from Steam or changed by Steam
  refresh.
- `developer` — `CharField(max_length=255, blank=True)` — manual editorial
  developer name (SBGC-59).  Never populated from Steam or changed by Steam
  refresh.
- `manual_description` — `TextField(blank=True)`
- `manual_image_url` — `URLField(max_length=500, blank=True)` — validated
  editor-supplied HTTPS URL reference (SBGC-60).  Blank means no manual
  image; see `docs/manual-assets.md`.
- `manual_website_url` — `URLField(max_length=500, blank=True)`

Not restricted to `source_type=manual` — editorial overrides may later
be useful for Steam records too.  `release_date`/`developer` are manual
editorial metadata, distinct from unpersisted Steam DTO metadata such as
Steam `developers`/`publishers`.

## Steam-owned metadata

- `steam_image_url` — `URLField(max_length=500, blank=True)` — the
  validated Steam header-image URL persisted from import candidates
  (SBGC-55).  URL-only metadata: no image bytes, no fetch, no proxy.
  Never populated from manual/editorial data; `manual_image_url` is
  never populated from Steam.  See `docs/steam-images.md`.
- `last_steam_refresh_at` — `DateTimeField(null=True, blank=True)` —
  when this Steam record's metadata was last successfully verified
  against Steam (SBGC-56).  `NULL` = never refreshed; not set when the
  Steam app is unavailable.  See `docs/steam-metadata-refresh.md`.

## Timestamps

- `created_at` — `DateTimeField(auto_now_add=True)`
- `updated_at` — `DateTimeField(auto_now=True)`

No external fetch or sync timestamps.

## Display identity

```python
@property
def display_identity(self) -> str:
    if self.source_type == SourceType.STEAM:
        return f"steam:{self.external_id}"
    return f"manual:{self.slug}"
```

`__str__` returns `f"{self.name} [{self.display_identity}]"`.

Deterministic, no network calls.

## Display image

`display_image_url` (SBGC-60) is the pure presentation-neutral fallback
helper:

```python
@property
def display_image_url(self) -> str:
    return self.manual_image_url or self.steam_image_url
```

Manual override wins; otherwise the Steam-owned URL is used.  No network,
no extra query.  See `docs/manual-assets.md`.

## Source helpers

`Game.is_manual` / `Game.is_steam` are pure source predicates (SBGC-61).
`games/services/source_policy.py` exposes `can_manual_edit()` and
`can_steam_refresh()` for shared capability checks.  See
`docs/source-specific-behaviour.md`.

## Constraints

| Constraint | Name | Description |
|------------|------|-------------|
| `CheckConstraint` | `game_source_external_id_ck` | Steam → non-null, nonempty external_id. Manual → NULL external_id. |
| `UniqueConstraint` | `game_unique_source_external_id` | `(source_type, external_id)` unique when `external_id IS NOT NULL`. |

## Indexes

| Index | Fields | Purpose |
|-------|--------|---------|
| `game_listing_name_idx` | `listing_status, name, id` | Efficient published-game listing queries |

No redundant indexes for slug (unique constraint provides one), primary
key, or the source/external unique constraint.

## Ordering

Default `ordering = ["name", "id"]` — duplicate names are distinguished
by insertion order.

## Admin

Registered at `/admin/games/game/` with:

- `list_display`: name, source_type, external_id, content_type,
  listing_status, updated_at
- `list_filter`: source_type, content_type, listing_status
- `search_fields`: name, slug, external_id
- `prepopulated_fields`: slug ← name (editing convenience)
- `readonly_fields`: display_identity, created_at, updated_at,
  steam_image_url, last_steam_refresh_at
- editing an existing record also makes `source_type` and `external_id`
  readonly (SBGC-59), freezing canonical source identity after creation
- editing an existing Steam record additionally makes `name` and
  `content_type` readonly (SBGC-61) — those are Steam-owned and
  overwritten by refresh
- slug-from-name prepopulation is disabled for existing Steam records
  (because `name` is readonly there)

Manual records are creatable through Admin; existing Steam/manual records
cannot change source identity through Admin editing.  See
`docs/source-specific-behaviour.md` for the full editability matrix.

## No network calls

The `Game` model layer never imports `SteamClient`, `requests`, or any
network-dependent module.  Construction, `clean()`, `full_clean()`,
`display_identity`, `__str__`, and Admin listing all operate without
external I/O.

## Steam import persistence (SBGC-54)

`games/services/imports/` persists validated `SteamGameImportCandidate`
DTOs as canonical Games.  See `docs/steam-import-workflow.md`.

- New imports set `source_type=steam`, `external_id=app_id`, `name`,
  `content_type`, a deterministically allocated `slug`, and the default
  `listing_status=draft` — imports never publish.
- Re-imports update only `name` and `content_type`; slug, listing status,
  manual metadata, timestamps, and editorial classifications are
  preserved.
- `manual_*` fields are editorial-only and are **never** populated from
  Steam data — Steam metadata persistence belongs to later tickets.

## Manual game management (SBGC-59)

`games/services/manual.py` is the canonical create/edit path for manual
(non-Steam) Games.  It forces `source_type=manual` and `external_id=None`,
rejects editing Steam Games, preserves slug on name changes, and never
touches Steam-owned fields or the editorial classification.  See
`docs/manual-game-management.md`.

## Limitations

- CheckConstraint enforcement depends on the database engine; SQLite
  enforces it by default (``PRAGMA ignore_check_constraints=0``).
  PostgreSQL-specific constraint and index behaviour is verified by
  SBGC-52.
- Steam-owned metadata (`short_description`, `header_image_url`,
  `website_url`, `is_free`, `developers`, `publishers`) has no canonical
  fields yet — the import workflow does not persist it.  Manual editorial
  `release_date`/`developer` fields (SBGC-59) are separate and are never
  populated from Steam DTO metadata.
