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
- `other`

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

## Limitations

- PostgreSQL-specific constraint and index behaviour is not verified
  (SBGC-52).
- No Classification models or Game-to-Classification relationships yet
  (SBGC-46).
- No Steam import or API integration (SBGC-53).
- No custom managers.
- No soft deletion.
- CheckConstraint enforcement depends on the database engine; SQLite
  may not enforce it without `PRAGMA` configuration.
