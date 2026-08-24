# SBGC-191 Postmortem — Infinite Homepage Carousel

- **Status:** closed / merged
- **Related governance:** SBGC-192 (browser-interaction engineering hardening)
- **Scope:** engineering incident record, not a product decision

## 1. Incident

### Intended feature

Extend the SBGC-189 homepage carousel from a finite, arrow-bounded strip into a
circular carousel: forward `…9 → 10 → 1 → 2…` and backward `…2 → 1 → 10 → 9…`,
with both arrows continuously usable and no visible rewind across the track.

### Approximate cost

- ~8 correction runs.
- ~6–8 hours of agent time.
- ~$30 of agent/token usage.

For comparison, prior backend tickets in the same codebase shipped much faster
at far lower cost. The disproportionate cost was not the feature's size; it was
the validation loop.

## 2. Concrete bugs

Three distinct defects surfaced, in sequence.

### 2.1 Fractional-boundary mismatch

The carousel's card pitch is `calc((100% - 4rem) / 5)`, a fractional value
(~259.19px at the desktop tier). The loop normalization compared the
browser-reported `scrollLeft` (whole pixels on a DPR-1 device) against a
fractional canonical-region boundary:

```ts
const canonicalStart = buffer * step;      // 1555.125
if (scrollLeft < canonicalStart) …          // 1555 < 1555.125 → true → false wrap
```

The initial canonical position was therefore misclassified as already inside the
tail-clone region and snapped to the far end of the track, which made the arrows
appear dead. The browser's `scrollLeft` is documented as subpixel-precise but is
only fractional on a subpixel-precise device; on DPR-1 it rounds to integers.
The code assumed exact idealized arithmetic.

**Resolution:** a one-pixel tolerance in the normalization helper, with a
documented semantic reason.

### 2.2 Structural normalization during active smooth scrolling

The loop normalization ran from the high-frequency `scroll` path. During a
smooth `scrollBy({ behavior: "smooth" })`, the browser owns an active
asynchronous scroll animation and fires `scroll` events continuously. The first
such event caused a direct `scrollLeft` write, which aborted the in-flight smooth
animation.

This was directionally asymmetric:

- **Forward** had a 10-card canonical runway, so the wrap only triggered at the
  far end (after the animation completed).
- **Backward** had zero runway (the canonical region *starts* at Game 1), so the
  wrap triggered on the first pixel of motion and every "Previous" click from
  Game 1 was pre-empted — the carousel appeared stuck at the left boundary.

`scroll-snap-type: x mandatory` compounded this: snap is applied *after*
scripted scroll operations and re-snaps the offset, so the browser's snap state
and the script's normalization were competing for the same coordinate.

**Resolution:** move normalization off the `scroll` path and run it only after
the scroll settles (a debounced `scrollend`-equivalent), so it can no longer
abort an in-flight smooth animation.

### 2.3 Emphasis flicker

Because normalization ran every scroll frame (and did an extra forced layout to
recompute the step), the positional brightness update lagged and flashed. This
was a symptom of 2.2, not an independent defect; it resolved when normalization
was separated from the per-frame `scroll` work.

## 3. Validation failure

The dominant failure was the testing harness, not the production code.

The agent validated with headless Chromium plus `--virtual-time-budget`.
Virtual time replaces real-time with a synthetic time source and may fast-forward
past delayed tasks. Under it, `scrollBy({ behavior: "smooth" })` did not advance
`scrollLeft` at all — even with `scroll-snap-type: none`. The harness therefore
never executed the actual smooth-scroll path the bug depended on, while still
producing reassuring "pass" results for an instant-scroll path the user never
took.

Only after switching to real Chromium with real timers was the defect reproduced
and the fix validated. The diagnosis time collapsed once the harness faithfully
executed the real runtime mechanism.

## 4. Process failure

- No harness-qualification gate: results were trusted without proving the
  harness exercised the mechanism under test.
- No correction stop-loss: the agent kept making local patches (epsilon,
  thresholds, clone arithmetic, event timing) without reassessing the
  architecture or the harness.
- No architecture reset: the same clone-buffer + scroll-normalization approach
  survived every correction cycle.
- Prolonged local patching with path dependence (sunk-cost).

## 5. Adopted controls

The following now encode the lessons durably:

- `skills.md` §8.8 — F0–F3 frontend interaction risk classification and hard
  gates (browser ground truth, harness validity, two-strike stop-loss, F3
  strategy gate).
- `.agents/skills/browser-interaction-engineering/SKILL.md` — detailed
  specialist guidance: state ownership, continuous-vs-settled events, geometry
  and subpixel rules, debugging protocol, harness qualification, Playwright
  usage, completion checklist.
- `docs/frontend-architecture.md` → "Browser Interaction and Motion Architecture"
  — application-level principles.
- `context.md` — concise approved project policy.
- `MyGameDNA_ASSISTANT_OPERATING_RULES.md` — planning-assistant frontend
  interaction preflight.
- `apps/frontend/tests/browser/homepage-carousel.spec.ts` — real-browser
  regression proving forward and reverse looping across multiple wraps.
- `apps/frontend/playwright.config.ts` + `test:frontend:browser` scripts.

The intent is that a future agent hitting `human FAIL` + `automation PASS` is
forced to validate its harness before another correction run, and that two
failed corrections force an architecture reset instead of a third local patch.
