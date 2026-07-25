# Frontend (`apps/frontend`)

This directory is the **Astro frontend workspace** for the Skill-Based Games Classification monorepo. The root [`README.md`](../../README.md) is authoritative.

## Monorepo Context

- All commands run from the **repository root**, not from this directory.
- This workspace is managed through the root npm workspace and the single root `package-lock.json`. Do not create a second `package-lock.json` here.
- Do not treat this directory as a standalone project.

## Stack

- **Astro** — multi-page application framework
- **Tailwind CSS 4** — styling via `@tailwindcss/vite`
- **Vercel adapter** (`@astrojs/vercel`) — production serverless runtime
- **Rendering:** `output: "server"` (SSR/on-demand by default), explicit `export const prerender = true` for fixed informational routes

## Key Paths

| Path                    | Purpose                                     |
| ----------------------- | ------------------------------------------- |
| `src/pages/`            | File-based routes                           |
| `src/layouts/`          | Shared page shells (BaseLayout)             |
| `src/styles/global.css` | Tailwind import and global baseline         |
| `astro.config.mjs`      | Astro configuration (adapter, Vite, output) |

## Boundary

- Do **not** import or build from `design-reference/` — it is a read-only design reference, not application source.
- Django owns all authoritative data and business logic. The frontend consumes the Django API and renders the result.

## Further Reading

- [Root README](../../README.md) — project overview, setup, CI, workflow
- [Frontend Architecture](../../docs/frontend-architecture.md) — MPA routing, hybrid rendering, planned routes
- [Frontend Styling](../../docs/frontend-styling.md) — Tailwind 4 conventions, visual identity
