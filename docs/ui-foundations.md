# UI Foundations

Reusable Astro components for the MyGameDNA design system. All components use Tailwind CSS 4 utilities generated from `@theme` tokens, render to semantic HTML with zero client JavaScript by default, and are compatible with Django-owned validation and business logic.

## Component Inventory

| Component       | Path                                    | Purpose                                        |
| --------------- | --------------------------------------- | ---------------------------------------------- |
| `Button`        | `src/components/ui/Button.astro`        | Primary, secondary, ghost, danger actions       |
| `FormField`     | `src/components/ui/FormField.astro`     | Label, help text, error message wrapper        |
| `TextInput`     | `src/components/ui/TextInput.astro`     | Single-line text/email/password/search input    |
| `SelectInput`   | `src/components/ui/SelectInput.astro`   | Native `<select>` dropdown                     |
| `TextArea`      | `src/components/ui/TextArea.astro`      | Multi-line text input                          |
| `Card`          | `src/components/ui/Card.astro`          | Bordered content container for grids           |
| `Badge`         | `src/components/ui/Badge.astro`         | Inline status/label indicator                  |
| `DataTable`     | `src/components/ui/DataTable.astro`     | Semantic `<table>` with overflow wrapper       |
| `ItemList`      | `src/components/ui/ItemList.astro`      | Semantic `<ul>` / `<ol>` with spacing          |
| `EmptyState`    | `src/components/ui/EmptyState.astro`    | Title, description, optional action            |
| `LoadingState`  | `src/components/ui/LoadingState.astro`  | `role="status"`, `aria-live`, reduced-motion    |
| `ErrorState`    | `src/components/ui/ErrorState.astro`    | Error title, message, optional action          |

## Conventions

### Astro Component Rules

- Typed `Props` interfaces in frontmatter.
- Semantic native HTML elements (`<button>`, `<input>`, `<table>`, `<ul>`, `<ol>`).
- Zero client JavaScript by default.
- No business logic — components are pure presentation.
- No `className` — Astro uses `class`.
- No polymorphic "as" prop API.

### Tailwind CSS 4 Token Policy

- Design tokens are defined in `@theme` inside `global.css`.
- Add tokens only when they are genuinely reused across multiple components.
- Use `bg-blue`, `text-muted` etc. generated from theme tokens — not raw hex values.
- `--color-*` tokens cover: background, surface levels, borders, text, status colours, accent.
- `--radius-sm` and `--radius-md` for shared border-radius values.

### Decision Order

When styling, follow this priority:

1. **Tailwind utility classes** — for local layout and styling.
2. **Astro component** — when semantic markup repeats across pages.
3. **Typed variant map** — for intentional component variants (e.g. `Button.variant`).
4. **`@utility` or custom CSS** — only when a stable class pattern repeats across multiple components and another component won't help.

### `@apply` Policy

`@apply` is allowed but restrained. Use it only when:

- The pattern is genuinely repeated across multiple files.
- The style represents a stable semantic primitive.
- Keeping it in templates materially harms readability.
- The result remains easy to trace.

Do not create a global `.btn-*` or `.card-*` CSS framework. The Astro component is the canonical reuse unit.

### Class-Name Rules

- Every class string must be a complete, statically detectable literal.
- Never construct class fragments (`bg-${color}-500`).
- Use typed variant maps (`Record<string, string>`) containing full class strings.
- If the same arbitrary value repeats, promote it to an `@theme` token.
- Tailwind 4 automatic source detection remains canonical — no manual `@source` or safelist config.

## Variants

### Button

| Variant    | Description                          |
| ---------- | ------------------------------------ |
| `primary`  | Default. Blue solid, white text.     |
| `secondary`| Bordered surface background.         |
| `ghost`    | Transparent, muted text, hover fill. |
| `danger`   | Red solid, white text.               |

Supports `disabled`, `loading` (aria-busy with visible text), `fullWidth`.

### Badge

| Variant    | Background        | Border       |
| ---------- | ----------------- | ------------ |
| `neutral`  | `surface-2`       | `border`     |
| `positive` | `green/15`        | `green/30`   |
| `warning`  | `yellow/15`       | `yellow/30`  |
| `negative` | `red/15`          | `red/30`     |
| `info`     | `blue/15`         | `blue/30`    |

Colour is never the sole status signal — badges also convey meaning through text labels.

## Accessibility

- Buttons: visible `focus-visible` outline, `disabled` native attribute, `aria-busy` when loading, reduced-motion-safe transitions.
- Forms: programmatically associated labels, `aria-invalid` on invalid controls, `aria-describedby` linked to help/error text, errors are text (not colour-only).
- Tables: `scope="col"` on header cells, `caption` for context, contained horizontal scroll on overflow.
- Loading: `role="status"`, `aria-live="polite"`, decorative skeleton hidden from AT, reduced-motion-safe animation.
- Errors: `role="alert"` only when immediate announcement is needed, no raw stack traces.
- Lists: semantic `<ul>` / `<ol>` elements.

## Django Compatibility

- Controls use native HTML attributes (`name`, `value`, `required`, `disabled`).
- No client-only validation — Django remains authoritative.
- Form components render standard HTML compatible with Django form submission.
- Error messages accept plain text suitable for server-rendered Django errors.

## Extension Policy

- SBGC-32 owns the Micro/Mystiko/Macro visual identity — do not add skill-specific colours here.
- No Storybook or third-party component library at the current project scale.
- Speculative variants (icon-only buttons, size variants, stretched-link cards) must not be added without an approved Jira task.
- New components should follow the same conventions documented here.

## Responsive and Direction-Safe Guidance

- Mobile-first responsive utilities (`sm:`, `md:`, `lg:`).
- Prefer logical properties (`padding-inline`, `text-align: start`) in `@utility` rules.
- Components that use `left`/`right` in layout should be reviewed for future RTL compatibility.
