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

- `manual_description` — `TextField(blank=True)`
- `manual_image_url` — `URLField(max_length=500, blank=True)`
- `manual_website_url` — `URLField(max_length=500, blank=True)`

Not restricted to `source_type=manual` — editorial overrides may later
be useful for Steam records too.

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
- `readonly_fields`: display_identity, created_at, updated_at

Manual records are creatable through Admin.

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
  fields yet — the import workflow does not persist it.
