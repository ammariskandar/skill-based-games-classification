---
name: browser-interaction-engineering
description: Engineering discipline for browser-interaction work that depends on scrolling, animation, gestures, runtime geometry, or timing (F2/F3 frontend risk). Load this when implementing, debugging, reviewing, or testing a frontend feature whose correctness depends on real browser runtime state — especially anything involving scrollLeft/scrollTop, scroll snap, smooth scrolling, requestAnimationFrame, ResizeObserver/IntersectionObserver, image load/error, drag/swipe/pointer gestures, or compositor/animation synchronization.
---

# Browser Interaction Engineering

This skill governs frontend work where the **browser runtime is the source of
truth**. It exists because of SBGC-191: a small infinite-carousel feature that
burned ~8 correction cycles because the agent (1) assumed browser geometry was
exact, (2) normalized loop position from a high-frequency `scroll` handler
during an active smooth `scrollBy`, and (3) validated against a virtual-time
headless harness that never executed the real smooth-scroll path.

Most of this skill is **not** new engineering knowledge; it is a set of hard
checks that SBGC-191 showed are easy to skip and expensive to skip.

## 1. Risk classification (apply first)

Classify every frontend ticket before implementation. Do not treat F3 work like
ordinary Astro markup.

| Level | Definition | Typical validation |
| --- | --- | --- |
| **F0 — Static presentation** | Astro markup, typography, static cards, ordinary responsive CSS, SSR data display, static metadata | unit/static tests, `astro check`, build, visual review. Real-browser optional. |
| **F1 — Deterministic interaction** | modal open/close, disclosure, form visibility, conditional fields, simple click state, `localStorage` preference, explicit class toggling | unit/helper tests + focused browser smoke where visual/runtime behavior matters. No large E2E suite by default. |
| **F2 — Browser-state-dependent interaction** | `scrollLeft`/`scrollTop`, runtime DOM measurement, `ResizeObserver`/`IntersectionObserver`, image `load`/`error`, responsive geometry, element positioning from actual browser dimensions | **real-browser runtime validation required**. Pure unit tests are supplementary only. |
| **F3 — Motion / timing / gesture / compositor-sensitive** | infinite carousel, smooth scrolling, scroll snap interactions, drag/swipe, pointer movement, animation synchronization, transition-dependent state, runtime transform loops, D3 transitions, canvas/WebGL/WebGPU, rAF coordination | architecture strategy comparison + real-browser prototype + real-browser automated regression + human visual validation where perceptual correctness matters. |

SBGC-191 is the canonical F3 ticket. If a ticket smells like it, escalate the
risk classification rather than assuming F1.

## 2. The browser runtime is the source of truth

When correctness depends on animation, scrolling, snapping, gestures, runtime
layout, frame timing, rendering, or compositor state, **the real browser is the
runtime source of truth**.

Pure or synthetic tools may supplement but cannot substitute:

- pure mathematical helper tests
- jsdom / happy-dom
- static HTML simulation
- manual `scrollLeft` mutation
- virtual-time headless Chrome
- DOM-only simulation
- mocked scroll events

These are useful for logic but must not be represented as evidence that a real
motion/timing behavior works.

If you are reasoning about what a browser "probably does," stop and measure it
in a real browser instead.

## 3. State ownership (competing state machines)

For F2/F3 work, before implementation, list every system capable of mutating the
same visual/runtime state.

Example for "horizontal carousel position":

| Owner | Mutates state? |
| --- | --- |
| native user scroll | yes |
| `Element.scrollBy({ behavior: "smooth" })` | yes |
| CSS scroll snap | yes (re-snaps after operations) |
| direct `scrollLeft` assignment | yes |
| transform animation | yes |
| DOM normalization/reordering | yes (changes layout) |

Then answer, in writing:

- Who owns **motion**?
- Who owns **normalization**?
- When may each mutate state?
- Can two systems mutate the same state **simultaneously**?

Strong preference: **one authoritative state owner per phase of interaction.**
If multiple systems must coordinate, the lifecycle boundaries must be explicit.
Never assume browser features compose safely merely because each API is
individually valid — `scroll-snap-type: x mandatory` and a programmatic
`scrollLeft` write both target the same coordinate and can fight each other.

## 4. Continuous-event vs settled-state work

High-frequency lifecycle events — `scroll`, `pointermove`, `mousemove`,
`resize`, `requestAnimationFrame` — should be limited to:

- measurement;
- lightweight visual state;
- passive observation;
- throttled/rAF-updated effects.

Structural mutations — teleporting `scrollLeft`, DOM rotation, clone
normalization, reindexing, layout reset — should normally happen **only after
the interaction has settled**, using semantic signals where supported:
`scrollend`, `transitionend`, `animationend`, `pointerup`, or a carefully
justified fallback.

