# Frontend Styling

## Canonical Approach

**Tailwind CSS 4** is the project's canonical styling system. It runs through the official `@tailwindcss/vite` Vite plugin — there is no legacy `@astrojs/tailwind` integration and no `tailwind.config.*` file.

## Setup

| Item                         | Location                                  |
| ---------------------------- | ----------------------------------------- |
| Vite plugin registration     | `apps/frontend/astro.config.mjs`          |
| Global stylesheet            | `apps/frontend/src/styles/global.css`     |
| Shared document shell        | `apps/frontend/src/layouts/BaseLayout.astro` |

The global stylesheet imports Tailwind via `@import "tailwindcss";` and defines a minimal baseline. `BaseLayout` imports `global.css` and provides the HTML document shell for all pages.

## Conventions

1. **Utility-first** — prefer Tailwind utility classes over custom CSS. Write utilities directly in Astro component markup.
2. **Reusable patterns become components** — if the same set of utilities appears in three or more places, extract an Astro component.
3. **Arbitrary values are exceptional** — use Tailwind's design tokens whenever possible. Square-bracket syntax (`w-[312px]`) requires a comment explaining why a token wasn't enough.
4. **Inline styles require justification** — `style=""` attributes should be rare and documented.
5. **No `@apply` in component styles** — use the `class` attribute in markup instead. `@apply` in `global.css` is acceptable only for the baseline reset.
6. **Responsive first** — every page and component must be readable at narrow (mobile) and wide (desktop) widths. Use Tailwind's responsive prefixes (`sm:`, `md:`, `lg:`).
7. **Accessible by default** — colour contrast, focus indicators, and semantic heading hierarchy are required.

## Micro / Mystiko / Macro Visual Identity

The distinct visual identity for the three skill dimensions (colours, badges, chart conventions) is **deferred to SBGC-32**. Do not add dimension-specific styling before that task.

Current pages use neutral tokens only.

## Application Shell Styling

The global shell (Header, Navigation, Footer, responsive container) uses a restrained dark theme with semantic tokens defined in `@theme`. The colour palette is inspired by the locked design reference but implemented independently:

| Token          | Role                                      |
| -------------- | ----------------------------------------- |
| `--color-bg`   | Page background (`#0d1117`)               |
| `--color-surface` | Header/footer background (`#161b22`)   |
| `--color-border` | Separator lines (`#21262d`)            |
| `--color-text` | Primary body text (`#e6edf3`)             |
| `--color-muted` | Secondary text (`#8b949e`)              |
| `--color-blue` | Links, focus rings, interactive accents   |

Active navigation state uses background contrast (`bg-surface-2`) rather than colour alone.

## Layout Modes

| Mode             | Description                                           | Used by                              |
| ---------------- | ----------------------------------------------------- | ------------------------------------ |
| Fluid shell      | Uses full viewport width with `shell-gutter` padding   | Header, Main, Footer, catalogue, rankings, future grids/charts |
| Prose measure    | `max-w-2xl` (672px) for readability                    | About, Methodology, long-form content |

Width constraints on pages **require a content-specific justification**. Do not introduce a new global shell maximum without an explicit owner decision (see `docs/human-intervened-decisions.md`).

## UI Foundation Components

Reusable Astro components live in `src/components/ui/`. See `docs/ui-foundations.md` for inventory, variant maps, accessibility contracts, and extension policies.

## Responsive Navigation

The header uses two mutually exclusive navigation presentations controlled by CSS breakpoints:

- **Desktop (`lg:` and above):** Single-row flex layout — brand left, horizontal `<Navigation>` right.
- **Compact (below `lg:`):** Three-column CSS grid (`grid-cols-[1fr_auto_1fr]`) so unequal left/right controls do not displace the centred brand. The disclosure panel is absolutely positioned relative to the `<header>` to span the full header width.

The `lg` (64 rem / 1024 px) breakpoint was chosen by content fit rather than device convention. The disclosure panel respects `prefers-reduced-motion` through existing `motion-reduce:` utility conventions.

Foldable progressive enhancement lives in `global.css` under a `@media (horizontal-viewport-segments: 2)` block. It forces the compact shell on hinged displays and is pure CSS — no JavaScript Viewport Segments API is used. Unsupported browsers ignore the media feature and fall back to the viewport-width breakpoint.

## Figma Make Design Reference

The Figma Make export archived at `design-reference/figma-make-dark-ui/` may inform visual implementation. However, Tailwind tokens and Astro components must be defined independently — do not duplicate the generated React structure automatically. Study the reference for layout, spacing, typography, and interaction intent; implement in canonical Astro + Tailwind CSS.
