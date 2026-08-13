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

### `classifications.EditorialClassification`

| Invariant | Constraint | Type | DB | App | SQLite | PG |
|-----------|-----------|------|----|-----|--------|-----|
| One per Game | `OneToOneField` | Implicit unique FK | ✅ | — | ✅ | ✅ |
| `updated_by` FK | `ForeignKey(PROTECT)` | FK constraint | ✅ | — | ✅ | ✅ |
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

## Invalid-State Matrix

| State | DB | Model | Service | Admin |
|-------|----|-------|---------|-------|
| Steam + NULL external_id | ❌ | ❌ | ❌ | ❌ |
| Steam + blank external_id | ❌ | ❌ | ❌ | ❌ |
| Manual + non-null external_id | ❌ | ❌ | ❌ | ❌ |
| Duplicate Steam identity | ❌ | ❌ | ❌ | ❌ |
| Duplicate slug | ❌ | ❌ | ❌ | ❌ |
| Duplicate name | ✅ | ✅ | ✅ | ✅ |
| Duplicate parent per Game | ❌ | ❌ | ❌ | ❌ |
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

## Questionnaire Readiness

Future questionnaire scores (SBGC-171, SBGC-175) belong to separate
`QuestionnaireClassification` / `QuestionnaireResult` models.  They:

- Link to canonical `Game` via FK
- Do not overwrite or replace editorial classification
- Use their own provenance, versioning, and persistence rules
- May reuse `validate_score_distribution()` patterns
- Are owned by SBGC-171 and SBGC-175

No questionnaire fields or tables exist in SBGC-47.
