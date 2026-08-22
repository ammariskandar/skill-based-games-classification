# MyGameDNA — Skill-Based Games Classification

MyGameDNA is a web application that classifies games across three skill-based
dimensions — **Micro**, **Mystiko**, and **Macro** — within two separate profiles
(**Challenge** and **Reward**), so players can understand and compare games through
a structured skill lens rather than genre or difficulty alone.

## Project status

- **Status:** Active development — not yet finished.
- **Approximate roadmap completion:** ~42% — measured by completed Jira issues
  against the current project issue inventory. This is a roadmap indicator, not
  a percentage of code or effort.
- **README last updated:** 22 August 2026, 13:59 MYT (UTC+8).
- **Estimated completion:** approximately 1 month — target late September 2026,
  subject to scope and validation findings. This is an estimate, not a deadline.

## What MyGameDNA does

Traditional game taxonomies group games by genre, platform, or difficulty.
MyGameDNA instead scores each game on the same three skill dimensions —
Micro (fine execution/timing), Mystiko (hidden knowledge/decision-making under
uncertainty), and Macro (strategy/planning) — and separates the skills a game
**challenges** a player to use from the skills it **rewards**. This produces a
comparable, product-consistent classification that is derived from editorial
submissions through a governed statistical model rather than a single opinion.

See [context.md](context.md) for the canonical product vision, and
[docs/statistical_model.md](docs/statistical_model.md) for the mathematics.

## Current capabilities

The project has moved well beyond a skeleton. What is implemented and tested today:

### Game / domain management

- Canonical `Game` model with Steam and Manual source types.
- Public listing and content-type rules (only published `game` records are
  publicly listable; hidden/draft/archived/non-game are excluded).
- Source-specific behaviour (Steam-owned fields vs manual-editable fields).
- Image/display handling with a canonical display-image fallback.
- Archive and hard-delete workflows. See
  [docs/game-model.md](docs/game-model.md) and
  [docs/source-specific-behaviour.md](docs/source-specific-behaviour.md).

### Steam integration

- Steam metadata import (App Details → persisted Game).
- Metadata refresh (manual Admin action and scheduled).
- Persisted Steam metadata and image URLs.
- HTTP import/refresh endpoints plus Django Admin workflows.
- Scheduled daily refresh with retry, audit, and operator email notification.
  See [docs/steam-integration.md](docs/steam-integration.md) and
  [docs/scheduled-steam-refresh.md](docs/scheduled-steam-refresh.md).

### Editorial / classification system

- Multi-user editorial submissions with role-aware weighting.
- Derived classification engine: Method 1 (role-aware anchored), Method 2
  (Isolation Forest), Method 3 (LoOP), and BHPCM unification.
- Provisional and unified regimes, and a Confidence Level.
- Persisted Final Classification. See
  [docs/classification-submissions.md](docs/classification-submissions.md) and
  [docs/statistical_model.md](docs/statistical_model.md).

### Admin

- Game and classification management.
- Read-only derived outputs (Final Classification).
- Safe bulk actions (publish/hide/archive; bulk delete disabled).
- Audit logging and scheduler audit visibility.

### Public frontend

- `GET /api/v1/games/{slug}` (SBGC-71) — public game-detail API.
- Astro `/games/{slug}` (SBGC-72/73/74) — server-rendered game page.
- Normalised Steam/Manual Game details.
- Classification display (Challenge/Reward profiles, confidence, state).
- Game Information dialog.
- Exceptional-state handling (404 / 5xx / missing image / sparse metadata).

Catalogue, search, and rankings pages are **not yet implemented** — they remain
route placeholders.

## Architecture

| Layer       | Technology                                        |
| ----------- | ------------------------------------------------- |
| Frontend    | Astro 7, TypeScript (strict), Tailwind CSS 4      |
| Backend API | Python 3.12, Django 6, Django Ninja               |
| Database    | PostgreSQL (Neon production); SQLite local dev    |
| Hosting     | Vercel (frontend), Render (backend), Neon (DB)    |
| Operations  | Django Admin, Render Cron, GitHub Actions         |

- **Frontend** is an Astro multi-page app: server-rendered/on-demand by default
  (`output: "server"` + Vercel adapter) with a few prerendered informational
  routes. Client JavaScript is minimal and used only where interaction requires
  it. See [docs/frontend-architecture.md](docs/frontend-architecture.md).
- **Backend** owns all domain logic, the classification engine, and the API.
  Django remains the single source of truth; the frontend only composes and
  renders API data. See [docs/backend-architecture.md](docs/backend-architecture.md)
  and [docs/backend-api.md](docs/backend-api.md).
- **Production deployment is the stated direction but is not yet fully
  verified** against live Render/Vercel/Neon services — see
  [render.yaml](render.yaml) and [docs/backend-operations.md](docs/backend-operations.md).

## Classification model

Each game has a **Challenge** profile and a **Reward** profile, each scoring
Micro, Mystiko, and Macro (0–100). Scores are derived from editorial submissions
through Methods 1–3 and the BHPCM unification layer, producing either a
**provisional** (small-N) or **unified** Final Classification with a Confidence
Level. The full mathematical specification is in
[docs/statistical_model.md](docs/statistical_model.md).

