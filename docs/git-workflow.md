# Git Workflow

## Branch Model

- **`main`** is the stable, deployable branch. It must always pass CI.
- One feature branch per Jira task.
- Never commit directly to `main` except for emergency hotfixes with documented justification.

## Branch Naming

```
SBGC-<key>-short-description
```

Examples:

```
SBGC-22-monorepo-structure
SBGC-23-initialize-applications
SBGC-27-configure-git-and-ci-foundation
```

## Commit Messages

```
SBGC-<key> concise imperative summary
```

Examples:

```
SBGC-22 create monorepo structure
SBGC-26 establish code-quality tooling
```

Keep the summary under 72 characters when possible. Use the body for additional context if needed.

## Pull Requests

### Title

```
SBGC-<key> Human-readable task title
```

### Requirements

- All CI checks must pass (lint, format, type check, build, Django system check).
- The PR template must be filled out completely.
- At least one review approval is required before merging.
- No secrets or generated files in the diff.

### After Merge

- Delete the merged feature branch.
- Verify `main` still passes CI.

## CI Pipeline

GitHub Actions runs on every pull request targeting `main` and on every push to `main`. Two independent jobs (frontend and backend) enforce the same gates as local `npm run ci`.

Each job includes:

**Frontend:** Prettier format check, ESLint, astro check, frontend test entry point (placeholder), design-reference isolation check, Astro production build.

**Backend:** Ruff lint, Ruff format check, Django system check, backend test entry point (placeholder).

No real application test suites exist yet. The placeholder test entry points exit successfully by design. Green CI means all currently implemented gates passed — it does not mean behavioural coverage is complete. Real tests will replace placeholders under the relevant testing tickets.

Design-reference isolation is enforced both locally (`check:design-reference`) and in GitHub Actions.

See `.github/workflows/ci.yml` for the full definition.

## Local Quality Gate

Run before pushing:

```bash
npm run ci
```

This executes: formatting check, lint, type/Django check, and frontend production build.
