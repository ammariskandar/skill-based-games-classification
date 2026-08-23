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
- **Editable metadata** — `release_date`, `developer`, `description`,
  `manual_website_url` (Steam Games also show per-field "Resume Steam sync"
  controls after each editable Steam-populated field)
- **Manual Image Overrides** (Steam) / **Images** (Manual) — `manual_image_url`,
  `manual_hero_url`, `manual_capsule_url`
- **Steam metadata** — `steam_image_url`, `library_hero_url`,
  `library_capsule_url`, `last_steam_refresh_at`
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
| `release_date` | E | E | E | Steam-managed unless overridden for Steam; manual for Manual. |
| `developer` | E | E | E | Steam-managed unless overridden for Steam; manual for Manual. |
| `description` | E | E | E | Steam-managed unless overridden for Steam; manual for Manual. |
| `manual_image_url` | E | E | E | Local editorial general/header image; overrides Steam header when present. |
| `manual_hero_url` | E | E | E | Local editorial wide-background image; overrides Steam Hero when present. |
| `manual_capsule_url` | E | E | E | Local editorial portrait key-art; overrides Steam Capsule when present. |
| `manual_website_url` | E | E | E | Local editorial metadata. |
| `steam_image_url` | R | R | R | Steam-owned; never populated from manual data. |
| `library_hero_url` | R | R | R | Steam-owned; derived from the App ID. |
| `library_capsule_url` | R | R | R | Steam-owned; derived from the App ID. |
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
  and `description`/`developer`/`release_date` remain editable. Editing one of
  those three fields marks it human-overridden automatically (no manual
  checkbox); a per-field "Resume Steam sync" control clears the override so
  the next refresh repopulates it. Steam metadata (`steam_image_url`,
  `library_hero_url`, `library_capsule_url`, `last_steam_refresh_at`) is always
  readonly.

This preserves the canonical rules: no source conversion, no immutable
source-identity editing, and no overwriting Steam-synced fields via Admin
(except the three explicitly editable Steam-populated fields, whose ownership
is tracked per field).

## Validation

Admin surfaces domain validation as clean form errors (no partial writes):

- whitespace-only `name`;
- duplicate `slug`;
- invalid `manual_image_url` / `manual_hero_url` / `manual_capsule_url`
  (HTTPS URL ending in `.jpg`, `.jpeg`, `.png`, or `.webp`);
- invalid `release_date` input;
- Steam `external_id` missing / non-decimal;
- Manual record with an `external_id`;
- duplicate Steam `(source_type, external_id)`.

The existing `games/tests/test_admin_validation.py` and
`games/tests/test_admin_date_formats.py` cover these boundaries.

## SBGC-190 — manual image overrides

Steam Games expose three optional, independent manual image overrides:
`manual_image_url` (general/header), `manual_hero_url` (wide background), and
`manual_capsule_url` (portrait key-art).  Presence of a role's manual URL
means that role is overridden; clearing it falls back to the current Steam
source value automatically (no override checkbox).  Manual Games use the same
three fields as their plain image sources (shown under the "Images" fieldset).

All three fields share one validator: HTTPS only, and the URL path must end in
`.jpg`, `.jpeg`, `.png`, or `.webp` (case-insensitive, query strings allowed).
No remote probing/download — validation is structural only.  Steam refresh
updates the underlying Steam source image fields but never writes the manual
override fields, so an active override survives refresh.

## SBGC-188 validation

Human verification completed on local SQLite with a live Steam refresh of two
public Steam Games: automatic population (Steam-managed fields filled),
selective per-field override (edited field preserved, untouched fields still
Steam-managed), and resume ownership (clearing an override then refreshing
repopulates from Steam).  Override/resume tests are in
`games/tests/test_admin_steam_override.py`.

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

`GameAdmin` exposes four bulk actions:

| Action | Effect | Eligibility |
|--------|--------|-------------|
| Publish selected Games | `listing_status → published` | skips already-published records |
| Hide selected Games | `listing_status → draft` | skips already-draft records |
| Archive selected Games | `listing_status → archived` | skips already-archived records |
| Refresh Steam metadata | calls the canonical `SteamGameRefreshService` | Steam only; Manual records skipped |

Publish/hide/archive only change the editorial `listing_status`; they never
mutate source identity, content type, classifications, or other metadata.
Each transition runs `full_clean()` before `save()`, so an invalid Game is
skipped without partial mutation.

`delete_selected` bulk deletion remains disabled (single-object cascade delete
is the canonical deletion path).

### Audit logging

Publish / Hide / Archive and Steam refresh (when it actually updates a Game)
write a standard Django Admin `LogEntry` (change) per affected object, so the
operator, object, action, and timestamp are visible in the Admin history.

### Action validation

Human verification completed on local SQLite. The four SBGC-69 checks passed:

1. Publish / Hide / Archive — disposable Games transitioned correctly with
   correct summary messages.
2. Steam refresh — Steam processed, Manual skipped, no source/manual metadata
   regression.
3. Classification recalculation — affected Game recalculated, current
   snapshot updated, no duplicate recalculation.
4. Safety regression — bulk delete still absent; derived Final Classification
   fields still read-only.

## Human verification

Completed on local SQLite. All five checks passed (5/5):

1. Game changelist — useful columns, search (name/slug/external_id/developer),
   and source/content/listing filters behave correctly.
2. Manual Game edit — source identity readonly; name/slug/content/listing and
   manual metadata editable; grouping clear.
3. Steam Game edit — `source_type`, `external_id`, `name`, `content_type`, and
   Steam-owned metadata readonly; `slug`, `listing_status`, and local/editorial
   metadata remain editable.
4. Copy / validation — no SBGC/Git/branch/internal jargon; representative
   validation error is clean.
5. Deletion confirmation — single-object cascade confirmation correct; bulk
   `delete_selected` absent.

## Safety validation (SBGC-70)

Human verification completed on local SQLite. All five safety checks passed:
identity/system fields protected (Manual and Steam), classification provenance
protected, single-object deletion with cascade and no bulk delete, derived
records view-only, and standard Admin history shows operator attribution and
timestamp for a safe Admin action.

## Scheduled Steam refresh audit (SBGC-183)

The daily scheduled Steam refresh records its current run in two read-only
Admin surfaces:

- `SteamRefreshRun` — scheduled/start/finish timestamps, status, selected /
  successful / failed counts, alert-sent flag.
- `SteamRefreshGameAttempt` — per-Game attempt number, timestamp, outcome, safe
  error code, and truncated error summary.

Both are registered as **view-only**: `has_add_permission`,
`has_change_permission`, and `has_delete_permission` all return `False`, and all
fields are readonly. There is no rerun button and no bulk deletion. The run and
attempt records are the persisted audit of the scheduled job, not an editorial
surface. See [`docs/scheduled-steam-refresh.md`](scheduled-steam-refresh.md).
