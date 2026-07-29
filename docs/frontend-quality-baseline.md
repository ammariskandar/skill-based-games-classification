# Frontend Quality Baseline

Accessibility and performance checks recorded during SBGC-35. This is a snapshot, not a complete audit.

## Accessibility Smoke Checks

| Check | Status |
|-------|--------|
| Semantic landmarks (`<header>`, `<nav>`, `<main>`, `<footer>`) | Present |
| Skip-to-content link | Present, visible on focus |
| Keyboard focus indicators (`focus-visible:`) | Present on interactive elements |
| Form labels (search input has `sr-only` label) | Present |
| Heading hierarchy (one `<h1>` per page) | Present |
| Recovery links on 404 and error pages | Present |
| No horizontal overflow at narrow widths | Verified |
| `prefers-reduced-motion` respected (animations, transitions) | Applied via `motion-reduce:` utilities |
| Colour contrast — `--color-dim` (`#484f58`) on `--color-bg` (`#0d1117`) | **Known failure — SBGC-164** |

This is not a WCAG audit. SBGC-164 tracks the known `--color-dim` contrast failure. Do not close SBGC-164 here.

## Performance Smoke Checks

| Check | Status |
|-------|--------|
| No analytics script when `PUBLIC_GOOGLE_ANALYTICS_ID` is unset | Verified |
| One analytics script when a valid `G-XXXXXXXXXX` ID is configured **and in production mode** | Verified |
| No new client framework or hydration added | Verified |
| No large analytics npm dependency | No dependency added |
| No unnecessary client JavaScript in shell or routes | Verified |
| Build succeeds | `npm run build:frontend` passes |
| Rendering modes unchanged (SSR default, prerendered fixed routes) | Verified |
| No SPA router or client state framework introduced | Verified |

## Automated Checks

| Check | Method |
|-------|--------|
| Analytics omitted without ID | Build inspection — no `googletagmanager` in output when ID is empty |
| Analytics present with valid test ID | Build inspection — exactly one tag when `G-XXXXXXXXXX` is set |
| `vercel.json` parses | `python3 -c "import json; json.load(open('vercel.json'))"` |
| No `PUBLIC_` secret variables | Manual review of Astro `@theme` and env schema |

No browser automation, screenshot tests, or full-page snapshots are used.

## Known Gaps

- No Lighthouse audit has been recorded.
- No automated accessibility scanning is configured.
- No performance budget or regression detection exists.
- CSP analytics whitelist is deferred until analytics is enabled in production.
