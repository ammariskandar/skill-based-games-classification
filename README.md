# Skill-Based Games Classification

A web application that classifies games across three skill-based dimensions — **Micro**, **Mystiko**, and **Macro** — enabling players to discover, compare, and understand games through a structured skill lens rather than genre or difficulty alone.

## Current Status

**Monorepo skeleton / pre-development.** The repository structure, configuration files, and project documentation have been established. Application scaffolding (Astro frontend and Django backend) has not yet been performed; that work belongs to [SBGC-23](context.md#32-complete-jira-epic-and-task-registry).

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
│   ├── frontend/   # Astro application (to be initialized in SBGC-23)
│   └── backend/    # Django application (to be initialized in SBGC-23)
├── docs/           # Project documentation and architecture decision records
├── scripts/        # Simple cross-project helper scripts
├── context.md      # Canonical project context — read this first
├── skills.md       # Agent engineering skill — defines workflows and standards
├── README.md       # This file
├── .editorconfig   # Editor encoding and indentation settings
├── .gitignore      # Files excluded from version control
└── package.json    # npm workspace root
```

## Key References

- **[context.md](context.md)** — The single source of truth for product vision, architecture, data model, Jira tasks, and all project decisions.
- **[skills.md](skills.md)** — The engineering skill that defines the required development workflow, architectural boundaries, coding standards, and quality gates for any agent or contributor working on this project.

## Getting Started

Astro and Django initialization are handled by **SBGC-23**. See [context.md](context.md) for the full task registry and implementation order.
