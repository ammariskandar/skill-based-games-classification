# Frontend Architecture

**Public product name:** MyGameDNA

## Rendering Model

Astro is configured as a **multi-page application (MPA)**, not a single-page app. There is no client-side router. Each navigation request loads a full HTML page from the server.

| Mode              | Use case                              |
| ----------------- | ------------------------------------- |
| `output: "server"`| Canonical. All routes render on the server by default. |
| `prerender = true`| Fixed informational pages built to static HTML at build time. |

The Vercel adapter (`@astrojs/vercel`) is the production runtime target. Dynamic routes render on-demand via serverless functions; prerendered pages are served as static assets.

## Application Shell

| Component     | File                                            | Responsibility                                    |
| ------------- | ----------------------------------------------- | ------------------------------------------------- |
| `BaseLayout`  | `src/layouts/BaseLayout.astro`                  | HTML shell, global CSS, SEO metadata, skip link, `<Header>`, `<main>`, `<Footer>` |
| `Header`      | `src/components/Header.astro`                   | Site identity (MyGameDNA), masthead, includes `<Navigation>` |
| `Navigation`  | `src/components/Navigation.astro`               | Mandatory separate component. Semantic `<nav>`, current-route detection via Astro.url, `aria-current`, visible focus, no SPA routing, no JavaScript |
| `Footer`      | `src/components/Footer.astro`                   | Site identity, product statement, Methodology/About links, copyright year, non-affiliation notice |

### Responsive Container

Pages render inside a single `<main>` landmark with `max-w-6xl`, centered layout, and responsive padding (`px-4 py-8 sm:px-6 sm:py-12 lg:px-8`). Shared via BaseLayout.

### Active-Link Strategy

`Navigation.astro` reads `Astro.url.pathname` and applies `aria-current="page"` plus a highlighted visual state (`bg-surface-2 text-text`) when the current route matches a link. Active state uses background contrast, not colour alone.

### SEO Metadata

`BaseLayout.astro` owns default `<title>`, `<meta name="description">`, Open Graph, Twitter card, canonical URL, and `<meta name="robots">`. Each page overrides title and description via props. Canonical URL is constructed from `PUBLIC_SITE_URL` with a safe local fallback.

## Routing

Routing is **file-based** under `src/pages/`:

```
src/pages/
├── index.astro          →  /              (prerendered)
├── about.astro          →  /about         (prerendered)
├── methodology.astro    →  /methodology   (prerendered)
├── catalogue.astro      →  /catalogue     (prerendered placeholder)
├── rankings.astro       →  /rankings      (prerendered placeholder)
├── games/
│   └── [slug].astro     →  /games/:slug   (dynamic, not yet created)
└── search.astro         →  /search        (planned)
```

Future dynamic routes **must not be prerendered** unless an explicit product decision changes that. Data-driven pages require live API data and must render on-demand.

## Client-Side JavaScript

Client-side JavaScript is limited to **bounded Astro islands**. Components that need interactivity opt in via client directives (`client:load`, `client:idle`, etc.). No SPA framework (React, Vue, Svelte) is required or planned unless a specific Jira task introduces one.

## Architecture Boundary

- **Django** owns authoritative data, business logic, classification rules, search indexing, and the admin interface.
- **Astro** owns routing, page rendering, presentation, asset delivery, server-side API consumption, and SEO metadata.
- The frontend never holds business logic; it consumes the Django API and renders the result.

## Vercel Adapter

The `@astrojs/vercel` adapter translates Astro's server output into Vercel serverless functions. `output: "server"` enables on-demand rendering for any route that does not declare `export const prerender = true`. The Vercel application root is `apps/frontend` — the `design-reference/` directory is outside this root and will not be deployed.

## Design Reference Boundary

Production frontend code (`apps/frontend/src`) must **not** import from `design-reference/`. The Figma Make React/Vite prototype archived there is a read-only design reference. All production UI must be manually reimplemented in Astro + Tailwind CSS.
