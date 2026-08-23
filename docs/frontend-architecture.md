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

### Navigation

Navigation destinations are centralized in `src/lib/nav-destinations.ts`. Both the desktop horizontal nav and the compact disclosure panel consume the same five-link source (Home, Catalogue, Rankings, Methodology, About). This prevents drift between two independently maintained link lists.

**Responsive strategy:** The header selects between two mutually exclusive navigation presentations based on available layout space, not device detection:

- **Desktop (≥1024 px / `lg`):** Single-row header with brand on the left and horizontal navigation links on the right. No hamburger trigger.
- **Compact (<1024 px):** Three-column header bar — menu trigger (left), centred "MyGameDNA" brand (centre), Search link (right). Navigation links are disclosed in a panel below the header.

The breakpoint was chosen by content fit: the desktop brand plus five navigation links need roughly 700 px. At the next-lower Tailwind breakpoint (`md` / 768 px) the content area is approximately 720 px, which is too tight. At `lg` (1024 px) the content area is approximately 960 px, giving comfortable room.

**Compact disclosure:** The menu trigger is a `<details>/<summary>` element with progressive JavaScript enhancement:

- **No-JS fallback:** Native `<details>` open/close behaviour. Summary click toggles visibility of the navigation panel.
- **JS enhancement:** Listens to the native `toggle` event to synchronize `aria-expanded`. Adds Escape key handling (closes panel and returns focus to trigger), closes panel when a navigation link is activated, and resets stale open state when the viewport crosses into desktop layout via `matchMedia`. Native click, Enter, and Space activation are not reimplemented — they are handled by the `<details>` element.

**Keyboard behaviour:** Tab reaches the trigger; Enter/Space toggles; Tab reaches disclosed links; Shift+Tab behaves normally; Escape closes and returns focus to the trigger. No focus trap, no arrow-key menu semantics. The disclosure is not a modal.

**Search:** The compact header includes a `/search` link with a magnifying-glass icon and accessible label. This is an ordinary Astro MPA link — no overlay, input, autocomplete, or functional search execution. Global search remains non-functional pending Django search endpoints.

**Foldable progressive enhancement:** When the viewport is split by a physical hinge, the compact navigation is forced regardless of total viewport width so that controls do not span the hinge. Browsers that do not support the media feature fall back to the regular viewport-width breakpoint. Exact hinge-aware placement is deferred because the viewport-segment CSS environment variables are experimental and no real segmented-device verification was available at implementation time. No real segmented-device test has been performed.

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

### Classification Display (SBGC-73)

The public Game-detail classification is rendered by `src/components/classification/`:

- `ClassificationDisplay.astro` — receives the SBGC-71 `classification` DTO and branches unavailable (null/non-ready) vs ready.
- `ClassificationProfile.astro` — the single shared Challenge/Reward profile component (100% stacked bar + exact Micro/Macro/Mystiko values).
- `ClassificationConfidence.astro` — confidence hierarchy: section label, primary percentage, semantic descriptor (`High confidence`).
- `ClassificationStatus.astro` — reusable dot status for provisional/stale.

Rendering is **static/zero-hydration**: no chart library, no `client:*` directive, no client JavaScript. The locked dimension order is `Micro, Macro, Mystiko` (single source in `src/lib/classification-presentation.ts`). Category colours reuse the site tokens `--color-micro`/`--color-macro`/`--color-mystiko`. Exact values are always visible (never colour-only).

State handling: `classification: null` and legitimate non-ready statuses both render an unavailable state with no bars/confidence/zeros; READY renders profiles + confidence + provisional/stale indicators + submission count. Historical SBGC-73 "notes" has **no canonical Final Classification note** — notes are not aggregated or invented.

### Game Detail Layout (SBGC-73)

The desktop Game page is a two-column grid: artwork (left) and a right panel (Game Information control above the always-visible Skill Classification). On mobile the panel stacks below the artwork. Game Information opens a native `<dialog>` (no refetch — it consumes the already-loaded SBGC-71 Game DTO); secondary metadata (developer, release date, source, Steam App ID, description) lives in that modal, while Skill Classification remains permanently visible and is **not** collapsible. The interaction is a tiny vanilla `<script>` (no framework island, no `client:*` directive). The future D3 radar visualization will inherit the classification region without a page-layout redesign.

