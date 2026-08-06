# Database Connectivity

Database configuration for the MyGameDNA Django backend.

## Connection Modes

| Environment  | Database | DATABASE_URL       | Fallback          |
| ------------ | -------- | ------------------ | ----------------- |
| Test / CI    | SQLite   | ignored             | N/A (in-memory)   |
| Development  | SQLite   | blank/absent       | Yes (local .db)   |
| Development  | Neon     | populated, direct  | Yes (to SQLite)   |
| Production   | Neon     | **required**       | **No** (fails)    |

## Supported URL Types

| Engine          | Scheme             | Example                                      |
| --------------- | ------------------ | -------------------------------------------- |
| SQLite          | `sqlite:///`       | `sqlite:///db.sqlite3`                       |
| PostgreSQL      | `postgresql://`    | See Neon connection section below            |

Other engines (MySQL, Oracle, etc.) raise `ImproperlyConfigured`.

## Neon Connection

### Direct Connection (SBGC-39 Policy)

Use a **direct** (non-pooler) Neon connection string:

```
postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require&channel_binding=require
```

The host must **not** contain `-pooler`. Pooled hosts use
transaction-level pooling which can interfere with Django migration
workflows and session-dependent operations.

**How to identify a pooled host:** The Neon hostname contains `-pooler`
(e.g., `ep-xyz-pooler.region.aws.neon.tech`). If your host includes
`-pooler`, it is a pooled connection and must not be used for the
current SBGC-39 connection mode.

### Why Direct Connections?

- Low expected traffic does not require pooling.
- Direct connections are safer for Django `migrate` workflows.
- Transaction pooling (PgBouncer) can break operations that depend on
  session state or explicit transaction boundaries.
- Pooling can be revisited after measured need.

### SSL and Channel Binding

- `sslmode=require` — mandatory TLS.
- `channel_binding=require` — SCRAM channel binding.

These are preserved from the URL query string and not altered by the
configuration helper.

### Connection Timeout

A `connect_timeout=10` (seconds) is added to PostgreSQL `OPTIONS` if
not already set by the caller. This prevents indefinite hangs when the
database is unreachable.

### CONN_MAX_AGE

Set to `0` (no persistent connections). No application-side connection
pooling is configured.

## Local Setup

### SQLite (default)

```bash
# No DATABASE_URL needed — SQLite is used automatically.
python manage.py runserver --settings=config.settings.development
```

### Neon (development)

```bash
# Set DATABASE_URL in apps/backend/.env or the process environment.
# Use a direct (non-pooler) connection string.
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require&channel_binding=require \
  python manage.py runserver --settings=config.settings.development
```

## Credential Safety

- `apps/backend/.env` is **gitignored**. Never commit it.
- Error messages from `build_database_config()` never include the
  original `DATABASE_URL`, hostname, username, password, or database name.
- Never print `settings.DATABASES` or `DATABASE_URL` in logs or tests.
- Do not copy connection strings into documentation, tests, or committed files.

## Migration Commands

### SQLite (local development)

```bash
DATABASE_URL="" python manage.py migrate --settings=config.settings.development
DATABASE_URL="" python manage.py migrate --check --settings=config.settings.development
DATABASE_URL="" python manage.py showmigrations --settings=config.settings.development
```

### Neon (direct connection)

```bash
python manage.py migrate --settings=config.settings.development
python manage.py migrate --check --settings=config.settings.development
python manage.py showmigrations --settings=config.settings.development
```

## Connection Probe

```bash
python manage.py shell --settings=config.settings.development -c "
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('SELECT 1')
    assert cursor.fetchone() == (1,)
print('Vendor:', connection.vendor)
"
```

## Direct-Host Verification

```bash
python manage.py shell --settings=config.settings.development -c "
from django.conf import settings
host = settings.DATABASES['default'].get('HOST', '')
assert '-pooler' not in host
print('Direct Neon endpoint verified')
"
```

The assertion fails if the host is a pooled Neon host (`-pooler` in
hostname). Switch to a direct host before proceeding.

## Test Settings

Automated backend tests and CI use a dedicated test settings module:

```
config.settings.test
```

This module **always** uses an in-memory SQLite database regardless of
whether `DATABASE_URL` is set in the local `.env` or process environment.

- **Never connects to Neon.**
- **Never creates a PostgreSQL test database.**
- **Never prompts.**
- **Deterministic** — same behavior with or without `apps/backend/.env`.

```bash
# Run all backend tests (always uses SQLite):
npm run test:backend

# Equivalent explicit command:
python manage.py test apps/backend --settings=config.settings.test --noinput
```

## CI Policy

GitHub Actions:
- Uses `config.settings.test`.
- Connects to an isolated in-memory SQLite test database.
- Does **not** supply `DATABASE_URL`.
- No Neon credentials or PostgreSQL service is configured.
- Never connects to Neon or any external database.

## Production Startup

Production settings (`config.settings.production`) **require**
`DATABASE_URL`. A missing, blank, or whitespace-only value raises
`ImproperlyConfigured` at startup. SQLite fallback is never used in
production.

```bash
# This fails with ImproperlyConfigured:
DATABASE_URL="" python manage.py check --settings=config.settings.production
```

## Current Limitations

- **Application migrations are present.** Domain models (`games`, `classifications`) have
  been migrated through SBGC-45–48.
- **No connection pooling.** `CONN_MAX_AGE=0` and no `psycopg_pool`.
  Pooling is deferred until measured traffic warrants it.
- **PostgreSQL verification completed** — SBGC-52 verified constraints,
  migrations, indexes, transactions, and concurrent uniqueness on an
  isolated PostgreSQL 16 instance.  See `docs/postgresql-verification.md`.
- **Production Neon has not been connected.** No live Render/Neon
  deployment verification has occurred.
- **No read replicas.**
- **No Neon API automation.**
- **No database health endpoint.**


## SBGC-43 — PostgreSQL-Only Production

Production enforces PostgreSQL-only database connectivity. Missing, blank,
SQLite, MySQL, Oracle, and unknown engine URLs all raise
`ImproperlyConfigured` at startup. Development retains SQLite fallback;
tests remain in-memory SQLite.

## SBGC-52 — Runtime vs Migration URLs

The `scripts/backend-migrate.sh` script supports `MIGRATION_DATABASE_URL`
for a direct Neon connection during migrations.  If set, it overrides
`DATABASE_URL` for the migration command only.  This allows runtime to
use a pooled connection while migrations use a direct (non-pooler)
connection.  See `docs/postgresql-verification.md`.
