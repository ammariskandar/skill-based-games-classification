# MyGameDNA (Skill-Based Games Classification)

A web application that classifies games across three skill-based dimensions — **Micro**, **Mystiko**, and **Macro** — enabling players to discover, compare, and understand games through a structured skill lens rather than genre or difficulty alone.

## Current Status

**Foundation phase complete.** The following are configured and operational:

- Astro frontend with official Vercel adapter (`output: "server"`)
- Hybrid MPA rendering (SSR/on-demand by default, prerendered fixed routes)
- Tailwind CSS 4 via `@tailwindcss/vite`
- Shared `BaseLayout` component
- Dark-themed MyGameDNA application shell (Header, Navigation, Footer, responsive container, SEO metadata)
- Prerendered placeholder routes for `/catalogue` and `/rankings`
- Reusable UI foundations (Button, FormField, Card, Badge, DataTable, ItemList, EmptyState, LoadingState, ErrorState) — see [`docs/ui-foundations.md`](docs/ui-foundations.md)
- Micro/Mystiko/Macro visual system (legends, score summaries, Observable Plot bars, D3 radar) — see [`docs/skill-visual-system.md`](docs/skill-visual-system.md)
- Django backend skeleton with `django-environ`
- Environment-variable loading for both apps
- Code-quality tooling (Prettier, ESLint, astro check, Ruff)
- GitHub Actions CI (frontend + backend jobs)
- Locked design reference (`design-reference/`)

**Pending:** Django Ninja, PostgreSQL/Neon connectivity, Django domain apps and models, Steam integration, Django Admin product workflows, public dynamic catalogue/search/rankings/game pages, production deployment and security hardening, application test suites.

| Service  | Development URL           |
| -------- | ------------------------- |
| Frontend | http://localhost:4321     |
| Backend  | http://127.0.0.1:8000     |

## Stack

| Layer       | Technology                          |
| ----------- | ----------------------------------- |
| Frontend    | Astro, Tailwind CSS                 |
| Backend API | Django, Django Ninja                |
| Database    | PostgreSQL (Neon)                   |
| Hosting     | Vercel (frontend), Render (backend) |

## Rendering

Astro MPA with hybrid rendering:

- **SSR/on-demand** by default (`output: "server"` + Vercel adapter)
- **Prerendered** fixed informational routes (`/`, `/about`, `/methodology`)
- **Limited client-side islands** — no SPA router, no client framework

See [docs/frontend-architecture.md](docs/frontend-architecture.md) for routing conventions and planned pages.

## Styling

Tailwind CSS 4 via the `@tailwindcss/vite` Vite plugin. Utility-first, responsive, and accessible. A shared `BaseLayout` provides the document shell. See [docs/frontend-styling.md](docs/frontend-styling.md).

## Design Reference

A read-only Figma Make React/Vite prototype is archived at [`design-reference/figma-make-dark-ui/`](design-reference/figma-make-dark-ui/) (SBGC-136, archived by SBGC-137). It is **not** production code — do not edit, import, build, or deploy it. Use it only as a visual implementation guide. See [`design-reference/README.md`](design-reference/README.md).

## Software Development Reviews

A **read-only** senior software development reviewer ([`codex.md`](codex.md)) performs periodic audits covering product alignment, architecture, code quality, security, dependencies, documentation, and maintainability. Review outputs are saved as immutable governance records in [`reviews/`](reviews/).

- **Zed** — implementation-agent workflow (write code, edit files, commit, push)
- **VS Code + Codex** — read-only reviewer workflow (analyse, report, never modify)

See [`docs/software-development-reviews.md`](docs/software-development-reviews.md) and [`reviews/README.md`](reviews/README.md).

## Monorepo Directory Layout

