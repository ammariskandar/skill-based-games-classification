# Database Constraints — SBGC-47

Complete inventory of database-enforced invariants, application-level
enforcement, and PostgreSQL-verification criteria for SBGC-52.

## Constraint Inventory

### `games.Game`

| Invariant | Constraint | Type | DB | App | SQLite | PG |
|-----------|-----------|------|----|-----|--------|-----|
| Steam → non-null, nonempty external_id | `game_source_external_id_ck` | `CheckConstraint` | ✅ | ✅ | ✅ | ✅ |
| Manual → NULL external_id | `game_source_external_id_ck` | `CheckConstraint` | ✅ | ✅ | ✅ | ✅ |
| `(source_type, external_id)` unique when not null | `game_unique_source_external_id` | `UniqueConstraint` (conditional) | ✅ | — | ✅ | ✅ |
| `slug` unique | Field `unique=True` | Implicit unique index | ✅ | — | ✅ | ✅ |
| Duplicate `name` allowed | — | No constraint | — | — | ✅ | ✅ |
| Steam decimal-ID format (`str.isdigit()`) | — | Application (`clean()`) | — | ✅ | ✅ | ✅ |
| Listing index | `game_listing_name_idx` | `Index` | ✅ | — | ✅ | ✅ |
| `BigAutoField` PK | Field `auto_created=True` | Implicit PK | ✅ | — | ✅ | ✅ |

`steam_image_url` (SBGC-55) carries **no database constraint** — remote
URL hostname policy is enforced by the pure `validate_steam_image_url()`
validator at the application layer (adapter + import persistence).  The
field is a plain nullable URLField; image presence is never a listing
criterion.

### `classifications.EditorialClassification`

| Invariant | Constraint | Type | DB | App | SQLite | PG |
|-----------|-----------|------|----|-----|--------|-----|
| `updated_by` FK | `ForeignKey(PROTECT)` | FK constraint | ✅ | — | ✅ | ✅ |
| `submitted_by` FK (SBGC-63) | `ForeignKey(PROTECT)` | FK constraint | ✅ | — | ✅ | ✅ |
| One submission per `(game, submitted_by)` (SBGC-63) | `UniqueConstraint` | Unique constraint | ✅ | — | ✅ | ✅ |
| Role/weight pair consistency (SBGC-64) | `editorial_submission_role_weight_ck` | `CheckConstraint` | ✅ | ✅ | ✅ | ✅ |
| `game` CASCADE delete | `on_delete=CASCADE` | FK constraint | ✅ | — | ✅ | ✅ |
| Exactly one Challenge + one Reward | — | Service/Admin only | — | ✅ | ✅ | ✅ |

### `classifications.ChallengeProfile`

| Invariant | Constraint | Type | DB | App | SQLite | PG |
|-----------|-----------|------|----|-----|--------|-----|
| One per parent | `OneToOneField` | Implicit unique FK | ✅ | — | ✅ | ✅ |
| 0 ≤ scores ≤ 100 | `challenge_scores_range_ck` | `CheckConstraint` | ✅ | ✅ | ✅ | ✅ |
| micro + mystiko + macro = 100 | `challenge_scores_total_100_ck` | `CheckConstraint` | ✅ | ✅ | ✅ | ✅ |
| Boolean rejection | `clean_fields()` | Application only | — | ✅ | ✅ | ✅ |
| CASCADE delete from parent | `on_delete=CASCADE` | FK constraint | ✅ | — | ✅ | ✅ |

### `classifications.RewardProfile`

| Invariant | Constraint | Type | DB | App | SQLite | PG |
|-----------|-----------|------|----|-----|--------|-----|
| One per parent | `OneToOneField` | Implicit unique FK | ✅ | — | ✅ | ✅ |
| 0 ≤ scores ≤ 100 | `reward_scores_range_ck` | `CheckConstraint` | ✅ | ✅ | ✅ | ✅ |
| micro + mystiko + macro = 100 | `reward_scores_total_100_ck` | `CheckConstraint` | ✅ | ✅ | ✅ | ✅ |
| Boolean rejection | `clean_fields()` | Application only | — | ✅ | ✅ | ✅ |
| CASCADE delete from parent | `on_delete=CASCADE` | FK constraint | ✅ | — | ✅ | ✅ |

### `classifications.ClassificationSnapshot` (SBGC-65)

