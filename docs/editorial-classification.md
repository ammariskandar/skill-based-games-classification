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

The total=100 rule is enforced at the application level (`clean()` +
service).  Django ORM `F()` arithmetic expressions do not cleanly
support `CHECK (a + b + c = 100)` across fields because
`CombinedExpression.__eq__` evaluates at Python class-definition time.
The range constraints are DB-enforced; the total is application-enforced.

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

## Limitations

- Total=100 is application-enforced, not DB-enforced
- No community/user classifications (SBGC-47)
- No API endpoints
- No PostgreSQL-specific constraint verification (SBGC-52)
- No history/version tables
