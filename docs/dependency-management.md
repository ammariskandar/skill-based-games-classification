# Dependency Management

## JavaScript / npm

- **npm** is the canonical JavaScript package manager for this project.
- The root `package-lock.json` is the **authoritative lockfile** — it pins exact versions of every installed npm package and must be committed.
- `apps/frontend` is the sole npm workspace. Frontend dependencies are declared in `apps/frontend/package.json`.
- Use `npm install <package> --workspace=apps/frontend` to add a workspace dependency.
- Run `npm install` from the repository root to install all workspace dependencies.
- The root `package.json` declares an `engines` field enforcing `node >= 22.12.0`.

## Python / pip

- Backend dependencies are managed in an isolated virtual environment at `apps/backend/.venv`.
- Pinned dependencies are recorded in `apps/backend/requirements.txt`, which must be committed.
- Use `python3 -m venv apps/backend/.venv` to create the environment (or run `npm run install:backend` from the root).
- Install dependencies with `apps/backend/.venv/bin/python -m pip install -r apps/backend/requirements.txt`.
- After adding a new package, freeze with `apps/backend/.venv/bin/python -m pip freeze > apps/backend/requirements.txt`.

## Policy

1. **Dependencies are added only when required by an approved Jira task.** Avoid speculative, unused, duplicate, or overlapping packages.
2. **Major-version upgrades** require testing and documentation before they are committed.
3. **Lockfiles and dependency manifests** (root `package-lock.json`, `apps/backend/requirements.txt`) must always be committed.
4. **Generated dependency directories** (`.venv/`, `node_modules/`, `dist/`, `.astro/`) must never be committed. These are already covered by the root `.gitignore`.