Human verification (visual + interaction) passed on the local dev servers: desktop two-column architecture, Game Information modal (open/Close/Escape), Manual/sparse metadata, and responsive mobile layout all reviewed and accepted; the modal was centered and the backdrop darkened during review.

### Exceptional States (SBGC-74)

The Game-detail page resolves every plausible upstream response into one honest state without inventing data:

- **Not found** — Django 404 (`GAME_NOT_FOUND`, indistinguishable for unknown/hidden/draft/archived/non-game) → real HTTP 404 via `404.astro`; hidden records are never disclosed.
- **Service failure** — timeout, network, Django 5xx, or malformed response → real HTTP 500 with a friendly `Try again` link to the current URL. No automatic retry/backoff/polling, and never a 200 "error page".
- **Unhandled render error** — Astro's native fallback renders `500.astro` with a real 500.
- **Missing image** — a null/empty `image_url` renders a local CSS placeholder (`GameImage.astro`) preserving the 16:9 container and carrying the Game name as accessible text; no broken image, no Steam/CDN fetch.
- **Sparse metadata** — optional Game Information rows are omitted when empty; no `N/A` or blank rows.
- **No / non-ready classification** — HTTP 200 with the deliberate unavailable state; no fake zeros.
- **Stale classification** — HTTP 200 with persisted scores plus a stale qualifier.
- A failed Steam metadata refresh does **not** invalidate a persisted Game; the page renders persisted data without querying scheduler audit.

The broader generic integration-failure (SBGC-92) and frontend error-state (SBGC-101) work remains separate — SBGC-74 is page-scoped only.

### Dynamic Game-Image Upscaling (SBGC-184)

Steam Games use a **layered Hero + Capsule** presentation; Manual Games keep
a single operator image.  WebSR 2x super-resolution is an optional,
browser-side progressive enhancement over the *foreground* artwork only.

#### Steam presentation

```text
STEAM GAME
  official Library Hero   → wide, softened/dimmed background (never upscaled)
  official Library Capsule → sharp portrait key-art foreground (optionally enhanced)
  header.jpg              → fallback only (foreground-over-Hero, or background when Hero absent)
```

The Library Logo is **intentionally not used**.  The fallback ladder is:

- **Hero + Capsule** → Hero background + Capsule foreground;
- **Hero only** → Hero background + contained `header.jpg` foreground;
- **Capsule only** → `header.jpg` background + Capsule foreground;
- **neither** → existing `header.jpg` full-frame behaviour;
- **no image** → existing placeholder (never upscaled).

The Hero + Capsule foreground is one centered group: the portrait Capsule on the
left and a reserved square **classification-visualization slot** on the right
(`data-classification-visualization`).  The slot shares the Capsule's flex-group
height and is `1 / 1` (so it is wider than the portrait Capsule).  It is empty
and `hidden` in production until SBGC-12 renders the combined radar chart;
`GameImage.astro` is already structured so adding that content requires no
layout restructuring.

Steam's canonical `header.jpg`/`image_url` semantics (SBGC-75 SEO/OG/Twitter
and `VideoGame.image`) are unchanged; the Library assets are additive fields
(`library_hero_url`, `library_capsule_url`) resolved by Django and exposed via
the public DTO.

### Source-agnostic artwork composition (SBGC-190)

The Hero/Capsule/Image composition is **source-agnostic**.  Django resolves
effective `image_url` / `library_hero_url` / `library_capsule_url` (manual
override first, Steam fallback), and the frontend renders whatever it receives
— no `manual ?? steam` branches in Astro.  Manual Games may now supply the same
three roles (`manual_image_url` / `manual_hero_url` / `manual_capsule_url`) and
receive the identical softened-Hero / foreground-Capsule treatment.  The
WebSR enhancer is also source-agnostic: it keys off the asset role and the
effective source URL, so a manual Capsule receives the same density/2x/cache
handling as a Steam Capsule.  `crossorigin="anonymous"` is applied only for
known Steam CDN hosts so arbitrary manual origins still display (enhancement is
skipped if pixel-read is blocked).

