# Skill-Based Games Classification

A web application that classifies games across three skill-based dimensions — **Micro**, **Mystiko**, and **Macro** — enabling players to discover, compare, and understand games through a structured skill lens rather than genre or difficulty alone.

## Current Status

**Application scaffolding complete.** Astro frontend and Django backend have been initialized. Tailwind CSS, Django Ninja, and PostgreSQL are not yet configured.

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

- **[context.md](context.md)** — The single source of truth for product vision, architecture, data model, Jira tasks, and all project decisions.
- **[skills.md](skills.md)** — The engineering skill that defines the required development workflow, architectural boundaries, coding standards, and quality gates for any agent or contributor working on this project.

## Getting Started

```bash
# Use the correct Node.js version
nvm use

# Install workspace dependencies
npm install

# Start the Astro dev server
npm run dev:frontend

# Start the Django dev server (separate terminal)
source apps/backend/.venv/bin/activate
python apps/backend/manage.py runserver
deactivate
```

Tailwind CSS, Django Ninja, and PostgreSQL are not configured yet. See [context.md](context.md) for the full task registry and implementation order.
