# Code Quality

## Tools

| Layer              | Tool                          | Purpose              | Config                          |
| ------------------ | ----------------------------- | -------------------- | ------------------------------- |
| Frontend formatting| Prettier + prettier-plugin-astro | Code formatting   | `apps/frontend/.prettierrc.mjs` |
| Frontend linting   | ESLint + eslint-plugin-astro  | Static analysis      | `apps/frontend/eslint.config.js`|
| Frontend types     | astro check (TypeScript)      | Type checking        | `apps/frontend/tsconfig.json`   |
| Backend formatting | Ruff                          | Code formatting      | `pyproject.toml` (root)         |
| Backend linting    | Ruff                          | Static analysis      | `pyproject.toml` (root)         |

## Formatting vs Linting vs Type Checking

- **Formatting** (Prettier, `ruff format`) — adjusts whitespace, line breaks, and quote style automatically. No semantic understanding. Always safe to auto-fix.
- **Linting** (ESLint, `ruff check`) — detects bugs, unused variables, import order issues, and style problems. Some rules offer auto-fixes; others require manual resolution.
- **Type checking** (`astro check`, TypeScript) — verifies that types are used correctly across the codebase. Catches missing properties, incorrect function signatures, and structural errors before runtime.

## Scripts

Run from the repository root:

| Command                | What it does                                   |
| ---------------------- | ---------------------------------------------- |
| `npm run lint`         | ESLint (frontend) + Ruff check (backend)       |
| `npm run format`       | Prettier (frontend) + Ruff format (backend)    |
| `npm run format:check` | Verify formatting without changing files       |
| `npm run check`        | astro check + Django system check              |

## Editor Recommendations

### VS Code

Recommended extensions are listed in `apps/frontend/.vscode/extensions.json`. Format-on-save is enabled by default via `apps/frontend/.vscode/settings.json`.

### Zed

Ruff is built into Zed — no additional configuration is required. Avoid committing personal Zed settings unless repository-level configuration is needed.

## Excluded Files

Generated and dependency directories are excluded from all tools:

- `dist/`, `.astro/`, `node_modules/` — Prettier, ESLint
- `.venv/`, `migrations/`, `__pycache__/` — Ruff

## Policy

1. **Run checks before every commit and pull request.** At minimum: `npm run lint && npm run format:check && npm run check`.
2. **Auto-fixes are acceptable** for formatting (`npm run format`) and for lint rules that offer safe fixes.
3. **Manual lint violations must be resolved** before merging — do not suppress rules without a documented reason.
4. **New rules** should be added conservatively and only when they catch real problems. Avoid subjective style preferences.
5. Do not use `--no-verify` to bypass checks unless there is an exceptional, documented reason.