| Invariant | Constraint | Type | DB | App | SQLite | PG |
|-----------|-----------|------|----|-----|--------|-----|
| At most one current snapshot per Game | `classification_snapshot_single_current_uniq` | Partial unique | ✅ | ✅ | ✅ | ⬜ |
| `epoch` survives snapshot deletion | `ForeignKey(PROTECT)` | FK constraint | ✅ | — | ✅ | ⬜ |

### `classifications.BoundaryCalibration` (SBGC-65)

| Invariant | Constraint | Type | DB | App | SQLite | PG |
|-----------|-----------|------|----|-----|--------|-----|
| One calibration per `(game, master_version)` | `boundary_calibration_game_version_uniq` | Unique constraint | ✅ | — | ✅ | ⬜ |

### `classifications.CalculationAttempt` (SBGC-65)

| Invariant | Constraint | Type | DB | App | SQLite | PG |
|-----------|-----------|------|----|-----|--------|-----|
| One attempt per `(game, epoch, number)` | `calculation_attempt_game_epoch_number_uniq` | Unique constraint | ✅ | — | ✅ | ⬜ |

SBGC-65 rows are SQLite-verified; the PostgreSQL lane was not rerun for
this ticket (no disposable PG 16 image available; not Neon).  See
`docs/classification-derived-calculation.md`.

## Deletion Cascade (SBGC-182)

`Game` deletion cascades through **all** submissions and their profiles:

```text
Game
├─ EditorialClassification (CASCADE)  → ChallengeProfile (CASCADE), RewardProfile (CASCADE)
├─ EditorialClassification (CASCADE)  → ChallengeProfile (CASCADE), RewardProfile (CASCADE)
└─ ...
```

`updated_by` and `submitted_by` (User) are `PROTECT` and survive.  See
`docs/game-deletion-workflow.md` and `docs/classification-submissions.md`.

SBGC-65 derived snapshots, boundary calibrations, and attempts also
cascade from `Game` (CASCADE); epochs are `PROTECT` from snapshots.

## Invalid-State Matrix

| State | DB | Model | Service | Admin |
|-------|----|-------|---------|-------|
| Steam + NULL external_id | ❌ | ❌ | ❌ | ❌ |
| Steam + blank external_id | ❌ | ❌ | ❌ | ❌ |
| Manual + non-null external_id | ❌ | ❌ | ❌ | ❌ |
| Duplicate Steam identity | ❌ | ❌ | ❌ | ❌ |
| Duplicate slug | ❌ | ❌ | ❌ | ❌ |
| Duplicate name | ✅ | ✅ | ✅ | ✅ |
| Duplicate submission per (game, user) | ❌ | ❌ | ❌ | ❌ |
| Duplicate Challenge per parent | ❌ | ❌ | ❌ | ❌ |
| Duplicate Reward per parent | ❌ | ❌ | ❌ | ❌ |
| Score < 0 | ❌ | ❌ | ❌ | ❌ |
| Score > 100 | ❌ | ❌ | ❌ | ❌ |
| Challenge total ≠ 100 | ❌ | ❌ | ❌ | ❌ |
| Reward total ≠ 100 | ❌ | ❌ | ❌ | ❌ |
| Missing Challenge (service) | — | — | ❌ | ❌ |
| Missing Reward (service) | — | — | ❌ | ❌ |
| Missing Challenge (Admin) | — | — | — | ❌ |
| Missing Reward (Admin) | — | — | — | ❌ |
| Parent without profiles (direct ORM) | ✅ | ✅ | — | — |

**Legend:** ❌ rejected · ✅ accepted · — not applicable

## Honest Limitations

- **Database does not enforce child existence.** Direct ORM can create an
  `EditorialClassification` without `ChallengeProfile` or `RewardProfile`
  rows.  Service and Admin both prevent this.
- **Steam decimal-ID format is application-enforced** (`clean()` checks
  `str.isdigit()`).  No portable cross-database `REGEXP` or `CAST`-based
  constraint exists.  PostgreSQL-specific format enforcement is deferred
  to SBGC-52.
- **SQLite passes all constraint tests at PRAGMA defaults**
  (`ignore_check_constraints=0`).  PostgreSQL-specific behaviour
  (deferred constraint timing, partial-index semantics for conditional
  uniqueness, `CASCADE`/`PROTECT` ordering) remains to be verified by
  SBGC-52.
