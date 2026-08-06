# Game Query Helpers — SBGC-49

Reusable query and model helpers for Game records and editorial
classification scores.

## Query Helpers (`GameQuerySet`)

All methods are chainable and use SQL evaluation (no Python-side filtering).

### `publicly_listable()`
Returns only `content_type=GAME AND listing_status=PUBLISHED` records.
Canonical implementation — do not reproduce elsewhere.

### `steam()` / `manual()`
Filter by `source_type`.  No classification or publication filtering.

### `editorially_classified()`
Returns only Games with a **complete** editorial classification:
parent row + Challenge profile + Reward profile.  Excludes all
incomplete states.

### `with_editorial_profiles()`
`select_related` for all editorial rows.  Does **not** filter —
returns every Game.  Use for N+1-safe profile access.

### `with_dominant_skill_categories()`
Annotates `challenge_dominant_skill_category` and
`reward_dominant_skill_category` (`str | None`).  Uses Django
`Case/When/Q/F` with strict-greater-than comparisons at the
database level.  Ties return `NULL`.  Missing profiles return
`NULL`.  One SQL query — no Python iteration.

### `filter_by_dominant_skill_category(profile, category)`
Requires complete classification.  Filters to rows whose
*profile* dominant skill equals *category*.  Ties excluded.
Validates `profile` against `EditorialProfile` and `category`
against `SkillCategory`.

### `filter_by_editorial_score(profile, category, minimum, maximum)`
Requires complete classification.  Inclusive integer bounds 0–100.
At least one bound required.  Booleans and floats rejected.
Range validated before query.

### `order_by_editorial_score(profile, category, descending=True)`
Requires complete classification.  Deterministic tie-breaking:
score → name → id.  `descending` must be a boolean.

## Model Helpers

### `dominant_skill_category(micro_score, mystiko_score, macro_score)`
Pure function in `classifications.skills`.  Returns the
`SkillCategory` with the strictly highest score, or `None` on tie.
Validates range and total via shared validator.  No DB/network.

### `ChallengeProfile.dominant_skill_category`
### `RewardProfile.dominant_skill_category`
Model properties delegating to the pure helper.

## Vocabularies (`classifications.skills`)

### `SkillCategory`
`micro`, `mystiko`, `macro`

### `EditorialProfile`
`challenge`, `reward`

## Composition

All queryset methods chain freely:
```python
Game.objects.publicly_listable().steam().editorially_classified()
Game.objects.steam().filter_by_editorial_score(...)
Game.objects.order_by_editorial_score(...).filter_by_dominant_skill_category(...)
```

## Default Manager

`Game.objects.all()` returns every canonical record — no hidden
filtering.  Only explicit helpers narrow results.

## Dominant Skill: Ties → NULL

The dominant-skill annotation and pure helper both use strict greater-than
comparisons.  Two or more scores tying for first place produce `NULL`.
This applies to both Challenge and Reward independently.

## Python/SQL Parity

The DB annotation (`with_dominant_skill_categories`) and model properties
(`dominant_skill_category`) produce identical results for the same row.
Tests verify this for unique winners and ties.

## Index

No new index is justified yet.  The existing composite index supports
current query patterns.  Real API query evidence may justify later tuning.

## No Network

All helpers evaluate at the database level.  No Steam, external service,
or network call occurs during queryset evaluation, annotation, or model
property access.

## Limitations

- No API endpoints consume these helpers yet
- No frontend listing page
- No Steam type mapping
- Score indexes deferred to real query evidence
- Questionnaire/community classification is separate (SBGC-171/175)
