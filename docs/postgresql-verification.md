# PostgreSQL Verification — SBGC-52

Verification of database constraints, indexes, migrations, and
transactions on an isolated PostgreSQL instance.

## Supported PostgreSQL Version

PostgreSQL 16 (pinned in CI via `postgres:16`).  Earlier versions may
work but are not tested.

## Isolated Test Setup

SBGC-52 requires a **disposable, isolated** PostgreSQL database — never
production Neon.

### Local (Docker / Podman)

```bash
# Start a disposable PostgreSQL container
docker run -d --name pg-test \
  -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \
  -p 5432:5432 postgres:16

# Run PostgreSQL tests
POSTGRES_TEST_DATABASE_URL='postgresql://test:test@localhost:5432/test' \
  npm run test:backend:postgresql

# Clean up
docker rm -f pg-test
```

### Local PostgreSQL

```bash
createdb sbgc52_test

POSTGRES_TEST_DATABASE_URL='postgresql://localhost/sbgc52_test' \
  npm run test:backend:postgresql

dropdb sbgc52_test
```

### CI (GitHub Actions)

The CI workflow starts a `postgres:16` service container with
auto-generated credentials.  See `.github/workflows/ci.yml`.

## Runtime vs Migration URLs

- **Runtime** (`DATABASE_URL`): May use a Neon pooled connection.
- **Migration** (`MIGRATION_DATABASE_URL`): Must use a direct (non-pooler)
  Neon connection.  The `scripts/backend-migrate.sh` script checks for
  `MIGRATION_DATABASE_URL` and maps it to `DATABASE_URL` before running
  migrations.
- If `MIGRATION_DATABASE_URL` is not set, `DATABASE_URL` is used for
  both runtime and migrations.

### Neon Direct vs Pooled

| Connection | URL | Suitable For |
|-----------|-----|-------------|
| Direct | `postgresql://...@ep-xyz.region.aws.neon.tech/...` | Migrations, development |
| Pooled | `postgresql://...@ep-xyz-pooler.region.aws.neon.tech/...` | Runtime (low traffic) |

The hostname with `-pooler` indicates a PgBouncer transaction-pooled
connection.  Pooled connections may interfere with Django migration
workflows and session-dependent operations.  The project's current
policy is:

- `MIGRATION_DATABASE_URL` → direct connection (required for production
  deployment)
- `DATABASE_URL` → pooled connection acceptable for runtime

## Production Engine Enforcement

Production settings (`config.settings.production`) raise
`ImproperlyConfigured` for:

- Missing `DATABASE_URL`
- Blank `DATABASE_URL`
- SQLite URLs
- MySQL URLs
- Oracle URLs
- Malformed URLs

Only `postgresql://` scheme URLs are accepted.  Development and test
SQLite behaviour is unchanged.

## Verified Constraints

### Game Constraints

| Constraint | Type | PostgreSQL Verified |
|-----------|------|--------------------|
| `game_source_external_id_ck` | CheckConstraint | ✅ |
| `game_unique_source_external_id` | UniqueConstraint (conditional) | ✅ |
| Slug unique index | Implicit | ✅ |
| Duplicate name allowed | No constraint | ✅ |
| `game_listing_name_idx` | Index | ✅ |

### Classification Constraints

| Constraint | Type | PostgreSQL Verified |
|-----------|------|--------------------|
| One parent per Game | OneToOneField | ✅ |
| `updated_by` PROTECT | FK constraint | ✅ |
| `game` CASCADE delete | FK constraint | ✅ |
| `challenge_scores_range_ck` | CheckConstraint | ✅ |
| `challenge_scores_total_100_ck` | CheckConstraint | ✅ |
| `reward_scores_range_ck` | CheckConstraint | ✅ |
| `reward_scores_total_100_ck` | CheckConstraint | ✅ |
| CASCADE parent→profile | FK constraint | ✅ |
| Challenge/Reward independence | No cross-constraint | ✅ |

### Bulk Operations

Bulk `create` and `update` operations through the Django ORM are
verified to enforce CheckConstraints and UniqueConstraints on
PostgreSQL.  Violations raise `IntegrityError`.

### Service Transactions

The `set_editorial_classification()` service is verified on PostgreSQL:

- Invalid Reward creation rolls back parent and Challenge
- Invalid update preserves prior state
- Nested savepoint recovers after `IntegrityError`

### Concurrent Uniqueness

Duplicate Steam identity insertion is verified to raise `IntegrityError`
under serialized connections.

## Migration Verification

All migrations apply cleanly on a fresh PostgreSQL database.  Verified:

- Forward to latest
- Reverse `classifications` to zero and re-apply
- Reverse `games` to `0001` and re-apply
- `other → unknown` data migration (forward)
- `unknown → other` data migration (reverse)
- `makemigrations --check --dry-run` reports no pending changes

## Migration Failure Handling

- Django's transactional DDL ensures failed migrations roll back
- The migration recorder does not mark failed migrations as applied
- Subsequent valid migrations succeed after a failed one is rolled back

## Credential Safety

- `POSTGRES_TEST_DATABASE_URL` is never committed or logged
- Test settings use deterministic secret keys, not developer `.env`
- Production Neon is never used for testing
- Error messages never include connection strings or credentials

## Questionnaire Deferral

PostgreSQL verification in SBGC-52 covers:

- `Game`
- `EditorialClassification`
- `ChallengeProfile`
- `RewardProfile`

Questionnaire-result constraints (`QuestionnaireClassification`,
`QuestionnaireResult`) are deferred to SBGC-177.

## CI Integration

GitHub Actions includes a PostgreSQL 16 service container.
The `test:backend:postgresql` job:
1. Starts the PostgreSQL service
2. Waits for health
3. Runs migration consistency checks
4. Runs PostgreSQL constraint tests
5. Runs migration forward/reverse tests

## Current Limitations

- No production Neon verification has been performed
- No load tests or performance benchmarks
- No read replicas or failover testing
- No database health endpoint
- No Neon API automation
- Questionnaire constraints deferred to SBGC-177
