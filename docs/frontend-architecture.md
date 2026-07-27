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

The application shell is **fluid** — it uses available viewport width with centralized responsive gutters. A single `shell-gutter` CSS utility class (defined in `global.css`) ensures Header, `<main>`, and Footer share identical horizontal padding at every breakpoint: 1rem mobile, 1.5rem tablet, 2rem desktop.

There is **no global `max-width`** on the shell. Width constraints apply only to content that has a specific readability or design reason:

- **Fluid shell** — default for application pages, catalogue, rankings, future grids, tables, game-detail layouts, charts, and filters.
- **Prose measure** — `max-w-2xl` (672px) for long-form reading content (About, Methodology). This is a content-specific choice, not a shell rule.

Pages must not invent arbitrary `max-w-*`, padding, or margin conventions without a content-specific justification. See `docs/human-intervened-decisions.md` for the SBGC-150 Option G decision record.

### Active-Link Strategy

`Navigation.astro` reads `Astro.url.pathname` and applies `aria-current="page"` plus a highlighted visual state (`bg-surface-2 text-text`) when the current route matches a link. Active state uses background contrast, not colour alone.

### UI Foundations

Reusable Astro components are in `src/components/ui/`. See [`docs/ui-foundations.md`](ui-foundations.md) for the component inventory, supported variants, and design conventions.

### Skill Visual System

Micro/Mystiko/Macro visualisation uses Observable Plot (bars) and D3 (radar). Canonical dimension order, labels, symbols, and colour tokens are defined in `src/lib/skill-dimensions.ts`. See [`docs/skill-visual-system.md`](skill-visual-system.md). Django owns authoritative scores; Astro owns presentation only. The bar-versus-radar product decision belongs to Ammar Iskandar.

### SEO Metadata

`BaseLayout.astro` owns default `<title>`, `<meta name="description">`, Open Graph, Twitter card, canonical URL, and `<meta name="robots">`. Each page overrides title and description via props. Canonical URL is constructed from `PUBLIC_SITE_URL` with a safe local fallback.

## Routing

Routing is **file-based** under `src/pages/`:

```
src/pages/
├── index.astro          →  /              (prerendered)
├── about.astro          →  /about         (prerendered)
├── methodology.astro    →  /methodology   (prerendered)
├── login.astro          →  /login         (prerendered — future account placeholder)
├── error.astro          →  /error         (prerendered — generic fallback)
├── catalogue.astro      →  /catalogue     (SSR/on-demand)
├── rankings.astro       →  /rankings      (SSR/on-demand)
├── search.astro         →  /search        (SSR/on-demand — reads ?q= param)
├── profile.astro        →  /profile       (SSR/on-demand — future auth required)
├── 404.astro            →  custom not-found (SSR — Vercel serverless)
└── games/
    └── [slug].astro     →  /games/:slug   (SSR/on-demand — dynamic route)
```

Future dynamic routes **must not be prerendered** unless an explicit product decision changes that. Data-driven pages require live API data and must render on-demand.

### Dynamic-route rules

- `/games/[slug]` uses `Astro.params.slug` as display text only — no backend query, no `getStaticPaths`. Django will supply all game data later.
- `/search` reads `?q=` from `Astro.url.searchParams`. A semantic GET form updates the URL. No backend search is executed.
- `/profile` is SSR and will require authentication in a future phase.
- `/login` is prerendered as an informational placeholder — no credential form, no auth package.
- `/error` is a prerendered visual fallback / demo route only. It does not automatically catch Astro SSR exceptions, does not handle Django/API failures, and does not implement HTTP 500 behaviour. Actual framework-level exception handling, API failure states, and production-safe error handling remain pending future integration/security work.
- Custom 404 uses `404.astro` and is the actual custom not-found route, handled by the Vercel serverless runtime.
- Route skeletons contain honest placeholder content — no fake records, counts, rankings, or operational claims.

## Client-Side JavaScript

Client-side JavaScript is limited to **bounded Astro islands**. Components that need interactivity opt in via client directives (`client:load`, `client:idle`, etc.). No SPA framework (React, Vue, Svelte) is required or planned unless a specific Jira task introduces one.

## Architecture Boundary

- **Django** owns authoritative data, business logic, classification rules, search indexing, and the admin interface.
- **Astro** owns routing, page rendering, presentation, asset delivery, server-side API consumption, and SEO metadata.
- The frontend never holds business logic; it consumes the Django API and renders the result.

## API Layer

Astro server routes consume Django through a shared server-side API client at `src/lib/server/api/`. The API layer owns base URL (`DJANGO_API_URL`), timeout (8s default), transport, and normalized error handling (`ApiResult<T>` with discriminated ok/failure). Ordinary browser code does not call Django directly by default. Domain endpoints and response types remain separate future work. See [`docs/frontend-api-layer.md`](frontend-api-layer.md).

## Vercel Adapter

The `@astrojs/vercel` adapter translates Astro's server output into Vercel serverless functions. `output: "server"` enables on-demand rendering for any route that does not declare `export const prerender = true`. The Vercel application root is `apps/frontend` — the `design-reference/` directory is outside this root and will not be deployed.

## Design Reference Boundary

Production frontend code (`apps/frontend/src`) must **not** import from `design-reference/`. The Figma Make React/Vite prototype archived there is a read-only design reference. All production UI must be manually reimplemented in Astro + Tailwind CSS.
