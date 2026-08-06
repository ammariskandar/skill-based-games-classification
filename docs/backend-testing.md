# Backend Testing — SBGC-44

Testing conventions, commands, and architecture for the Django backend.

## Philosophy

- **Django's test runner** with Python `unittest` — no pytest, no factory-boy.
- **`SimpleTestCase`** is the default for non-database tests.
- **`TestCase`** for database-backed tests (Admin, future models).
- **`TransactionTestCase`** only for real transaction-boundary behavior.
- **Subprocess tests** only for settings import, process environment, deployment failure, and command-level behavior that cannot be isolated in-process.
- **No live network** — all external-service tests use mocks, fakes, or adapter inspection.

## Commands

| Command | Purpose |
|---------|---------|
| `npm run test:backend` | Canonical normal suite (deterministic order) |
| `npm run test:backend:discovery` | Discovery audit — reports counts by module |
| `npm run test:backend:reverse` | Reverse-order run (detects order dependencies) |
| `npm run test:backend:shuffle` | Shuffled run with random seed (detects order dependencies) |
| `npm run test:backend:warnings` | Suite with `python -Wa` (all warnings visible) |

All commands use `--settings=config.settings.test --noinput`.

## Test Taxonomy

### `unittest.TestCase`

Pure Python behavior with no database and no configured Django dependency.

*Currently unused in this project — all tests are Django-aware.*

### `SimpleTestCase`

Django-aware configuration, routing, schema, script, logging, and mocked transport tests without database access.  **This is the default.**

Used by: API tests, security/config tests, Steam service tests, operations tests.

### `TestCase`

Database-backed authentication, Admin, and future model tests.

Prefer `setUpTestData()` for class-shared immutable data.

Used by: Admin tests, database tests.

### `TransactionTestCase`

Only for real transaction-boundary behavior.

*Currently unused — no multi-transaction tests exist yet.*

### Subprocess tests

Only for: settings import, process environment, deployment/startup failure, import side effects, command-level behavior.

Uses shared helpers from `config/test_helpers.py`.

## Package and Naming Conventions

```
tests/
  __init__.py
  test_<subject>.py
```

- Files: `test_*.py`
- Classes: descriptive `*Tests`
- Methods: descriptive `test_*`

No `tests.py` alongside a `tests/` package in the same directory.

Stub `tests.py` files (empty Django-generated placeholders) are replaced with `tests/` packages when real tests are added.

## Discovery Audit

`scripts/backend-test-discovery.sh` runs the full suite at verbosity 2 and parses the output to report:

- Total discovered tests
- Counts by module
- Structural defects (duplicate IDs, empty modules)

Enforced in CI.  No hard-coded expected count — the audit validates structure, not quantity.

## Subprocess Environments

`config/test_helpers.py` provides:

- **`minimal_subprocess_env(**extras)`** — inherits only safe variables (PATH, locale, temp dirs).  Never inherits `DJANGO_SETTINGS_MODULE`, `DJANGO_SKIP_DOTENV`, `DATABASE_URL`, `DJANGO_SECRET_KEY`, Steam keys, Admin path, Render/proxy values.
- **`prod_test_env(**overrides)`** — valid production-like dummy values for settings-import subprocess tests.
- **`run_manage(*args, env=...)`** — safe manage.py subprocess execution.

Rules:
- Production subprocess tests explicitly receive production variables.
- Test-settings subprocesses receive deterministic test configuration.
- Development subprocess tests may exercise intended `.env` loading in a fresh process.
- `DJANGO_SKIP_DOTENV` is an internal test-isolation mechanism — not a public configuration variable.

## Database Isolation

- Default test settings use in-memory SQLite (`:memory:`).
- `SimpleTestCase` for no-database tests (default).
- `TestCase` for database-backed tests.
- No test contacts Neon or any external database.
- Future SBGC-52 lane: isolated disposable PostgreSQL for constraints, migrations, indexes, transaction behavior — separate command/CI job, never production Neon.

## Network Isolation

