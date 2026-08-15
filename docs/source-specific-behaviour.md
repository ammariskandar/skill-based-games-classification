# Source-Specific Behaviour — SBGC-61

Canonical source-policy matrix for `Game` (manual vs Steam).

## Canonical identity

```text
manual  → source_type == manual, external_id is NULL
steam   → source_type == steam, valid nonempty external_id
```

`Game.id` remains the universal primary key.  There is no
`ManualGame`/`SteamGame` model split or proxy hierarchy.

## Capability helpers

`games/services/source_policy.py` exposes pure, dependency-free checks:

```python
can_manual_edit(game)     # game.is_manual
can_steam_refresh(game)   # game.is_steam
```

`Game.is_manual` / `Game.is_steam` are properties on the model.  These
helpers perform no network, no database query, and no authorization —
server-side enforcement still lives at the service/Admin/API boundary.

## Admin editability matrix (existing records)

| Field | Manual Game | Steam Game |
|-------|-------------|------------|
| `name` | editable | **readonly** (Steam-owned) |
| `slug` | editable | editable |
| `content_type` | editable | **readonly** (Steam-owned) |
| `listing_status` | editable | editable |
| `release_date` | editable | editable (local/editorial) |
| `developer` | editable | editable (local/editorial) |
| `manual_description` | editable | editable (local/editorial) |
| `manual_image_url` | editable | editable (local/editorial) |
| `manual_website_url` | editable | editable (local/editorial) |
| `source_type` | **readonly** | **readonly** |
| `external_id` | **readonly** | **readonly** |
| `steam_image_url` | readonly | readonly |
| `last_steam_refresh_at` | readonly | readonly |
| `display_identity` | readonly | readonly |
| `created_at` / `updated_at` | readonly | readonly |

Creation still permits choosing source/external ID.  Existing records
can never change `source_type`, `external_id`, or (for Steam) its
Steam-owned `name`/`content_type`.

## Manual service

`create_manual_game()` / `update_manual_game()` remain manual-only via
`can_manual_edit()`.  Steam Games are rejected before mutation.

## Steam refresh

`SteamGameRefreshService` remains Steam-only via `can_steam_refresh()`.
Manual Games are rejected before any Steam call or write.  The Admin
refresh action skips manual records without network.

## Release/developer ownership

`release_date` and `developer` are local/editorial metadata for both
sources.  Steam import/refresh never populates or changes them.

## Image fallback

`Game.display_image_url` is unchanged:

```python
manual_image_url or steam_image_url
```

Manual override wins; otherwise the Steam-owned URL is used.

## Listing and classification

Both remain source-independent:

- `publicly_listable()` uses only `content_type == GAME` and
  `listing_status == PUBLISHED`.
- editorial classification applies to both manual and Steam Games.
