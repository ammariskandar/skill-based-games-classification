# MyGameDNA Assistant Operating Rules

Mandatory operating rules for AI agents working in this repository. These are
binding preflight checks, not suggestions.

## Frontend (Astro) CSS preflight

Before any Astro CSS implementation or correction prompt, an agent MUST:

1. **Classify the affected DOM** as one of:
   - **local** — rendered directly by the current `.astro` component;
   - **child-owned** — rendered by another Astro component;
   - **runtime-created** — built by vanilla JS / `document.createElement` / dynamic insertion;
   - **global** — truly site-wide.
2. **Never assume scoped CSS reaches child-owned or runtime-created DOM.** Astro
   rewrites scoped selectors with generated `data-astro-*` scope attributes, so a
   selector can look correct while its compiled form cannot match the target node.
3. **If apparently-correct CSS does not apply, check Astro scope ownership before
   proposing layout changes.** Inspect the rendered DOM and whether the selector
   expects a generated scope attribute that the node lacks.
4. **Do not recommend wholesale global CSS when a bounded solution exists.**
   Prefer the narrowest safe boundary (scoped `<style>`, or a selective `:global()`
   where genuinely required), never `<style is:global>` as the default.

See `docs/frontend-architecture.md` → "Astro CSS ownership and scoping" for the
full rule and the SBGC-78 autocomplete example.
