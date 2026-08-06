# Backend Typing — SBGC-53

Type-checking conventions for the MyGameDNA Django backend using
BasedPyright with django-stubs.

## Toolchain

| Component | Version | Role |
|-----------|---------|------|
| [BasedPyright](https://github.com/DetachHead/basedpyright) | 1.32.1 | Type checker (CLI + LSP) |
| [django-stubs](https://github.com/typeddjango/django-stubs) | 6.0.2 | Django type stubs |
| [django-stubs-ext](https://github.com/typeddjango/django-stubs) | 6.0.2 | Django stub extensions |

## Configuration

`pyrightconfig.json` at the repository root:

```json
{
  "venvPath": "apps/backend",
  "venv": ".venv",
  "pythonVersion": "3.12",
  "include": ["apps/backend"],
  "exclude": [
    "apps/backend/.venv",
    "**/__pycache__",
    "apps/backend/**/migrations",
    "apps/backend/staticfiles",
    "apps/frontend"
  ],
  "extraPaths": ["apps/backend"],
  "typeCheckingMode": "standard",
  "reportMissingTypeStubs": false
}
```

Key decisions:

- **`reportMissingTypeStubs: false`** — the only broad diagnostic disable.
  Third-party packages without stubs are accepted; this project does not
  maintain its own stub library.
- **Migrations excluded** — auto-generated migration files are not type-checked.
- **Static files excluded** — collected WhiteNoise output (`staticfiles/`) is
  never type-checked.
- **`extraPaths`** — `apps/backend` is added so that project imports resolve
  correctly without editable installs or `PYTHONPATH` manipulation.

## Dependencies

- **`django-stubs`** provides types for Django ORM, test framework, and
  management commands.
- **`django-stubs-ext`** provides plugin hooks for the mypy daemon — the
  mypy plugin is **not** used under BasedPyright, but the package is kept
  as a Django-stubs companion for forward compatibility.
- **`django-types` is not used.** It would conflict with `django-stubs`.

## Running the Type Checker

### CLI (authoritative)

```bash
npm run typecheck:backend
```

This runs:

```bash
apps/backend/.venv/bin/basedpyright --project .
```

The CLI result is the **repository truth** for type checking.  Zed's LSP
diagnostics are a development convenience and may differ.

### Zed (Flatpak)

If using Flatpak Zed:

1. Ensure the Flatpak has `filesystems=home` (required for project access).
2. Open any backend Python file.
3. Run `Toolchain: Select` from the command palette.
4. Select the project virtual-environment interpreter:

   ```
   <repository>/apps/backend/.venv/bin/python
   ```

5. Restart the Python language server (`Python: Restart Server`).
6. Verify with:

   ```bash
   npm run typecheck:backend
   ```

**Do not** commit `.zed/settings.json` — it contains local-machine paths
and is intentionally untracked.

## CI Enforcement

Type checking runs in GitHub Actions as part of the backend job:

```yaml
- name: Type check (BasedPyright)
  run: npm run typecheck:backend
```

It is also included in the local CI chain:

```bash
npm run ci
```

## Suppression Policy

- **No global diagnostic disables** except `reportMissingTypeStubs`.
- **Per-line suppressions only** — `# pyright: ignore[reportXxx]`.
- Suppressions are used at framework boundaries where Django's dynamic
  patterns (e.g., `_meta`, reverse relations, manager assignment) cannot
  be fully typed with current stubs.
- Centralised helpers (`config/env_typing.py`, `config/test_typing.py`)
  isolate framework-boundary casts so individual tests and settings
  modules do not need per-line suppressions.

## Known Limitations

- **`django-stubs` mypy plugin does not run under BasedPyright.**
  Some reverse-relation and manager-assignment patterns require explicit
  `# pyright: ignore` suppressions.
- **`config/model_typing.py`** — helper for type-safe Django model `_meta`
  inspection.  Does not require an initialised Django app registry.
  Renamed from `test_typing.py` in SBGC-181 to avoid triggering the
  discovery audit's `test_*.py` scan (it is a helper, not a test module).
- **Zed LSP diagnostics** may differ from CLI BasedPyright due to
  incremental analysis differences.  The CLI result is authoritative.
- **No `reportMissingImports` override** — the default `standard` mode
  already enables it.

## Adding Type Hints

- Prefer built-in types (`list`, `dict`, `str | None`) over `typing`
  imports where Python 3.12+ syntax allows.
- Use `from __future__ import annotations` at the top of every module.
- Use `TYPE_CHECKING` for import-only type dependencies to avoid
  circular imports.
- Annotate public APIs (services, queryset methods, view parameters,
  schema fields).
- Do not annotate obvious locals or purely internal helpers where the
  type is unambiguous.
