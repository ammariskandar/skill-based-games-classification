# Skill Visual System

Canonical visual representation for the MyGameDNA Micro/Mystiko/Macro skill dimensions across Challenge and Reward profiles.

## Terminology and Order

| ID       | Label   | Symbol | Colour Token    | Description |
| -------- | ------- | ------ | --------------- | ----------- |
| `micro`  | Micro   | ◆      | `--color-micro`  (blue)  | Execution, mechanics, timing, precision |
| `mystiko`| Mystiko | ◈      | `--color-mystiko`(purple) | Hidden information, probability, mind games, prediction |
| `macro`  | Macro   | ⬟      | `--color-macro`  (orange)| Systems, resource management, planning, strategy |

Dimensions always appear in this canonical order. Challenge and Reward are separate profiles — each independently totals 100.

## Non-Colour Identity

Every dimension is identifiable through three channels:
1. **Label** — text name
2. **Symbol** — Unicode glyph for accessible, non-colour identification
3. **Colour** — semantic theme token (`--color-micro`, `--color-mystiko`, `--color-macro`)

No dimension relies on colour alone. Symbols are always visible in legends and summaries.

## Components

| Component            | Path | Role |
| -------------------- | ---- | ---- |
| `SkillLegend`        | `src/components/score/SkillLegend.astro` | Dimension definitions list (compact + full modes) |
| `SkillScoreSummary`  | `src/components/score/SkillScoreSummary.astro` | Universal accessible text profile — always present |
| `SkillScoreBars`     | `src/components/score/SkillScoreBars.astro` | Observable Plot horizontal bar chart |
| `SkillRadarChart`    | `src/components/score/SkillRadarChart.astro` | D3 radar/spider chart (three axes) |
| `SkillProfilePanel`  | `src/components/score/SkillProfilePanel.astro` | Composition panel: heading + summary + legend + selected chart |
| `SkillChartFallback` | `src/components/score/SkillChartFallback.astro` | CSS/HTML bars — no JavaScript required |

## Data Contract

```typescript
interface SkillProfile {
  type: "challenge" | "reward";
  micro: number;    // integer 0-100
  mystiko: number;  // integer 0-100
  macro: number;    // integer 0-100
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

| Trade-off | Bars | Radar |
|-----------|------|-------|
| Precision | High — exact values labelled | Lower — angle/area perception |
| Compactness | Good for catalogue rows, tables | Larger space requirement |
| Mobile | Excellent at narrow widths | Workable but constrained |
| Scanning | Fast numeric comparison | Slower — shape interpretation |
| Overlay | Difficult to overlay profiles | Possible but cluttered |
| Shape storytelling | Weak | Strong — overall balance visible |
| Accessibility | Text summary + bar labels | Text summary + axis labels |
| 3-dimension shape | N/A | Triangle — fixed geometry |

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