```
skill-based-games-classification/
├── apps/
│   ├── frontend/   # Astro application (initialized)
│   └── backend/    # Django application (initialized)
├── docs/           # Project documentation and architecture decision records
├── scripts/        # Simple cross-project helper scripts
├── context.md      # Canonical project context — read this first
├── skills.md       # Agent engineering skill — defines workflows and standards
├── README.md       # This file
├── .editorconfig   # Editor encoding and indentation settings
├── .gitignore      # Files excluded from version control
├── .nvmrc          # Node.js version pinning
└── package.json    # npm workspace root
```

## Key References

- **[context.md](context.md)** — The single source of truth for product vision, architecture, data model, Jira tasks, and all project decisions. The canonical framework contains separate **Challenge** and **Reward** profiles, each scored on Micro, Mystiko, and Macro dimensions.
- **[skills.md](skills.md)** — The engineering skill that defines the required development workflow, architectural boundaries, coding standards, and quality gates for any agent or contributor working on this project. Its context-sources section is auto-generated by `scripts/update-skills-context.py` and must not be edited manually.
- **[docs/archive/context-pre-reward-framework-2026-07-22.md](docs/archive/context-pre-reward-framework-2026-07-22.md)** — Historical snapshot of the classification framework before the dual-profile (Challenge/Reward) model was introduced. Reference only; must not override the current `context.md`.

## Getting Started

```bash
# Use the correct Node.js version
nvm use

# Install workspace dependencies
npm install

# Configure environment variables (first time only)
cp apps/frontend/.env.example apps/frontend/.env
cp apps/backend/.env.example apps/backend/.env

# Create backend virtual environment (first time only)
npm run install:backend

# Start the Astro dev server
npm run dev:frontend

# Start the Django dev server (separate terminal)
source apps/backend/.venv/bin/activate
python apps/backend/manage.py runserver
deactivate
```

### Environment Variables

- Copy `.env.example` to `.env` for each app — **never commit `.env` files**.
- Frontend and backend use separate `.env` files (`apps/frontend/.env`, `apps/backend/.env`).
- In the frontend, only variables prefixed `PUBLIC_` are accessible in browser code.
- Backend secrets (keys, database URLs) belong only in Django's environment.
- In production, values are set in Vercel (frontend), Render (backend), and Neon (database) settings.

See [docs/environment-variables.md](docs/environment-variables.md) for the full variable reference.

### Adding Dependencies

```bash
# Frontend — add a package to the Astro workspace
npm install <package> --workspace=apps/frontend

# Backend — install into the virtual environment, then freeze
apps/backend/.venv/bin/python -m pip install <package>
apps/backend/.venv/bin/python -m pip freeze > apps/backend/requirements.txt
```

### Code Quality

```bash
npm run lint         # ESLint + Ruff
npm run format       # Prettier + Ruff (auto-fix)
npm run format:check # verify formatting without changing files
npm run check        # astro check + Django system check
npm run ci           # full local quality gate (format, lint, check, build)
```

See [docs/code-quality.md](docs/code-quality.md) for tool details and editor setup.

## Git Workflow

- **`main`** is the stable branch. Create one feature branch per Jira task: `SBGC-<key>-short-description`.
- Commit messages use the format `SBGC-<key> concise imperative summary`.
- Pull requests require all CI checks to pass before merging. See the [PR template](.github/pull_request_template.md).
- Run `npm run ci` locally before pushing — this executes the full quality gate.

See [docs/git-workflow.md](docs/git-workflow.md) for the complete workflow.

## CI

GitHub Actions runs on every pull request targeting `main` and on every push to `main`. Two independent jobs enforce the same gates as local `npm run ci`:

- **Frontend** — Prettier format check, ESLint, astro check, test entry point (placeholder), design-reference isolation check, Astro production build
- **Backend** — Ruff lint, Ruff format check, Django system check, test entry point (placeholder)

No real application test suites exist yet. Green CI means all currently implemented gates passed — it does not mean behavioural coverage is complete.

See `.github/workflows/ci.yml` for the pipeline definition.
