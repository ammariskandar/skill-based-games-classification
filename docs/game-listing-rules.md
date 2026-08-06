# Game Listing Rules — SBGC-48

Content-type vocabulary and public-game-listing eligibility.

## Content Types

Six normalized content types classify every canonical `Game` record:

| Value | Label | Meaning |
|-------|-------|---------|
| `game` | Game | A playable game |
| `dlc` | Downloadable content | Expansion or add-on for a base game |
| `demo` | Demo | Free demonstration or trial version |
| `software` | Software | Non-game application (e.g. tools, SDKs) |
| `soundtrack` | Soundtrack | Standalone music/audio product |
| `unknown` | Unknown | Type not yet determined or cannot be mapped |

`OTHER` has been removed (SBGC-48).  A data migration (`games.0003`)
converts any persisted ``other`` rows to ``unknown``.  The reverse
migration converts ``unknown`` back to ``other`` — inherently lossy
for legitimate Unknown records created after the forward migration.
No ``other`` values exist in any known environment; the data migration
is a safety net for developer databases.

`GAME` remains the default.

## Public Listing Rule

Only records that satisfy **both** conditions appear in the public game
listing:

1. `content_type = GAME`
2. `listing_status = PUBLISHED`

This is implemented as:

```python
Game.objects.publicly_listable()
```

The queryset method returns only Published Game records.  Every other
combination — Draft Game, Archived Game, Published DLC/Demo/Software/
Soundtrack/Unknown — is excluded.

## Content Type vs Listing Status

These are independent dimensions:

- `content_type` — what kind of product this is
- `listing_status` — whether editors have approved it for public display

Valid records include `Published DLC`, `Published Demo`, `Published Software`,
`Published Soundtrack`, and `Published Unknown`.  They are merely excluded
from the public **game** listing.  Changing content type does not mutate
listing status, and vice versa.

## Default Manager

`Game.objects.all()` returns every canonical record — no hidden filtering.
Only `Game.objects.publicly_listable()` applies the public listing rule.

## Unknown

`UNKNOWN` is a valid canonical type for records whose normalized product
type has not yet been determined.  Unknown records are never returned by
`publicly_listable()`, even when `PUBLISHED`.

## Index

No new listing index is justified yet.  The existing composite index
``game_listing_name_idx`` on ``(listing_status, name, id)`` may be
revisited when real listing-query evidence from API endpoints or
PostgreSQL query plans becomes available.

## Migration

`games/migrations/0002_alter_game_content_type.py` — `AlterField` changing
the `content_type` choices from 4 to 6.  SQLite generates a no-op SQL
(state change only).  No `RunPython` data migration — no `other` values
exist in any environment.  Fully reversible (reverse restores the 4-choice
state).

## Steam Independence

No Steam endpoint or import mapping is implemented.  The `Game` model
remains usable for manual records without Steam, and no model/queryset/
Admin/test makes a Steam call.

## Limitations

- Content-type choices are **application-level validation** (Django
  ``choices``), not a database ``CHECK`` constraint.  Arbitrary direct
  SQL values are not prevented.  The ``other → unknown`` data migration
  handles historical values; new raw writes are not DB-enforced.
- Public listing remains safe because ``publicly_listable()`` explicitly
  requires ``content_type="game"`` — obsolete or raw values are excluded
  regardless.
- No public listing API endpoint yet
- No frontend listing page
- No Steam type mapping
- Index tuning deferred to real query evidence
