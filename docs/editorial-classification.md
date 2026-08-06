# Editorial Classification — SBGC-46

One editorial classification per Game with separate Challenge and Reward
profile models.

## Ownership

Owned by the `classifications` app.  One `EditorialClassification` per
`Game` via `OneToOneField`.  The `classifications` app depends on `games`.

## Models

### `EditorialClassification`

| Field | Type | Notes |
|-------|------|-------|
| `game` | `OneToOneField(Game, CASCADE)` | `related_name="editorial_classification"` |
| `notes` | `TextField(blank=True)` | Optional editorial notes |
| `updated_by` | `ForeignKey(User, PROTECT)` | Assigned by the service, never inferred from request state in the model |
| `created_at` | `DateTimeField(auto_now_add)` | |
| `updated_at` | `DateTimeField(auto_now)` | |

### `ChallengeProfile`

| Field | Type | Notes |
|-------|------|-------|
| `classification` | `OneToOneField(CASCADE)` | `related_name="challenge_profile"` |
| `micro_score` | `PositiveSmallIntegerField` | Challenge Micro — moment-to-moment skill demands |
| `mystiko_score` | `PositiveSmallIntegerField` | Challenge Mystiko — depth, knowledge, discovery |
| `macro_score` | `PositiveSmallIntegerField` | Challenge Macro — strategic and long-term demands |

### `RewardProfile`

| Field | Type | Notes |
|-------|------|-------|
| `classification` | `OneToOneField(CASCADE)` | `related_name="reward_profile"` |
| `micro_score` | `PositiveSmallIntegerField` | Reward Micro — immediate feedback and pacing |
| `mystiko_score` | `PositiveSmallIntegerField` | Reward Mystiko — discovery-based satisfaction |
| `macro_score` | `PositiveSmallIntegerField` | Reward Macro — long-term progression and achievement |

## Score Contract

- Each score: `0 ≤ score ≤ 100` (integer)
- Each profile independently totals exactly 100: `micro + mystiko + macro = 100`
- Challenge and Reward are independent — no combined totals
- Boolean values are normalised to integers by Django's field cleaning

## Validation Layers

| Layer | What |
|-------|------|
| `classifications/validation.py` | Shared pure function `validate_score_distribution()` — type, range, total |
| Model `clean()` | Invokes `validate_score_distribution()` with profile-specific label |
| `CheckConstraint` (DB) | Range 0–100 for each score on both profiles |
| Service | Validates both distributions before any database writes |

The total=100 rule is enforced at the database level via
``CheckConstraint`` using Django ``F()`` expressions:

```sql
CHECK ("micro_score" = ((100 - "mystiko_score") - "macro_score"))
```

Application-level validation in ``clean()`` and the service layer
provides earlier, context-specific error messages.  Both layers
enforce the same contract; neither can be bypassed.

## Service

`set_editorial_classification()` in `classifications/services/editorial.py`:

- Takes `game`, `updated_by`, `challenge` (`ScoreDistribution`),
  `reward` (`ScoreDistribution`), optional `notes`
- Validates both distributions before any database writes
- Operates inside `transaction.atomic()`
- Creates or updates parent, Challenge, and Reward
- Returns the saved `EditorialClassification` with both profiles

## One-per-Game Enforcement

- `OneToOneField(Game)` prevents multiple parent rows
- `OneToOneField(EditorialClassification)` prevents multiple profiles
- The database guarantees at-most-one; the service guarantees completeness
  (both profiles always created together)

## Admin

Registered at `/admin/classifications/editorialclassification/` with:
- Two distinct `StackedInline` entries (`ChallengeProfileInline`,
  `RewardProfileInline`) — `extra=0`, `max_num=1`, `min_num=1`,
  `can_delete=False`
- `list_display`: game, updated_by, updated_at
- `search_fields`: game name/slug/external_id, updated_by username
- `readonly_fields`: created_at, updated_at, updated_by
- `updated_by` set from `request.user` in `save_model`

### Admin persistence contract

The Admin saves the parent and inline profiles **directly** (not through
`set_editorial_classification()`).  Django's `changeform_view` wraps the
entire save in `transaction.atomic()`, so a database failure during inline
persistence rolls back the parent.

**Profile completeness:** Custom `BaseInlineFormSet` subclasses
(`ChallengeProfileInlineFormSet`, `RewardProfileInlineFormSet`) enforce
exactly one active profile per formset:
- Zero submitted forms → `ValidationError`
- More than one submitted form → `ValidationError`
- Empty extra rows are ignored
- Existing unchanged instances count as one
- Deletion of the sole profile is blocked (`can_delete=False`)

The Admin therefore guarantees the same completeness invariant as the
service: every saved `EditorialClassification` has exactly one Challenge
and one Reward profile.

**Limitations:**
- The database guarantees at-most-one parent and at-most-one of each
  profile.  It does **not** guarantee every parent has both child rows.
- Direct unrestricted ORM use (bypassing both Admin and service) may
  still create an incomplete parent.

## Score Analysis Helpers

`classifications/skills.py` provides vocabulary enums (`SkillCategory`,
`EditorialProfile`) and a pure `dominant_skill_category()` function.
Challenge and Reward `dominant_skill_category` model properties delegate
to this helper.  Tied highest scores have **no dominant category**.

Game queryset helpers in `games/models.py` (`GameQuerySet`) provide
DB-level dominant-skill annotations, filtering, score-range filtering,
and score sorting — all editorial-only, independent of future
questionnaire/community classifications.

See `docs/game-query-helpers.md` for the complete helper inventory.

## Limitations

- Database guarantees at-most-one; service guarantees completeness;
  Admin creates parent + inlines atomically but does not enforce child
  existence at form-submit time.
- No community/user classifications (SBGC-47)
- No API endpoints
- No PostgreSQL-specific constraint verification (SBGC-52)
- No history/version tables
