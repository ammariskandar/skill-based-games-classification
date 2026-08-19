# Game Administration — SBGC-67

This document describes the configured Django Admin experience for the
canonical `Game` model. It documents operator-facing behavior only; the Game
domain rules themselves are owned by `game-model.md`,
`manual-game-management.md`, `source-specific-behaviour.md`, and
`game-deletion-workflow.md`.

## Changelist

`GameAdmin.list_display` shows, in order:

1. `name`
2. `source_type` (Steam / Manual)
3. `external_id` (Steam App ID; blank for Manual)
4. `content_type`
5. `listing_status`
6. `developer`
7. `submission_count` (number of editorial classification submissions)
8. `classification_status` (current Final Classification status + Confidence
   Level, read-only)
9. `updated_at`

The two derived columns (`submission_count`, `classification_status`) are
precomputed in `get_queryset()` via an annotation and a prefetch of the single
current classification snapshot, so the changelist does not issue per-row
queries.

## Search

`search_fields` covers `name`, `slug`, `external_id`, and `developer`.

## Filters

`list_filter` covers the three canonical categorical states:

- `source_type`
- `content_type`
- `listing_status`

## Ordering

The changelist is deterministically ordered by `("name", "id")`, matching the
model's own ordering without changing global model ordering.

## Fieldsets

The add/edit form groups fields as:

- **Identity** — `name`, `slug`, `source_type`, `external_id`, `content_type`
- **Publication** — `listing_status`
- **Manual / editorial metadata** — `release_date`, `developer`,
  `manual_description`, `manual_image_url`, `manual_website_url`
- **Steam metadata** — `steam_image_url`, `last_steam_refresh_at`
- **System** (collapsed) — `display_identity`, `created_at`, `updated_at`

## Field ownership / editability matrix

Legend: **E** = editable, **R** = readonly, **—** = hidden/non-editable
(auto-managed or not applicable).

| Field | Create | Manual edit | Steam edit | Notes |
|-------|--------|-------------|------------|-------|
| `name` | E | E | R | Steam-owned for Steam records; refreshed from Steam. |
| `slug` | E | E | E | Editorial URL identity; never refreshed from Steam. |
| `source_type` | E | R | R | Source identity is immutable after creation. |
| `external_id` | E (Steam only) | R | R | Steam App ID is immutable after creation. |
| `content_type` | E | E | R | Steam-owned for Steam records; refreshed from Steam. |
| `listing_status` | E | E | E | Editorial publication state; source-independent. |
| `release_date` | E | E | E | Local editorial metadata. |
| `developer` | E | E | E | Local editorial metadata. |
| `manual_description` | E | E | E | Local editorial metadata. |
| `manual_image_url` | E | E | E | Local editorial metadata. |
| `manual_website_url` | E | E | E | Local editorial metadata. |
| `steam_image_url` | R | R | R | Steam-owned; never populated from manual data. |
| `last_steam_refresh_at` | R | R | R | Steam-owned; set only by refresh. |
| `created_at` | — | R | R | Auto-managed timestamp. |
| `updated_at` | — | R | R | Auto-managed timestamp. |
| `display_identity` | — | R | R | Derived `steam:<id>` / `manual:<slug>` identity. |

## Source-specific editability

- **New Game** — the operator chooses `source_type` and `external_id` on
  creation. The canonical identity can be established once.
- **Existing Manual Game** — source identity (`source_type`, `external_id`) is
  readonly; `name`, `slug`, `content_type`, `listing_status`, and all manual
  metadata are editable.
- **Existing Steam Game** — source identity (`source_type`, `external_id`) and
  Steam-owned `name` / `content_type` are readonly; `slug`, `listing_status`,
  and all manual/editorial metadata remain editable. Steam metadata
  (`steam_image_url`, `last_steam_refresh_at`) is always readonly.

This preserves the canonical rules: no source conversion, no immutable
source-identity editing, and no overwriting Steam-synced fields via Admin.

## Validation

Admin surfaces domain validation as clean form errors (no partial writes):

- whitespace-only `name`;
- duplicate `slug`;
- invalid `manual_image_url`;
- invalid `release_date` input;
- Steam `external_id` missing / non-decimal;
- Manual record with an `external_id`;
- duplicate Steam `(source_type, external_id)`.

The existing `games/tests/test_admin_validation.py` and
`games/tests/test_admin_date_formats.py` cover these boundaries.

## Delete behavior

`delete_selected` bulk deletion remains disabled. Canonical deletion is the
single-object confirmation page with its cascade summary. Steam deletion never
contacts Steam. This is preserved from SBGC-182 and covered by
`games/tests/test_game_deletion_admin.py`.

## Related classification reference

The changelist shows a **read-only** `classification_status` column (current
Final Classification status + Confidence Level) and `submission_count`. These
are persisted reads — they never trigger a statistical calculation.

Classification **administration** (forms, diagnostics, actions) is owned by
**SBGC-68**; this ticket only surfaces the current published status.

## Additional Admin actions

New bulk actions (bulk publish/archive, batch refresh, batch calculate) are
**out of scope** and deferred to **SBGC-69**. Only the existing
`refresh_from_steam` action remains.
