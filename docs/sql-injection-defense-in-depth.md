# SQL Injection Defense-in-Depth — Verification Playbook & Post-Execution Report

**SBGC-185** · Epic SBGC-16 · 2026-09-06

This document integrates the external SQL-injection playbook into MyGameDNA's
runtime architecture and records the executed audit, the fixes applied, and the
observations that remain operator actions.  It is organised as:

1. [Scope & ground rules](#1-scope--ground-rules)
2. [Architectural adjustments applied](#2-architectural-adjustments-applied)
3. [Code-level audit results](#3-code-level-audit-results)
4. [Injection-class probe log](#4-injection-class-probe-log)
5. [Neon least-privilege runbook](#5-neon-least-privilege-runbook)
6. [Render notes](#6-render-notes)
7. [Tooling consolidation](#7-tooling-consolidation)
8. [Out of scope, and why](#8-out-of-scope-and-why)

---

## 1. Scope & ground rules

Three layers are covered separately because they have separate owners:

| Layer | What lives here | Who patches it |
| --- | --- | --- |
| Application | Django views, ORM usage, raw SQL | Engineering (this ticket) |
| Database engine | PostgreSQL binaries, roles, extensions | Neon (managed) |
| Platform config | Env vars, network policy, connection strings | Engineering, via Render/Neon consoles |

Ground rules honoured by this pass:

- **No production testing.** Automated probes run inside the Django test suite
  against the in-memory test database (never live data).  Any future live
  black-box pass must target a Neon copy-on-write branch (e.g.
  `pentest-<date>`) behind a Render preview service, and the branch is deleted
  when done.
- **Production-like error behaviour.** Probe classes force `DEBUG=False`
  (`@override_settings`) because `config.settings.test` runs with
  `DEBUG=True`, which would invalidate error-based results.
- **Rate limiter isolation.** The SBGC-107 load-shedders are disabled in the
  test settings module; on a dedicated scan branch they are disabled via the
  new environment toggles (Section 2.4).  Never disabled on a
  production-traffic branch.
- One-loop protocol per point × class: attempt → if vulnerable fix immediately
  → otherwise exactly one modified variant → log either way (Section 4).

Deliberately **not** exercised: post-exploitation escalation mechanics
(large-object / `COPY ... FROM PROGRAM`, step-by-step CVE-2026-6471
exploitation).  The fix is identical regardless of mechanism — a
least-privilege role with no `REPLICATION`/`SUPERUSER` — see Section 8.

---

## 2. Architectural adjustments applied

### 2.1 Dual connection strings (playbook §4.1 conflict — migrations need DDL)

`scripts/backend-migrate.sh` already preferred a `MIGRATION_DATABASE_URL`
(direct, project-owner) over the runtime `DATABASE_URL` (SBGC-52), and
`config/database.py::build_database_config` documents the runtime-pooled /
migration-direct split via `override_url`.  SBGC-185 hardens the seam:

- **`scripts/backend-migrate.sh`** now **fails fast** if the effective
  `DATABASE_URL` still targets a Neon `-pooler.` hostname — migrations and
  `createcachetable` must always run against the direct compute endpoint.
- **`scripts/db-provision-app-role.sql`** (new) provisions the scoped runtime
  role (`app_django` by default) with DML-only grants, default privileges,
  an explicit grant on the unmanaged `django_cache` table (when present), and
  `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`.  Idempotent; usable for
  credential rotation.  See Section 5 for usage and the REPLICATION audit.
- **`.env.example`** documents `DATABASE_URL` (scoped role, pooled) vs
  `MIGRATION_DATABASE_URL` (owner, direct) plus the provisioning command.

### 2.2 PgBouncer transaction pooling (playbook §4.7)

- **`config/settings/production.py`** pins `DATABASES["default"]["CONN_MAX_AGE"]
  = 0` with a comment explaining Neon's transaction-mode pooler: Django must
  not persist connection-level state across pooled transactions.
- Migrations / `createcachetable` bypass the pooler (Section 2.1).

### 2.3 Admin path & ingress topology (playbook §1/§3 conflict)

- The admin route env var in this codebase is **`ADMIN_URL_PATH`** (validated
  single path segment), *not* `DJANGO_ADMIN_PATH`.  Development default is
  `admin`; production **requires** a non-default value (fail-fast).
- Public `/api/v1/*` is terminated at the edge proxy (SBGC-105); black-box
  probes of first-order API injection must therefore target the public Astro
  BFF routes (`/api/auth/*`) or run authenticated probes against Django on
  loopback/preview.  CI probes in this ticket hit Django directly (test
  client), which is the correct app-layer harness.
- Second-order priority was given to the user-controlled strings that exist:
  game names/slugs and classification submission notes (no CSV/Excel export
  views, no admin bulk actions building SQL, no search-reindex or webhook raw
  consumers exist — Section 3).

### 2.4 Rate-limit / circuit-breaker toggles for scan branches (playbook §0/§5.3)

- **`config/settings/base.py`**: `API_RATE_LIMITING_ENABLED` and
  `ADMIN_THROTTLING_ENABLED` are now read from the environment
  (`get_env_bool`, strict parsing, default `true`).  A dedicated scan/preview
  branch sets them false so automated probes are not swallowed by the
  load-shedders; both stay enabled on production-traffic branches.  Strict
  boolean parsing means a typo fails fast rather than silently disabling a
  control.

### 2.5 Tooling consolidation (playbook §6 — bandit)

- **`pyproject.toml`**: Ruff's flake8-bandit rule **`S608`** (hardcoded SQL
  built from untrusted strings) is enabled in the existing lint set, so raw
  SQL-string construction is a CI failure via `ruff check apps/backend`
  without adding a new external dependency.

### 2.6 Cache-table privileges (playbook §4.1)

- `db-provision-app-role.sql` grants `SELECT, INSERT, UPDATE, DELETE` on
  `public.django_cache` when the table already exists (it is created later by
  `createcachetable` under the migration role, which also inherits the
  `ALTER DEFAULT PRIVILEGES` grants set in the same script).

---

## 3. Code-level audit results

Static audit of the whole backend (`apps/*`), matching the playbook §1.1–1.5
five places where real injection bugs hide:

| Check | Result |
| --- | --- |
| `Model.objects.raw(...)` | **None** in application code |
| `.extra(...)` | **None** |
| `RawSQL(...)` / `annotate(RawSQL=...)` | **None** |
| `cursor.execute` with string interpolation (`f"…"`, `%`, `.format`) | **None** |
| `cursor.execute` (raw cursor) | Only inside PostgreSQL **introspection tests** (`test_pg_*.py`, `config/tests/test_database.py`), all constant strings or parameterised via the `%s` + params-list form (`conrelid = %s::regclass`, `[table]`) |
| Identifier-from-input (table/column/schema names) | **None** — no multi-tenant schema-per-tenant, no user-chosen export columns |
| `order_by(user_input)` / sort parameter | Not an injection vector through the ORM.  Public `sort=` is a Pydantic `Literal` **allowlist** (`games/schemas/catalogue.py`), so the authorisation-motivated allowlist pattern is already enforced at the schema boundary |
| Second-order consumers (exports, bulk admin actions, celery, webhooks, tsvector reindex) | **None exist** — the only stored-text consumers are ORM reads and `name__icontains` catalogue search (probe-covered) |
| Input-validation layering | `check-username` applies a strict `^[a-zA-Z0-9_-]{4,20}$` regex **before** any DB access (SBGC-107) — validation is a rate-limit/DoS control, *not* the injection control; parameterisation is (probe-covered in §4) |

**Audit conclusion:** zero raw-SQL construction in application code; every
user-controlled value reaches the database through the parameterised ORM or
Pydantic-validated parameters.  `S608` (Section 2.5) now makes any future
regression a static-analysis failure.

---

## 4. Injection-class probe log

Automated probes live in `apps/backend/security/tests/test_sql_injection_defense.py`
(7 tests, `DEBUG=False`).  Every row below was executed against the in-memory
test DB on 2026-09-06 and passed.

| Injection point | Class | T1 | Result | T1′ | Result | Status | Fix applied | Retest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET /api/v1/games/?q=` | Boolean-blind (3.1) | `widget' AND '1'='1` vs `'1'='2` | byte-identical 200 | `' OR '1'='1` / `x' OR 1=1--` | 200, empty, no markers | Not exploitable | none (parameterised `icontains`) | covered by suite |
| `GET /api/v1/games/?q=` | Time-blind (3.2) | `zzz' AND (SELECT CASE WHEN (1=1) THEN pg_sleep(5) …)--` | < 4 s, 200 | control `(1=2)` | < 4 s, 200 | Not exploitable | none | covered by suite |
| `GET /api/v1/games/?q=` | Error-based (3.3) | `…CAST((SELECT current_setting('server_version')) AS INT)--` | 200, no PG text | `…1=(1/0)--` | 200, no PG text | Not exploitable | none | covered by suite |
| `GET /api/v1/games/?q=` | UNION (3.4) | `x' UNION SELECT NULL,NULL,NULL--` | 200, no PG text | `x' UNION SELECT NULL,NULL,NULL--` (escaped variants) | 200 | Not exploitable | none | covered by suite |
| `POST /{admin}/login/` username | Boolean/Error (3.1/3.3) | `admin'--` | 200 re-render | `' OR '1'='1' --` | 200 re-render | Not exploitable | none (parameterised auth) | covered by suite |
| `GET /api/v1/auth/check-username` | Robustness (3.6) | `admin'--` | 422 (regex gate) | `robert'); DROP TABLE x;--` | 422 | Not exploitable (validation precedes DB) | none | covered by suite |
| Game `name` stored → catalogue `q` | Second-order (3.5) | Store `Game Robert'); DROP TABLE games_game;--` | round-trips literally; table intact | search `DROP TABLE` | 200; row still exists | Not exploitable | none (ORM/icontains readers only) | covered by suite |

---

## 5. Neon least-privilege runbook

### 5.1 Provisioning the scoped runtime role

```bash
psql "$MIGRATION_DATABASE_URL" \
  -v app_user="$APP_DJANGO_DB_USER" \
  -v app_password="$APP_DJANGO_DB_PASSWORD" \
  -f scripts/db-provision-app-role.sql
```

What the script grants (playbook §4.1):

- `CONNECT` on the current database; `USAGE` on schema `public`;
  `SELECT/INSERT/UPDATE/DELETE` on all tables; `USAGE, SELECT` on all
  sequences; matching `ALTER DEFAULT PRIVILEGES` for future objects;
  explicit DML on `django_cache` when present.
- Role flags are always `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`
  (re-run repairs any earlier ad-hoc elevation).
- Idempotent — safe on every release and for credential rotation.

Runtime `DATABASE_URL` must point at this role.  DDL stays on the
project-owner `MIGRATION_DATABASE_URL` (Section 2.1).

### 5.2 Why no `REPLICATION` matters — CVE-2026-6471 ("PostGREShell")

A disclosed PostgreSQL vulnerability (patched 2026-08-13; patched releases
14.24 / 15.19 / 16.15 / 17.11 / 18.6; PostgreSQL 13 EOL, unfixed) allows a
non-superuser role holding `REPLICATION` to supply an arbitrary filesystem
path as a logical-decoding output-plugin name — a privilege-escalation/RCE
path.  Neon makes logical replication available per project, so CDC roles are
a realistic presence.  **This role class is neutralised by construction here**:
the app role never holds `REPLICATION`, so an injection bug in application
code is serious (unauthorised data access) but cannot escalate to OS-level
code execution through the database layer.

Operator actions (require Neon console/CLI — not executable from this repo):

1. Confirm the Neon compute's PostgreSQL minor is on a patched build
   (≥ 16.15 for the 16 line, etc.) — a version bump is distinct from routine
   platform maintenance.
2. Audit every role: `SELECT rolname FROM pg_roles WHERE rolreplication;` —
   remove `REPLICATION` from anything that is not an active CDC integration.
3. Keep `DATABASE_URL` on the DML-only role (never an owner/CDC role).

### 5.3 TLS, IP allow, branching, pooling

- **TLS:** Neon connection strings default to `sslmode=require`; production
  enforces it via `DB_SSL_REQUIRE` (default true).  Never downgrade for local
  convenience and forget to revert.
- **IP allow (Pro):** restrict project ingress to stable egress IPs *if*
  Render's tier provides them — verify Render networking docs first.
- **Branching:** use copy-on-write branches for risky migrations and any live
  pentest pass, exactly as Section 0 prescribes for this exercise.
- **Pooling:** `-pooler` hostname = PgBouncer transaction mode.  Normal ORM
  traffic (extended query protocol) is unaffected; `SET/RESET`, `LISTEN/
  NOTIFY`, session advisory locks, and SQL `PREPARE` are not available over
  the pooler.  Django runs `CONN_MAX_AGE=0` in production (Section 2.2).

---

## 6. Render notes

- **Settings posture** (already enforced, verified by this pass): `DEBUG=False`
  fail-fast (SBGC-104), production `ALLOWED_HOSTS`, env-only `SECRET_KEY`/
  `DATABASE_URL`, session/CSRF cookie security, HSTS, and the SBGC-105 header
  baseline.
- **Pre-deploy gate:** `bash scripts/backend-deploy-check.sh` (configuration
  only, no DB) runs `manage.py check --deploy` — wired into CI and the
  `verify-security-posture.sh` runner.
- **Rate limiting:** Render adds no WAF by default; the SBGC-107 limiter +
  circuit breaker protect both this test cycle and real attackers.  Scan
  branches disable via the Section 2.4 toggles.
- **Logging:** time-based injection is a latency outlier first; alert on p99
  spikes for DB-touching endpoints in whatever APM/log tooling is wired up.

---

## 7. Tooling consolidation

| Tool | Role in this stack |
| --- | --- |
| Ruff `S608` (flake8-bandit) | Static gate for hardcoded-SQL anti-patterns in `apps/backend` (added, Section 2.5) |
| `pip-audit` / `npm audit` | Dependency-CVE gates (SBGC-108) — the way a future Django/driver-level SQLi CVE is caught |
| `manage.py check --deploy` | Pre-deploy configuration gate (CI + posture runner) |
| `sqlmap` (external, optional) | Black-box automation against a **preview branch on a Neon copy-on-write branch** only — start `--risk=1 --level=1`; never against anything backed by production data |

---

## 8. Out of scope, and why

- **Large-object / `COPY ... FROM PROGRAM` OS-execution mechanics.**  They
  assume an attacker already holds elevated database privileges; the fix is
  identical regardless of mechanism — the Section 5 least-privilege role —
  so walking the exploitation steps changes nothing operationally.
- **Step-by-step CVE-2026-6471 exploitation.**  Section 5.2 states the
  precondition and the two operator actions; turning the bug into a working
  exploit is unnecessary for those actions.
- **MSSQL/Oracle primitives** (`xp_cmdshell`, `UTL_INADDR`, …) — out of stack,
  not merely out of scope: the backend is PostgreSQL.

---

## Post-execution summary

**Issues found:** none exploitable.  Static audit found zero raw-SQL
construction; all probe classes returned parameterised, non-leaking behaviour.

**Fixes applied (defense-in-depth, not vulnerability responses):** Neon
pooler-aware migrate guard + `CONN_MAX_AGE=0` pin, DML-only role provisioning
script with `django_cache` grants, env-tunable scan-branch throttling toggles,
Ruff `S608` static gate, and the automated probe suite that pins this posture.

**Observations / operator actions pending:**
1. Confirm Neon compute is on a patched PostgreSQL build and audit
   `pg_roles.rolreplication` (Section 5.2).
2. Provision `app_django` and repoint `DATABASE_URL`; keep
   `MIGRATION_DATABASE_URL` on the owner role (Section 5.1).
3. Any future live black-box pass runs against a Neon branch + Render preview,
   never production (Section 1).