#### Enhancement policy

- **Original-first SSR** — the ordinary `<img>` always renders first; the page
  never waits for WebGPU/WebSR/weights before showing artwork.
- **Capsule density rule** — a Capsule is enhanced only when its effective
  physical density is insufficient: `required = renderedCssSize ×
  devicePixelRatio`, `target = required × 1.25` (`QUALITY_HEADROOM`).  A source
  meeting the target is skipped; a deficient source is a WebSR candidate.  The
  1.25 is *display-density headroom*, not a native 1.25x neural model — WebSR
  remains a 2x model internally.
- **Header/Manual width rule** — the header fallback and Manual primary image
  use the original `ELIGIBILITY_WIDTH_THRESHOLD` (800px) width-only rule.
- **Hero is never upscaled** — it is a high-resolution background whose slight
  softening already de-emphasizes source imperfections.
- **2x only** — output is exactly `2 × source width` and `2 × source height`,
  preserving aspect ratio (never iterative, never resized to a fixed target;
  the UI never auto-doubles the rendered CSS size).
- **Cache-before-inference** — a valid IndexedDB hit bypasses WebSR entirely.
- **IndexedDB cache** — binary Blob storage (never localStorage/base64), a
  content- and model-addressed key, and a hard 10-entry LRU policy.
- **Cache identity/invalidation** — the key includes the Game slug, the asset
  role (`library-capsule`, `header`, `manual-primary`), the source URL, and the
  model version, so artwork, role, or model changes produce a miss.
- **Worker strategy** — a classic Web Worker (import-free) runs WebSR against an
  `OffscreenCanvas`; the main thread only orchestrates and reveals the result.
- **CORS** — Steam's image CDN sends `Access-Control-Allow-Origin: *`, so the
  enhanceable Steam foreground uses `crossorigin="anonymous"` to permit pixel
  reads; the decorative Hero carries no `crossorigin`; Manual images omit it
  (they render regardless, and enhancement is skipped if pixel-read is blocked).
- **Transition** — the portrait Capsule crossfades (~200ms); the header and
  Manual full-frame images keep the top-to-bottom wipe.
- **Failure semantics** — every enhancement-only failure (no WebGPU, worker
  error, cross-origin pixel-read, cache/encoding failure) degrades silently to
  the original image.  No user-facing error UI.
- **Reduced motion** — `prefers-reduced-motion: reduce` swaps the enhanced
  image in instantly (no animation).

WebSR is `@websr/websr@0.0.16` using the `anime4k/cnn-2x-s` network with the
`cnn-2x-s-3d` weights (the 3D/gaming-trained variant). Custom Game-art model
training is **not** part of this ticket — see the future
"Train MyGameDNA Game-Art Super-Resolution Model" ticket recorded in
`context.md`.

### Homepage (SBGC-189)

The homepage (`/`) is **SSR/on-demand** (`export const prerender = false`) — it
depends on live persisted Game data, so the random carousel selection happens per
request rather than at build time. `index.astro` fetches two independent things
server-side in parallel and degrades each gracefully:

- **Random Steam carousel** — `GET /api/v1/games/homepage` (see
  `docs/backend-api.md`) returns up to 10 randomly selected publicly-listable
  Steam base Games that have a Library Capsule. Django owns eligibility and
  selection; Astro never downloads the whole catalogue.
- **Hades showcase** — `getGameDetail("hades")` fetches the real public Hades
  Game through the existing SBGC-71 detail boundary, reusing its persisted
  Library Hero/Capsule.

The carousel is full-bleed (it breaks out of `shell-gutter`), uses CSS
`scroll-snap` plus a small vanilla TypeScript controller (Previous/Next buttons,
no autoplay, no framework), shows 5 capsules on desktop and fewer on smaller
screens, and respects `prefers-reduced-motion`. Each card links Capsule and title
to `/games/{slug}`.

The Hades showcase reuses `GameImage.astro` (the SBGC-184 Hero + Capsule +
classification-visualization-slot composition) as the left column of a
two-column product-explanation section. No Game Information dialog or
classification bars are rendered in the sample. `GameImage.astro` is the
reusable artwork component shared by the Game-detail page and the homepage
showcase; it is not duplicated.

