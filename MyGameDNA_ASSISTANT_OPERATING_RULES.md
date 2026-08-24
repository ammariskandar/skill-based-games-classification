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

## Frontend interaction preflight

Before any frontend interaction implementation or correction prompt, an agent
MUST:

1. **Classify interaction risk F0–F3** (static / deterministic / browser-state
   / motion-timing) before drafting. See `skills.md` §8.8 and
   `.agents/skills/browser-interaction-engineering/SKILL.md`.
2. **Not preselect a complex browser architecture for F3** without comparing at
   least two viable alternatives.
3. **Identify fixed product behavior separately from suggested implementation.**
   Do not let a suggested technique override an accepted visual/interaction
   contract.
4. **Require real-browser ground truth for F2/F3.** Pure/synthetic tests are
   supplementary only.
5. **Explicitly protect existing visual/interaction behaviors** when a
   correction only targets a narrow defect.
6. **After two failed corrections, do not generate another local-patch prompt.**
   Stop for architecture/harness reassessment.
7. **Require harness validation if human observation conflicts with automation**
   (`human FAIL` + `automation PASS` ⇒ suspect the harness first).
8. **Never let “tests pass” substitute for perceptual human PASS** when the
   requirement is visual.
9. **Remember Astro DOM ownership/scoping** when runtime DOM manipulation is
   proposed (cloning, moving, creating, reparenting).