- **Pure tests:** No Requests objects or network.
- **Real adapter-policy tests:** Instantiate real Requests/urllib3 objects but send no request.
- **Mocked transport tests:** Inject fake/mock sessions.
- **Future contract tests:** Use representative safe payloads, not live Steam.

`config/test_helpers.py` provides `assert_no_live_requests()` and `NetworkProhibitedError` for test suites that must not make external calls.

All current Steam, settings, and operations tests make no external requests.

## Mocking Conventions

- Use `unittest.mock.patch` where the symbol is looked up.
- Use `autospec=True` or an appropriate spec where useful.
- Use fakes for streaming/protocol behavior (e.g., `_fake_response` in Steam tests).
- Use mocks for interaction assertions (e.g., `MagicMock` sessions).
- Do not mock the unit under test.
- Do not mock ordinary ORM behavior in model tests.
- Avoid private-helper call-order assertions.

## Logging and Warning Discipline

- Use `assertLogs` for expected log output.
- Use `assertWarns` for expected warnings.
- Use redirected stdout/stderr or subprocess capture for command output.
- The normal suite should not print large expected tracebacks or warning stacks.

`npm run test:backend:warnings` runs with `python -Wa` to surface all warnings.  Warnings are classified as:

- **Project defect** — must be fixed.
- **Intentional tested warning** — accepted (e.g., staged HSTS, malformed database URL).
- **Third-party warning** — documented, not actionable in this project.
- **Future dependency concern** — tracked for later review.

Warnings mode is not currently in required CI due to third-party warnings that cannot be made clean without unrelated dependency work.

## Order Independence

- `npm run test:backend:reverse` — `--reverse`
- `npm run test:backend:shuffle` — `--shuffle` (random seed recorded)

Both are run during SBGC-44 verification.  They are not in normal CI to keep duration proportionate.  Normal CI remains deterministic.

## Performance

- Baseline duration: ~41 seconds (451 tests).
- No unnecessary `TransactionTestCase`.
- No repeated subprocess imports or collectstatic runs.
- No database-enabled tests using `TestCase` when `SimpleTestCase` suffices.
- Slow-test review expectations documented but no hard-coded threshold.

## Shared Test Helpers

`config/test_helpers.py`:

| Helper | Purpose |
|--------|---------|
| `minimal_subprocess_env(**extras)` | Clean subprocess environment |
| `prod_test_env(**overrides)` | Production dummy settings |
| `run_manage(*args, env=...)` | Safe manage.py subprocess |
| `assert_no_live_requests()` | Network prohibition guard |
| `audit_discovery()` | Programmatic discovery audit |

## CI Parity

- `npm run ci` runs: format check, lint, discovery audit, deploy check, Django check, tests, design-reference check, frontend build
- `npm run test:backend` is the canonical normal suite
- GitHub Actions uses `npm run ci`
- No command or label hard-codes the current test count
- Test settings always explicit (`--settings=config.settings.test`)

## Future PostgreSQL Lane (SBGC-52)

- Isolated disposable PostgreSQL (not production Neon)
- Command: `POSTGRES_TEST_DATABASE_URL='...' npm run test:backend:postgresql`
- Settings: `config.settings.postgresql_test`
- Used for: constraints, migrations, indexes, transaction behavior, engine-specific semantics
- PostgreSQL 16 in CI (GitHub Actions service container)
- See `docs/postgresql-verification.md`.

## PostgreSQL Lane (SBGC-52)

The PostgreSQL verification lane (`config.settings.postgresql_test`) is
operational — 51 PostgreSQL-specific tests covering constraints, migrations,
indexes, transactions, and concurrent uniqueness on isolated PostgreSQL 16.
All PG tests gracefully skip on SQLite.  CI includes a `postgres:16` service
container for the PostgreSQL job.  See `docs/postgresql-verification.md`.

## Current Limitations

- No pytest, factory-boy, coverage, or snapshot testing.
- Warnings mode (`python -Wa`) is not in required CI.
- No browser or integration testing.
- Shuffle/reverse not in normal CI.
- Some subprocess tests in test_security.py and test_steam.py use `os.environ` directly rather than the shared helper — acceptable but not canonical.