Failure behaviour: a carousel API failure renders a restrained "unavailable"
state (hero and Hades copy still render); a Hades failure omits the sample
artwork while keeping the explanatory copy. Neither failure turns the homepage
into a 500.

### Game Catalogue (SBGC-77)

The catalogue (`/catalogue`) is **SSR/on-demand** (`export const prerender = false`) — it
depends on live persisted Game data, so each request reads the current page from
Django rather than building statically.  `catalogue.astro` fetches one page of
the SBGC-76 catalogue DTO server-side via `getGameCatalogue({ page })` (page size
left to Django's 24 default) and renders the result as plain HTML — no client
router, no client-side fetch, no React/Vue/Svelte.

- **Card** — `GameCatalogueCard.astro` renders one item as a single full-card
  `<a href="/games/{slug}">` (no nested links, no JS click handler): effective
  artwork (Capsule first, general image fallback, then a local SVG placeholder),
  the title, a compact Steam/Manual source label, and a compact Challenge/Reward
  summary or "Not yet classified".  Artwork is an ordinary `<img>` — the SBGC-184
  WebSR enhancer is **not** mounted here, so up to 24 cards stay cheap.
  All cards share an identical outer width and height: the title reserves two
  lines (`min-height`) and the classification area reserves the fully-populated
  height so unclassified/no-cover cards do not collapse the grid.
- **Dense presentation** — catalogue cards are much smaller than the homepage
  carousel, then enlarged ~15% from that corrected size.  The grid uses
  `repeat(auto-fill, minmax(7rem, 1fr))` so many titles fit per row on wide
  screens while still collapsing to a usable multi-column grid on mobile.  The
  homepage carousel sizing is untouched.  Hover/keyboard focus enlarges the
  whole card by ~1.15× via `transform: scale(1.15)` (no reflow); reduced-motion
  users get no enlargement.
- **Compact classification** — `CatalogueProfileSummary.astro` renders each
  profile as a small segmented bar plus an accessible label; exact
  "Micro X · Macro Y · Mystiko Z" values move to a visually-hidden text node
  (`sr-only`) rather than six visible rows.  The locked Micro/Macro/Mystiko
  order and `--color-micro`/`--color-macro`/`--color-mystiko` tokens are
  unchanged; colours are never the sole semantic carrier.  `classification:
  null` (or missing scores) renders "Not yet classified", never a fake 0/0/0.
- **Pagination** — `CataloguePagination.astro` emits ordinary anchor links
  (`/catalogue?page=N`; page 1 is the bare route).  Previous/Next are omitted or
  `aria-disabled` at the bounds; a page beyond the last renders a truthful empty
  state with a "Back to first page" link (never a fabricated page).
- **States** — a Django/service failure renders a real HTTP 500 error state
  (never "0 games"); an empty catalogue renders a distinct empty state.
- **No client loading state** — the initial render is SSR, so the browser's
  normal navigation is the loading state; there is no spinner/skeleton/hydration.
- **Canonical URL** — the shared `BaseLayout` canonical helper accepts only a
  pathname (it strips query strings), so every pagination page canonicalizes to
  the base `/catalogue` URL.  This is an accepted SBGC-77 limitation; a
  query-aware canonical helper is deferred.

### Cover state and broken-cover ordering (SBGC-77 correction)

Each card has a source-agnostic `data-cover-state` of `unknown` / `has-cover` /
`no-cover`.  A card with no effective Capsule URL is `no-cover` immediately (no
remote request is attempted); otherwise it starts `unknown` and the browser's
native `<img>` `load`/`error` events are the **only** remote-health signal — no
`fetch`, no `HEAD`, no `new Image()` probe, so there is no duplicate image
request.  Cached images are settled via `img.complete`/`img.naturalWidth`.

Confirmed `no-cover` cards are stably partitioned to the end of the **current
rendered page** (working/unknown first, coverless last, each group preserving
original API order) using a `requestAnimationFrame`-batched reorder.  This is a
runtime enhancement only: it does **not** implement global cross-page
"show games without a cover last" sorting, which belongs to SBGC-79 and must
run before pagination in the backend.  A failed Capsule swaps to the local
placeholder (no broken-image icon); the card is still treated as coverless for
sorting even when a general-image fallback is shown.  A broken **general image**
(no Capsule) also swaps to the placeholder via the same native `load`/`error`
handling, so a Manual Game with a dead image URL never shows a broken-image
icon.

### Header Search (SBGC-78)

A **persistent Search control** lives in the Header.  On desktop the Search
button sits immediately next to the `About` link (after the nav tabs); clicking
it moves the icon left and expands a search input that **replaces the nav-tab
region** (the nav tabs are hidden from layout, tab order, and the accessibility
tree), while `About` stays at the far right and the Header height is unchanged.
On compact/mobile the same Search control expands within the compact bar (the
menu trigger and brand collapse).  CSS transitions animate the expansion;
`prefers-reduced-motion` disables it.  Escape or the explicit close button
restores the nav.

The form is a progressive-enhancement `GET /catalogue` form (`name="q"`); plain
Enter always navigates to `/catalogue?q=...` even with JavaScript disabled, and
never waits on autocomplete.

- **Autocomplete** — a local, source-agnostic matcher (`src/lib/game-search.ts`)
  ranks prefix matches before substring matches (max 6) against the complete
  public Game set, never the current catalogue page.
- **Search index** — Django `GET /api/v1/games/search-index` returns the complete
  compact index (`slug`, `name`, effective `capsule_url`, effective `image_url`);
  the browser fetches it through a same-origin Astro proxy (`/api/search-index`)
  so it never talks to Django directly.  The shared loader
  (`src/lib/game-search-index.ts`) adds a memory cache, a versioned
  `sessionStorage` cache (15-minute TTL), and a single in-flight Promise so
  background preload and explicit open never produce a duplicate request.
- **Selective preload** — discovery routes (Home and Catalogue) opt in via
  `BaseLayout`'s `preloadGameSearchIndex` and schedule a low-priority
  `requestIdleCallback` preload after render; ordinary routes (Game detail,
  Methodology, About) stay lazy and load on Search open.  Future `/rankings`
  should enable the same flag.
- **No per-keystroke network** — once the index is loading/loaded, typing performs
  zero backend requests; only the current (≤6) suggestion rows render `<img>`s, so
  there is no image-download storm.  Index failure keeps the input usable (Enter
  still submits) and shows a restrained "Suggestions unavailable".

SBGC-79 (source/classification filters + sort controls) remains intentionally
absent — no filter/sort controls and no disabled placeholders.

### SEO Metadata

`BaseLayout.astro` owns default `<title>`, `<meta name="description">`, Open Graph, Twitter card, canonical URL, and `<meta name="robots">`. Each page overrides title and description via props. Canonical URL is constructed from `PUBLIC_SITE_URL` with a safe local fallback.

## Routing

Routing is **file-based** under `src/pages/`:

```
src/pages/
├── index.astro          →  /              (SSR/on-demand — random Steam carousel + Hades showcase)
├── about.astro          →  /about         (prerendered)
├── methodology.astro    →  /methodology   (prerendered)
├── login.astro          →  /login         (prerendered — future account placeholder)
├── error.astro          →  /error         (prerendered — generic fallback)
├── catalogue.astro      →  /catalogue     (SSR/on-demand)
├── rankings.astro       →  /rankings      (SSR/on-demand)
├── search.astro         →  /search        (SSR/on-demand — reads ?q= param)
├── profile.astro        →  /profile       (SSR/on-demand — future auth required)
├── 404.astro            →  custom not-found (SSR — Vercel serverless)
├── 500.astro            →  custom server-error (SSR — Vercel serverless)
└── games/
    └── [slug].astro     →  /games/:slug   (SSR/on-demand — dynamic route)
```

Future dynamic routes **must not be prerendered** unless an explicit product decision changes that. Data-driven pages require live API data and must render on-demand.

### Dynamic-route rules

- `/games/[slug]` is an **on-demand** route that reads `Astro.params.slug`, fetches the SBGC-71 public game-detail DTO server-side via `getGameDetail()`, and renders the normalized Game + persisted classification. No `getStaticPaths`. A Django `404 GAME_NOT_FOUND` rewrites to the custom `404.astro` (real 404); every other failure (timeout, network, Django 5xx, malformed response) renders a friendly service-failure state with a real 500 (never a 404, never a 200 "error page"). Unhandled render errors fall through to the native `500.astro`. `classification: null` and non-ready statuses render the ordinary page at 200 (no fake scores).
- `/search` reads `?q=` from `Astro.url.searchParams`. A semantic GET form updates the URL. No backend search is executed.
- `/profile` is SSR and will require authentication in a future phase.
- `/login` is prerendered as an informational placeholder — no credential form, no auth package.
- `/error` is a prerendered visual fallback / demo route only — it is **not** the framework error handler.
- `404.astro` is the custom not-found route (real 404 status), handled by the Vercel serverless runtime.
- `500.astro` is the custom server-error page used by Astro's native error fallback for unhandled render errors (real 500 status). The `/games/[slug]` route renders its own service-failure state (real 500) for backend/service failures before any exception reaches the framework fallback.
- Route skeletons contain honest placeholder content — no fake records, counts, rankings, or operational claims.

## Client-Side JavaScript

Client-side JavaScript is limited to **bounded Astro islands**. Components that need interactivity opt in via client directives (`client:load`, `client:idle`, etc.). No SPA framework (React, Vue, Svelte) is required or planned unless a specific Jira task introduces one.

## Architecture Boundary

- **Django** owns authoritative data, business logic, classification rules, search indexing, and the admin interface.
- **Astro** owns routing, page rendering, presentation, asset delivery, server-side API consumption, and SEO metadata.
- The frontend never holds business logic; it consumes the Django API and renders the result.

## Frontend Engineering Defaults

Standing MyGameDNA frontend rules (SBGC-73 onwards):

- **DRY** — extract genuinely repeated UI. Challenge and Reward share one profile component.
- **KISS** — prefer Astro components + TypeScript + semantic HTML + scoped CSS. No framework library for static content.
- **Performance-first** — server-render/static HTML first; zero unnecessary client JavaScript; optimize assets through Astro; hydrate only interactive islands.
- **Islands** — `.astro` components render without a client runtime by default. Hydrate only with a concrete interactive reason (`client:load` for immediate, `client:idle`/`client:visible` for lower priority). Never hydrate merely because it is available.
- **Scoped styling** — component-local `<style>` blocks; reuse design tokens; no CSS-in-JS.
- **Assets** — prefer `astro:assets` `Image`/`Picture` where remote domains can be safely authorized; otherwise a plain `<img>` is acceptable. Do not build manual image optimization.
- **Structure** — `src/pages` (routes), `src/layouts` (shells), `src/components` (reusable UI), `src/lib` (non-UI helpers/API/types).
- **TypeScript** — strict; no `any`/`as any`/`@ts-ignore` unless objectively unavoidable and documented.
- **Slots** — named/default slots for genuinely flexible wrappers only; prefer typed props otherwise.
- **Environment safety** — server-only env vars stay server-only; never leak backend/env settings into client JS; do not add env vars unless required.

## API Layer

Astro server routes consume Django through a shared server-side API client at `src/lib/server/api/`. The API layer owns base URL (`DJANGO_API_URL`), timeout (8s default), transport, and normalized error handling (`ApiResult<T>` with discriminated ok/failure). Ordinary browser code does not call Django directly by default. SBGC-72 added the game-detail boundary (`getGameDetail`, typed DTOs, `GameNotFoundError`/`BackendApiError`). See [`docs/frontend-api-layer.md`](frontend-api-layer.md).

## Vercel Adapter

The `@astrojs/vercel` adapter translates Astro's server output into Vercel serverless functions. `output: "server"` enables on-demand rendering for any route that does not declare `export const prerender = true`. The Vercel application root is `apps/frontend` — the `design-reference/` directory is outside this root and will not be deployed.

## Design Reference Boundary

Production frontend code (`apps/frontend/src`) must **not** import from `design-reference/`. The Figma Make React/Vite prototype archived there is a read-only design reference. All production UI must be manually reimplemented in Astro + Tailwind CSS.
