# Scripts

This folder contains simple, documented helper scripts that operate across the monorepo.

## Guidelines

- **App-specific logic** (build steps, test runners, deployment helpers) belongs inside the relevant `apps/` directory, not here.
- Scripts must remain **simple and self-contained** — if a script grows complex enough to require its own dependencies or tests, it likely belongs in an app or a dedicated tool package.
- Every script must include a brief **comment or docstring** explaining its purpose, inputs, and expected output.

### `update-skills-context.py`

Synchronises the auto-generated context-sources section of `skills.md` with the canonical `context.md` and archived context. Run via:

```bash
npm run update:skills-context
```

The generated section in `skills.md` is marked with `<!-- BEGIN/END GENERATED CONTEXT SOURCES -->` — **do not edit it manually**.

## Security verification scripts (SBGC-109)

### `verify-security-posture.sh`

Unified Epic SBGC-16 posture gate. Runs six checks and fails fast (exit 1) on
any violation: backend `pip-audit`, frontend `npm audit`, a tracked-repo scan
for owner identifiers / private-key material / certificate files, Django
migration drift, the configuration-only deploy check, and the full
`security.tests` suite.

```bash
bash scripts/verify-security-posture.sh
```

Requires the backend venv (`npm run install:backend`) and an installed
frontend workspace.  The secret scan excludes `context.md` (immutable project
journal) and the script itself.

### `verify-ingress-boundary.sh`

Live ingress audit against a deployed environment. Confirms the edge drops
external `/api/v1/*` calls, the standard `/admin/` returns 404, the obfuscated
admin path resolves, the internal API answers, and neither surface leaks
application banner headers (`X-Powered-By` / WSGI runtime).

```bash
bash scripts/verify-ingress-boundary.sh [PUBLIC_BASE_URL] [INTERNAL_API_URL]
```

### `db-provision-app-role.sql`

Least-privilege PostgreSQL role provisioning for Neon/Render (SBGC-185).
Creates or resets the scoped DML-only runtime role (`app_django` by default)
with `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`, grants DML on the
public schema plus default privileges, and grants access to the unmanaged
`django_cache` table when present.  Idempotent — safe on every release.

```bash
psql "$MIGRATION_DATABASE_URL" \
  -v app_user="$APP_DJANGO_DB_USER" \
  -v app_password="$APP_DJANGO_DB_PASSWORD" \
  -f scripts/db-provision-app-role.sql
```

See [docs/sql-injection-defense-in-depth.md](../docs/sql-injection-defense-in-depth.md)
for the full playbook, audit, and CVE-2026-6471 notes.

## Catalogue data scripts (SBGC-20)

### `verify-initial-catalogue.py`

Validates `apps/backend/games/fixtures/initial_catalogue_200.json`, the curated
200-game manifest for the initial public catalogue (SBGC-125).  Offline checks
prove the 175 `STEAM` / 25 `MANUAL` split, slug and AppID uniqueness, the schema
contract, and that aesthetics and skill biases match the canonical enums.

```bash
apps/backend/.venv/bin/python scripts/verify-initial-catalogue.py
apps/backend/.venv/bin/python scripts/verify-initial-catalogue.py --online
```

`--online` additionally queries `store.steampowered.com` for every AppID and
asserts it resolves to a standalone base game (`type: "game"`), which is the gate
to run before starting the SBGC-126 bulk import.  The Steam Store API rate-limits
bursts, so a lone `success: false` should be re-checked before a title is treated
as invalid.  The offline checks are mirrored by
`apps/backend/games/tests/test_initial_catalogue_manifest.py` and run in CI.

See [docs/catalogue-composition.md](../docs/catalogue-composition.md) for the
distribution breakdown and curation notes.
