# Human-Intervened Decisions

This file records explicit human product/architecture decisions that override or refine agent recommendations. Each entry is a permanent governance record.

---

## SBGC-150 — Option G: Fluid Shell with Controlled Gutters

**Date:** 2026-07-25

**Ticket:** SBGC-150

**Problem observed:** Excessive horizontal whitespace on desktop. The application shell used a global `max-w-6xl` (1152px) centered column, causing content to appear too far inward and text to wrap prematurely. At 1440px viewport, 20% of horizontal space was unused; at 1920px, 40% was unused.

**Root cause:** Uniform `max-w-6xl` on Header inner wrapper, `<main>`, and Footer inner wrapper.

**Options considered:**

| Option | Description |
|--------|-------------|
| A | Increase to `max-w-7xl` (1280px) |
| B | Arbitrary value e.g. `max-w-[90rem]` |
| C | Remove max-width entirely; use viewport padding only |
| D | Separate shell width from prose width (wider shell + narrow prose) |
| E | Responsive breakpoint-specific shell widths |
| G | Fluid shell with centralized responsive gutters (selected) |

**Why Option D was rejected:** It still depended on choosing another arbitrary global maximum (`max-w-7xl`, 90rem, or similar), which risked becoming a future layout constraint for data-heavy pages (catalogue, rankings, tables, grids, charts).

**Why pure Option C raised concern:** Without centralized layout conventions, inconsistent section widths and arbitrary per-page gutter choices could creep in over time.

**Why Option G was selected:**

- Fluid shell — uses available viewport width, no arbitrary ceiling.
- Centralized responsive gutters — one canonical `shell-gutter` utility class ensures Header, Main, and Footer share identical horizontal padding at every breakpoint.
- Separate prose measure — `max-w-2xl` remains available for content that has a readability justification (About, Methodology).
- Named layout modes — future catalogue/ranking/grid/chart pages default to fluid width without inventing new shell rules.
- Consistency is enforced through a shared CSS utility rather than a global width cap.

**Canonical rule:**

> MyGameDNA uses a fluid application shell with centralized responsive gutters. Width constraints apply only to content that has a specific readability or design reason, not to the entire application.

**Implementation consequences:**

- Removed `max-w-6xl` from `BaseLayout.astro`, `Header.astro`, and `Footer.astro`.
- Added `shell-gutter` CSS utility in `global.css` using Tailwind 4 `@utility` with responsive `--gutter` custom property (1rem mobile, 1.5rem tablet, 2rem desktop).
- Prose content (`max-w-2xl`) retained on body paragraphs for readability.
- Header and Footer outer wrappers remain full-width for background/border styling.

**Out of scope:**

- Ultrawide viewport (>1920px) optimization.
- Catalogue grid implementation.
- Game-detail layout.
- Rankings table design.
- Final responsive design system.

**Future review trigger:** Revisit only when real catalogue, ranking, or game-detail layouts show a measured need for additional layout modes or different gutter scales.

---

## SBGC-32 — Bar Chart vs Radar Chart Authority

**Date:** 2026-07-26

**Ticket:** SBGC-32

**Decision:** Both Observable Plot bars and D3 radar charts are implemented as evaluation candidates. No final product default has been selected.

**Authority:** Ammar Iskandar makes the final decision on when to use bars versus radar. Agents may recommend based on context analysis and trade-offs, but no agent recommendation becomes canonical without explicit owner approval.

**Contexts may vary:** Different pages or features may ultimately use different chart forms. Catalogue rows may favour bars for compact precision; game-detail pages may favour radar for shape-based storytelling. Both foundations are ready for either path.

**Non-negotiable rule:** Exact-value text representation (labels, percentages, totals) remains mandatory regardless of chart type. No tooltip-only design is acceptable.