## Current public experience

A visitor can open a classified game at `/games/{slug}` and see its artwork,
source, and Skill Classification (Challenge/Reward profiles, confidence, and
provisional/stale status). Secondary metadata (developer, release date, source,
description) lives in a "Game information" dialog. Unknown/hidden games return a
real 404, and backend failures return a real 500 — neither leaks backend detail
nor fabricates data.

## Remaining roadmap

Major remaining areas (not exhaustive):

- Finish Public Game Pages (metadata completeness).
- Richer Micro/Macro/Mystiko visualisation (e.g. the planned D3 radar).
- Catalogue, search, and discovery.
- Rankings and skill-based filtering.
- Broader integration/error hardening.
- Community scoring and recommendation (final-product phases).
- Production deployment and release verification.

See the registry in [context.md](context.md) for the full ticket inventory.

## Monorepo directory layout

```
skill-based-games-classification/
├── apps/
│   ├── frontend/   # Astro application
│   └── backend/    # Django application
├── docs/           # Project documentation and architecture decision records
├── scripts/        # Cross-project helper scripts
├── reviews/        # Read-only software-development review records
├── context.md      # Canonical project context — read this first
├── skills.md       # Agent engineering skill — workflows and standards
├── README.md       # This file
├── render.yaml     # Render blueprint (backend web service)
├── .nvmrc          # Node.js version pinning
└── package.json    # npm workspace root
```

## Getting started

```bash
# Use the correct Node.js version
nvm use

# Install workspace dependencies
npm install

# Configure environment variables (first time only)
cp apps/frontend/.env.example apps/frontend/.env
cp apps/backend/.env.example apps/backend/.env

# Create the backend virtual environment (first time only)
npm run install:backend

# Start the Astro dev server
npm run dev:frontend

# Start the Django dev server (separate terminal)
source apps/backend/.venv/bin/activate
python apps/backend/manage.py runserver
deactivate
```

| Service  | Development URL        |
| -------- | ---------------------- |
| Frontend | http://localhost:4321  |
| Backend  | http://127.0.0.1:8000  |

### Environment variables

- Copy `.env.example` to `.env` for each app — **never commit `.env` files**.
- Frontend and backend use separate `.env` files (`apps/frontend/.env`,
  `apps/backend/.env`).
- In the frontend, only `PUBLIC_`-prefixed variables reach browser code.
- Backend secrets (keys, database URLs) belong only in Django's environment.
- In production, values are set in Vercel, Render, and Neon settings.

See [docs/environment-variables.md](docs/environment-variables.md).

### Adding dependencies

```bash
# Frontend
npm install <package> --workspace=apps/frontend

# Backend — install into the virtual environment, then freeze
apps/backend/.venv/bin/python -m pip install <package>
apps/backend/.venv/bin/python -m pip freeze > apps/backend/requirements.txt
```

### Code quality

```bash
npm run lint         # ESLint + Ruff
npm run format       # Prettier + Ruff (auto-fix)
npm run format:check # verify formatting without changing files
npm run check        # astro check + Django system check
npm run ci           # full local quality gate (format, lint, check, test, build)
```

See [docs/code-quality.md](docs/code-quality.md).

## Git workflow

- **`main`** is the stable branch. Create one feature branch per Jira task:
  `SBGC-<key>-short-description`.
- Commit messages use the format `SBGC-<key> concise imperative summary`.
- Pull requests require all CI checks to pass before merging. See the
  [PR template](.github/pull_request_template.md).
- Run `npm run ci` locally before pushing.

See [docs/git-workflow.md](docs/git-workflow.md).

## CI

GitHub Actions runs on every pull request to `main` and every push to `main`
(see [.github/workflows/ci.yml](.github/workflows/ci.yml)):

- **Frontend** — Prettier, ESLint, astro check, Vitest tests, design-reference
  isolation check, and production build.
- **Backend (SQLite)** — Ruff lint/format, BasedPyright type check, Django
  system check, and the Django test suite.
- **Backend (PostgreSQL 16)** — the PostgreSQL test lane.

## Design reference

A read-only Figma Make React/Vite prototype is archived at
[`design-reference/figma-make-dark-ui/`](design-reference/figma-make-dark-ui/).
It is **not** production code — do not edit, import, build, or deploy it. Use it
only as a visual guide. See [design-reference/README.md](design-reference/README.md).

## Software development reviews

A read-only senior reviewer ([`codex.md`](codex.md)) performs periodic audits.
Review outputs are saved as governance records in [`reviews/`](reviews/). See
[docs/software-development-reviews.md](docs/software-development-reviews.md).

## Documentation

- [context.md](context.md) — canonical product vision, architecture, data model,
  and full Jira registry.
- [docs/statistical_model.md](docs/statistical_model.md) — classification mathematics.
- [docs/backend-api.md](docs/backend-api.md) — public API contract.
- [docs/frontend-architecture.md](docs/frontend-architecture.md) — frontend
  rendering model and conventions.
- [docs/frontend-api-layer.md](docs/frontend-api-layer.md) — server-side API client.
- [docs/backend-operations.md](docs/backend-operations.md) — deployment/operations.
