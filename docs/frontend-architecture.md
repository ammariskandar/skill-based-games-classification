# Frontend Architecture

## Rendering Model

Astro is configured as a **multi-page application (MPA)**, not a single-page app. There is no client-side router. Each navigation request loads a full HTML page from the server.

| Mode              | Use case                              |
| ----------------- | ------------------------------------- |
| `output: "server"`| Canonical. All routes render on the server by default. |
| `prerender = true`| Fixed informational pages built to static HTML at build time. |

The Vercel adapter (`@astrojs/vercel`) is the production runtime target. Dynamic routes render on-demand via serverless functions; prerendered pages are served as static assets.

## Routing

Routing is **file-based** under `src/pages/`:

```
src/pages/
├── index.astro          →  /
├── about.astro          →  /about
├── methodology.astro    →  /methodology
├── games/
│   └── [slug].astro     →  /games/:slug       (dynamic, not yet created)
├── catalogue.astro      →  /catalogue          (planned)
├── search.astro         →  /search             (planned)
└── rankings/
    └── [dimension].astro → /rankings/:dimension (planned)
```

### Current Routes

| Route           | File                                      | Rendering    |
| --------------- | ----------------------------------------- | ------------ |
| `/`             | `src/pages/index.astro`                   | Prerendered  |
| `/about`        | `src/pages/about.astro`                   | Prerendered  |
| `/methodology`  | `src/pages/methodology.astro`             | Prerendered  |

### Planned Routes

| Route                  | File                              | Rendering      |
| ---------------------- | --------------------------------- | -------------- |
| `/games/:slug`         | `src/pages/games/[slug].astro`    | SSR/on-demand  |
| `/catalogue`           | `src/pages/catalogue.astro`       | SSR (likely)   |
| `/search`              | `src/pages/search.astro`          | SSR (likely)   |
| `/rankings/:dimension` | `src/pages/rankings/[dimension].astro` | SSR (likely) |

Future dynamic routes **must not be prerendered** unless an explicit product decision changes that. Data-driven pages require live API data and must render on-demand.

## Client-Side JavaScript

Client-side JavaScript is limited to **bounded Astro islands**. Components that need interactivity opt in via client directives (`client:load`, `client:idle`, etc.). No SPA framework (React, Vue, Svelte) is required or planned unless a specific Jira task introduces one.

## Architecture Boundary

- **Django** owns authoritative data, business logic, classification rules, search indexing, and the admin interface.
- **Astro** owns routing, page rendering, presentation, asset delivery, server-side API consumption, and SEO metadata.
- The frontend never holds business logic; it consumes the Django API and renders the result.

## Vercel Adapter

The `@astrojs/vercel` adapter translates Astro's server output into Vercel serverless functions. `output: "server"` enables on-demand rendering for any route that does not declare `export const prerender = true`.
