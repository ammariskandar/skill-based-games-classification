# Classification Administration — SBGC-68

This document describes the Django Admin experience for editorial
classification **source data** (human submissions) and **derived data**
(calculated snapshots). The two are deliberately separated:

- Human submissions are editable according to the submission domain rules.
- Derived statistics are strictly read-only.

The classification architecture itself is owned by the SBGC-63/64/65/66 work;
this ticket only configures the Admin around it.

## Source vs derived ownership

| Data | Kind | Editable? |
|------|------|-----------|
| `game`, `submitted_by`, `submitted_role`, `submitted_base_weight` | submission provenance | readonly on existing submissions |
| `notes`, `updated_by` | submission attribution | `notes` editable; `updated_by`/timestamps readonly |
| Challenge/Reward `micro/mystiko/macro` | human source scores | editable |
| `total`, `dominant_display` | computed source helpers | readonly (derived from source) |
| Method 1/2/3 scores | derived | readonly |
| unified Final Classification | derived | readonly |
| Confidence (`confidence_final`, `confidence_label`) | derived | readonly |
| status / N / timestamps / provenance | derived | readonly |

## Submission changelist

`EditorialClassificationAdmin.list_display`:

1. `game`
2. `submitted_by`
3. `submitted_role`
4. `challenge_dominant`
5. `challenge_total`
6. `reward_dominant`
7. `reward_total`
8. `updated_at`

The dominant and total columns read from the two profile models. The six raw
score values are intentionally not dumped into the changelist; they are edited
on the change form.

## Search

`search_fields` covers `game__name`, `game__slug`, `game__external_id`,
`submitted_by__username`, and `updated_by__username`.

## Filters

`list_filter` covers `submitted_role`, `game__source_type`, and
`game__content_type`.

## Challenge / Reward editing

Each submission renders two stacked inlines (one `ChallengeProfile`, one
`RewardProfile`), each showing:

- `micro_score`
- `mystiko_score`
- `macro_score`
- `total` (readonly)
- `dominant_display` (readonly)

Both inlines enforce exactly one active profile and cannot be deleted.

## Totals

`ChallengeProfile.total` / `RewardProfile.total` are pure properties
(`micro + mystiko + macro`). The changelist and inline both display them.
They are never editable and never normalized.

## Dominant display

`dominant_display` is a pure property that reports the highest-scoring
dimension (`Micro`, `Mystiko`, `Macro`), or a tie like `Micro / Macro tie`.
It is computed directly for display and never validates, so it does not raise
while a form is mid-edit. The authoritative validating helper remains
`dominant_skill_category`.

## Validation

The Admin surfaces the shared `validate_score_distribution` errors as clean
form errors, including the current total. Example:

> Challenge scores must total exactly 100 (got 99).

No partial write occurs on validation failure. Submitted profiles are never
silently normalized (a `50 / 30 / 19` source is invalid, never rounded).

## Provenance immutability

On existing submissions the following are readonly:

- `game`
- `submitted_by`
- `submitted_role`
- `submitted_base_weight`

`updated_by` and the timestamps are also readonly. This preserves the
immutable role snapshot and submitter attribution required by SBGC-63/64.

## Game navigation

The `game` column on the submission changelist links to the Game Admin change
page. Game administration itself remains owned by SBGC-67; classification
Admin does not duplicate Game editing.

## Final Classification (read-only)

`ClassificationSnapshotAdmin` presents the persisted derived snapshot:

- **Final Classification** fieldset: `game`, `status`, `regime`,
  `validated_count`, `final_challenge`, `final_reward`,
  `confidence_final`, `confidence_label`.
- **Method diagnostics** (collapsed): `method_1_summary`,
  `method_2_summary`, `method_3_summary` — the three pseudo-final score sets,
  each showing status plus Challenge/Reward integer profiles.
- **Timing & provenance** (collapsed): timestamps, current/stale flags, and
  version/hash provenance.

The changelist shows the unified `final_challenge` / `final_reward` columns so
the true Final Classification is visually obvious rather than one of four
ambiguous score sets.

`ClassificationSnapshot`, `CalculationEpoch`, and `BoundaryCalibration` have
`has_add_permission` / `has_change_permission` / `has_delete_permission` set to
`False`; every field is readonly. No superuser backdoor can override the
mathematics.

## Calculation prohibition on render

Opening any classification Admin page (submission changelist, change form, or
derived snapshot pages) reads only persisted data. It never invokes Method
1/2/3, BHPCM, bootstrap, Confidence, the simulation, or the scheduler.

## Out of scope

- **SBGC-69** owns additional Admin actions (including any future
  recalculation action). SBGC-68 adds no new actions.
- **SBGC-70** owns broader Admin safety/usability (destructive confirmations,
  system-field protection, audit-visible timestamps/updaters).
