# Skill Visual System

Canonical visual representation for the MyGameDNA Micro/Mystiko/Macro skill dimensions across Challenge and Reward profiles.

## Terminology and Order

| ID        | Label   | Symbol | Colour Token              |
| --------- | ------- | ------ | ------------------------- |
| `micro`   | Micro   | ◆      | `--color-micro` (blue)    |
| `mystiko` | Mystiko | ◈      | `--color-mystiko`(purple) |
| `macro`   | Macro   | ⬟      | `--color-macro` (orange)  |

Dimensions always appear in this canonical order. Challenge and Reward are separate profiles — each independently totals 100.

Labels, symbols, colours, and order are **shared invariants** across both profiles. Only the explanatory descriptions are profile-dependent (see **Profile-Dependent Semantics** below).

## Non-Colour Identity

Each dimension is identifiable through three channels:

1. **Label** — text name
2. **Symbol** — Unicode glyph for accessible, non-colour identification
3. **Colour** — semantic theme token (`--color-micro`, `--color-mystiko`, `--color-macro`)

**Canonical invariant:** Every dimension's label, legend marker, bar, radar axis/value marker, fallback bar, and summary symbol must use the same canonical colour token and non-colour symbol. `--color-blue`, `--color-purple`, or any generic token must not be used as a dimension identity — only `--color-micro`, `--color-mystiko`, and `--color-macro`. Neutral structural tokens (`--color-chart-grid`, `--color-chart-muted`) are acceptable only for chart framework elements (grid lines, backgrounds, structural labels).

No dimension relies on colour alone. Symbols are always visible in legends and summaries.

## Profile-Dependent Semantics

Descriptions are resolved via `getDimensionDescription(profile, dimension)` (`DIMENSION_DESCRIPTIONS` in `src/lib/skill-dimensions.ts`). `SkillLegend` requires a `profile` prop; components must never hardcode a single Challenge-oriented description.

### Challenge — what the game demands of the player

| Dimension | Meaning                                                                                                |
| --------- | ------------------------------------------------------------------------------------------------------ |
| Micro     | Fine motor execution, reflexes, precision, timing, and mechanical dexterity.                           |
| Mystiko   | Decision-making under uncertainty, hidden information, tactical adaptation, and situational awareness. |
| Macro     | High-level strategy, resource management, long-term planning, and systemic foresight.                  |

### Reward — what yields player satisfaction, fulfillment, mastery payoff, or victory

| Dimension | Meaning                                                                                      |
| --------- | -------------------------------------------------------------------------------------------- |
| Micro     | Kinetic satisfaction, sensory feedback, mechanical mastery, and reflex execution payoff.     |
| Mystiko   | Discovery, tactical outplay, deduction, puzzle resolution, and out-adapting opponents.       |
| Macro     | Strategic triumph, realization of long-term planning, economic dominance, and grand victory. |

## Components

| Component            | Path                                            | Role                                                           |
| -------------------- | ----------------------------------------------- | -------------------------------------------------------------- |
| `SkillLegend`        | `src/components/score/SkillLegend.astro`        | Dimension definitions list (compact + full modes)              |
| `SkillScoreSummary`  | `src/components/score/SkillScoreSummary.astro`  | Universal accessible text profile — always present             |
| `SkillScoreBars`     | `src/components/score/SkillScoreBars.astro`     | Observable Plot horizontal bar chart                           |
| `SkillRadarChart`    | `src/components/score/SkillRadarChart.astro`    | D3 radar/spider chart (three axes)                             |
| `SkillProfilePanel`  | `src/components/score/SkillProfilePanel.astro`  | Composition panel: heading + summary + legend + selected chart |
| `SkillChartFallback` | `src/components/score/SkillChartFallback.astro` | CSS/HTML bars — no JavaScript required                         |

## Data Contract

```typescript
interface SkillProfile {
  type: "challenge" | "reward";
  micro: number; // integer 0-100
  mystiko: number; // integer 0-100
  macro: number; // integer 0-100
  title?: string;
  description?: string;
  source?: string;
}
```

Presentation-level validation (`validateProfile` in `src/lib/skill-dimensions.ts`) enforces:

- All three dimensions present and numeric
- Integer values only
- 0–100 range per dimension
- Total exactly 100
- Valid profile type

Malformed input is never silently rendered. Django will own authoritative server-side validation.

## Chart Technologies

### Observable Plot (`SkillScoreBars`)

- Used for horizontal bar visualisations
- Responsive width, fixed 0–100 domain
- Direct numeric labels on bars (no tooltip-only values)
- Theme tokens via CSS custom properties
- Client-side only — server renders `<noscript>` fallback

### D3 (`SkillRadarChart`)

- Used for radar/spider visualisations
- Three axes (triangle shape with exactly three dimensions)
- Responsive SVG `viewBox`
- Value labels, axis labels, grid levels
- No jQuery, no global mutable state, no external tooltip plugins
- Client-side only — server renders `<noscript>` fallback

## Chart Selection Governance

**The bar-versus-radar product decision belongs to Ammar Iskandar.** Both foundations are implemented for evaluation.

| Trade-off          | Bars                            | Radar                            |
| ------------------ | ------------------------------- | -------------------------------- |
| Precision          | High — exact values labelled    | Lower — angle/area perception    |
| Compactness        | Good for catalogue rows, tables | Larger space requirement         |
| Mobile             | Excellent at narrow widths      | Workable but constrained         |
| Scanning           | Fast numeric comparison         | Slower — shape interpretation    |
| Overlay            | Difficult to overlay profiles   | Possible but cluttered           |
| Shape storytelling | Weak                            | Strong — overall balance visible |
| Accessibility      | Text summary + bar labels       | Text summary + axis labels       |
| 3-dimension shape  | N/A                             | Triangle — fixed geometry        |

### When to prefer bars

- Precision matters
- Users compare exact percentages
- Mobile width is constrained
- Compact repeated displays are needed (catalogue rows, ranking tables)
- Accessibility and scanning speed dominate

### When to prefer radar

- Overall shape is the main communication goal
- Balance is more important than precise comparison
- Only one or a small number of profiles are shown
- Visual storytelling is valuable
- Exact text values remain adjacent

## Accessibility

- Visible profile title, labels, and percentages
- Non-colour identity (symbols) in all legends and summaries
- No tooltip-only data — every value appears in text
- `SkillScoreSummary` always present — screen-reader-complete
- SVG has `role="img"` and `aria-label`
- `<noscript>` fallback for all chart components
- 200% zoom compatible
- Reduced-motion: chart animations are optional and respect `prefers-reduced-motion`

## Progressive Enhancement

- Server renders: profile title, labels, numeric scores, total, `<noscript>` fallback
- Client JavaScript enhances chart containers on `astro:page-load`
- Chart modules load only on routes that use them — no global chart code
- Multiple instances work without selector collisions
- Failure leaves usable text content visible

## Django Boundary

Django owns authoritative score validation and persistence. Astro owns presentation only. The frontend's `validateProfile` is a presentation-level convenience — it does not replace Django's server-side rules.

## Performance

- D3 and Observable Plot are tree-shaken at import — only used APIs are bundled
- Chart JavaScript loads only on routes with chart components
- No chart code in `BaseLayout`
- CSS growth is limited to theme tokens (`--color-micro/mystiko/macro/chart-*`)