SBGC-191 lesson, stated generically: continuous brightness measurement during
scroll and loop-position normalization are **different classes of work** and
should not share one handler. The first is continuous and safe; the second is
structural and must wait for settle.

## 5. Real-browser validation

For F2/F3:

1. Use a real browser engine, real timers, and the real animation lifecycle.
2. Do **not** use `--virtual-time-budget` (or equivalent virtual-time
   acceleration) to validate a behavior that depends on actual animation
   progression unless you have explicit proof the accelerated mode preserves
   that mechanism. Virtual time replaces real-time with a synthetic source and
   may fast-forward past delayed tasks; it does not reliably advance smooth
   scroll animations frame-by-frame.
3. Wait for semantic/observable completion (`scrollend`, settled `scrollLeft`,
   a stable DOM predicate), not arbitrary giant sleeps.
4. Prefer real Chromium first. Cross-browser expansion (Firefox/WebKit) only
   when product/browser risk justifies it, not as ritual.

## 6. Harness-validity gate

Before trusting any automated harness for an F2/F3 bug, **prove the harness
actually executes the browser mechanism under test**.

For smooth scrolling, the harness itself must demonstrate:

```text
start scroll position
→ real intermediate motion over browser frames
→ scroll events
→ settled final scroll state
```

If the target behavior is smooth scrolling and the harness changes `scrollLeft`
instantaneously or does not move it at all, that harness is **INVALID** for that
bug.

If `human browser = FAIL` but `automation = PASS`, the immediate assumption is:

> the automation/harness may be invalid

**not** "keep modifying production code until it satisfies both."

Required workflow when that mismatch appears:

1. stop production changes;
2. reproduce the human failure in instrumentation;
3. validate the harness;
4. only then resume correction.

## 7. Two-strike stop-loss

If the same user-visible interaction defect survives **two correction attempts**,
STOP. No third substantially similar implementation correction may proceed
automatically.

Required process:

1. freeze code-changing work;
2. record the exact observed failure;
3. inspect `git diff`, current source, and relevant history;
4. validate the testing harness;
5. identify all systems/state machines involved;
6. challenge the current architecture;
7. compare at least two viable alternative implementation strategies;
8. start a fresh agent context/session if the trajectory is long or contaminated;
9. proceed only after explaining why the next architecture is different, or why
   the existing one remains justified.

A third patch using materially the same architecture requires explicit written
justification. This rule exists to prevent the `patch → patch → patch → …`
sunk-cost loop.

## 8. Debugging protocol

Use this sequence for browser-interaction defects. Do not start from a theory.

### OBSERVE

Reproduce the exact reported runtime problem. Write the observable symptom
plainly, e.g. "After repeated Previous operations, the carousel reaches a
physical left boundary and can no longer move."

### INSTRUMENT

Measure actual browser state: `scrollLeft`, `scrollWidth`, `clientWidth`,
`devicePixelRatio` where relevant, card bounding rects, event timing, active
animation state, relevant DOM attributes. Use browser devtools/automation.

### ISOLATE

Identify the smallest set of state machines involved (e.g. smooth programmatic
scrolling + scroll snap + normalization).

### FALSIFY

Attempt to disprove the current hypothesis with controlled experiments:

- disable scroll snap temporarily;
- use `behavior: "auto"` instead of `"smooth"`;
- disable normalization;
- inspect DPR 1 vs DPR 2;
- wait until scroll completion before normalizing.

Change one variable at a time.

### PATCH

Only after evidence identifies a cause. Do not patch solely because a value
"looks suspicious."

### VERIFY

Re-run the exact real-browser reproduction that previously failed, then run
focused regression tests.

## 9. Geometry and subpixel rule

Values from `getBoundingClientRect()`, `scrollLeft`, `clientWidth`, layout
widths, transforms, and `calc()` may involve fractional CSS pixels,
device-pixel-ratio effects, browser rounding, and subpixel layout. Do **not**
assume `computed ideal position === browser-returned position`.

`scrollLeft` is documented as subpixel-precise but is only fractional on a
subpixel-precise device (e.g. DPR 2); on a DPR-1 device it rounds to whole
pixels. Code that compares a fractional boundary against an integer scroll
offset is device-dependent and fragile.

Use tolerances where the semantic condition is approximate. But:

> An epsilon is not automatically a root-cause fix.