- **SBGC-64 role/weight CheckConstraint**
  (`editorial_submission_role_weight_ck`) is SQLite-verified; fresh
  PostgreSQL verification is pending a disposable PostgreSQL 16 image.
- **Per-User editorial role conflict is not DB-enforced.**  A non-superuser
  resolving to both Moderator and Community Leader through two separate
  Groups is a many-to-many cross-row invariant, not representable as a
  per-row `CheckConstraint`.  It is enforced at the User Admin form,
  `resolve_editorial_role()`, and the submission service.  The per-Group
  mutual exclusion remains DB-enforced via
  `editorial_group_role_exclusive_ck`.

## PostgreSQL Verification Matrix (SBGC-52)

All constraints listed above with PG status "✅" were verified on an
isolated PostgreSQL 16 instance.  See `docs/postgresql-verification.md`.

Verification scope included:
- `game_source_external_id_ck` — CheckConstraint behaviour
- `game_unique_source_external_id` — conditional partial unique index
- Score range and total CheckConstraints (4 total)
- OneToOneField uniqueness under serialized writes
- CASCADE and PROTECT FK ordering
- Bulk update/create constraint enforcement
- Migration forward/reverse on PostgreSQL
- Service transaction rollback on PostgreSQL
- Concurrent uniqueness (serialized connections)
- Concurrent Steam import identity race (SBGC-54) — two parallel
  imports of the same App ID produce exactly one canonical row;
  `game_unique_source_external_id` is the authority and the losing
  import recovers the winner's row.  Verified in
  `games/tests/test_import_concurrency.py`.
- Concurrent slug race across distinct App IDs with the same name
  (SBGC-54) — the losing import's INSERT fails on the unique slug
  index; it recomputes a deterministic suffixed slug and retries once.
  Both identities persist exactly once.  Verified in
  `games/tests/test_import_concurrency.py`.

## Questionnaire Persistence (SBGC-177)

The questionnaire models seeded by SBGC-175 are hardened at the database
layer by SBGC-177 (migration `classifications.0011_questionnaire_db_constraints`).

### `classifications.QuestionnaireResult`

| Constraint / Index | Type | Target |
| --- | --- | --- |
| `chk_qresult_q15_range` | CheckConstraint | `q15_rating BETWEEN 1 AND 10` |
| `chk_qresult_norm_c_{micro,macro,mystiko}_range` | CheckConstraint | normalized Challenge dims `<= 100` |
| `chk_qresult_norm_r_{micro,macro,mystiko}_range` | CheckConstraint | normalized Reward dims `<= 100` |
| `chk_qresult_adj_c_{micro,macro,mystiko}_range` | CheckConstraint | adjusted Challenge dims `<= 100` |
| `chk_qresult_adj_r_{micro,macro,mystiko}_range` | CheckConstraint | adjusted Reward dims `<= 100` |
| `chk_qresult_norm_{challenge,reward}_sum_100` | CheckConstraint | normalized profile `Σ = 100` |
| `chk_qresult_adj_{challenge,reward}_sum_100` | CheckConstraint | adjusted profile `Σ = 100` |
| `idx_qresult_user_game_created` | Index | `(user_id, game_id, -created_at)` |

Lower bounds (`>= 0`) are enforced by PostgreSQL/SQLite for every
`PositiveSmallIntegerField` column (`smallint ... CHECK (column >= 0)`), so the
upper-bound checks plus the sum invariants cover the full `[0, 100]` range.

### `classifications.QuestionnaireClassification`

| Constraint / Index | Type | Target |
| --- | --- | --- |
| `uniq_qclass_user_game` | UniqueConstraint | `(user_id, game_id)` |
| `idx_qclass_status_updated` | Index | `(status, -updated_at)` |
| `latest_result` FK | Foreign Key | `QuestionnaireResult`, `ON DELETE CASCADE` |

### `classifications.UserGameScoreSubmission`

| Constraint / Index | Type | Target |
| --- | --- | --- |
| `questionnaire_result` FK | Foreign Key | `QuestionnaireResult`, `ON DELETE SET_NULL` |
| `idx_usergamescoresub_source` | Index | `(source, game_id)` |

`Game.aesthetic` carries a `db_index` from SBGC-172.  Behavioural verification
lives in `classifications/tests/test_database_constraints.py`, and migration
forward/backward execution in `test_migration_verification.py`.
