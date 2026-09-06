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