Every tolerance must have a documented semantic reason (e.g. "absorb ≤0.5px
rounding at DPR 1"). Do not solve every geometry bug by adding arbitrary pixels.

## 10. Magic-number / timing rule

For constants like `80ms`, `120ms`, `1px`, `2 frames`, be able to answer:

- What lifecycle/state does this approximate?
- Why is a semantic browser event not used?
- What failure occurs if hardware/timing differs?

Prefer semantic completion events (`scrollend`, `transitionend`,
`animationend`) over timing guesses. If a debounce fallback is necessary
(because `scrollend` is newly-available or unsupported), isolate and document
it. Do not tune arbitrary delays over repeated correction runs without runtime
evidence.

## 11. Alternative-strategy gate (F3)

Before substantial implementation of an F3 ticket, write a short comparison of
at least two viable approaches. For an infinite carousel:

| Approach | State owners | Native scroll | A11y | Animation complexity | Timing sensitivity |
| --- | --- | --- | --- | --- | --- |
| native scroll + clone normalization | 2+ (scroll + snap + JS) | yes | must hide clones | low | high |
| transform/index-controlled | 1 (JS) | no (JS-driven) | easier | medium | medium |
| DOM rotation | 1 (JS) | no | medium | low | low |

Compare on: number of state owners, interaction with current architecture,
accessibility, native scrolling, animation complexity, responsive behavior,
testability, browser timing sensitivity, regression surface. Choose explicitly.
Do not select the first familiar pattern without comparison.

## 12. Astro DOM/scoping interaction

This skill cross-references `docs/frontend-architecture.md` → "Astro CSS
ownership and scoping". Before dynamically cloning, moving, creating, or
reparenting DOM in Astro, check:

- who owns the DOM?
- does scoped CSS still match?
- will runtime-created nodes receive the expected `data-astro-*` attributes?

`cloneNode(true)` on a rendered node preserves existing scope attributes;
manually reconstructed markup does not. Do not solve browser-interaction issues
by blindly making component CSS global. The two disciplines — Astro DOM
ownership and browser runtime state ownership — are related, not separate.

## 13. Context reset / correction hygiene

If any of the following are true, start a fresh diagnostic session before
further implementation:

- multiple corrections have occurred;
- agent context has been compacted;
- architecture has been repeatedly patched;
- the same reasoning is being re-derived.

The fresh session must receive: current source, current diff, the exact
human-observed defect, known failed hypotheses, and validated runtime evidence.
Do not carry pages of speculative historical reasoning as authoritative context.
Repository/source/runtime evidence outranks old agent thoughts.

## 14. Human validation still matters

Browser automation can prove: does not get stuck, cycles correctly, preserves
logical ordering. It does **not** automatically prove: no perceptible flicker,
good animation quality, correct visual rhythm. For F3 visual interactions,
human validation remains required unless the ticket explicitly states otherwise.
Never claim unit/browser tests prove aesthetic or perceptual correctness.

## 15. Performance considerations

- Keep `scroll`/`pointermove` handlers passive and cheap.
- Batch reads/writes; avoid forced synchronous layout (`getBoundingClientRect()`
  followed by a write) in a hot path.
- Use `requestAnimationFrame` to coalesce visual updates.
- Avoid per-frame `getBoundingClientRect()` over a large card set when a cached
  measurement suffices; re-measure on resize/orientation change.

## 16. Common failure patterns

1. Normalizing/normalizing loop position from every `scroll` event (cancels
   smooth `scrollBy`).
2. Comparing integer scroll offset against fractional geometry without a
   documented tolerance.
3. Validating smooth/motion behavior under virtual-time headless.
4. Assuming `scroll-snap-type: mandatory` composes with programmatic scroll
   writes (it re-snaps after the operation).
5. Trusting `tests pass` while the harness does not execute the failing path.
6. Patching (epsilon/delay/threshold) repeatedly without challenging the
   architecture or the harness.
7. Cloning/reparenting Astro DOM without checking scope-attribute ownership.

## 17. Completion checklist (F2/F3)

- [ ] Ticket classified F0/F1/F2/F3 before implementation.
- [ ] If F3: alternative strategies compared and one chosen explicitly.
- [ ] State owners enumerated; no two systems mutate the same state
      simultaneously without explicit lifecycle boundaries.
- [ ] Continuous events do measurement/visual state only; structural
      normalization happens after settle (semantic event or justified fallback).
- [ ] Real-browser evidence captured for the actual runtime mechanism.
- [ ] Harness proven to exercise the mechanism (not just unit/helper logic).
- [ ] Reverse AND forward directions covered across multiple wraps if looping.
- [ ] Reduced-motion path tested separately, not substituted for ordinary mode.
- [ ] Geometry tolerances documented with a semantic reason.
- [ ] Any magic number/timing constant justified in code or docs.
- [ ] Human visual validation performed where perceptual correctness matters.
- [ ] No local-patch loop beyond the two-strike stop-loss.
