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

## Figma Make Design Reference

The Figma Make export archived at `design-reference/figma-make-dark-ui/` may inform visual implementation. However, Tailwind tokens and Astro components must be defined independently — do not duplicate the generated React structure automatically. Study the reference for layout, spacing, typography, and interaction intent; implement in canonical Astro + Tailwind CSS.
