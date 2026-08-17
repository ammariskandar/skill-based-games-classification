# Derived Classification Calculation — SBGC-65

Canonical documentation for the derived-classification engine.

The normative mathematical specification is `docs/statistical_model.md`
(`STATISTICAL_MODEL_V1.0.0`).  That file is law: every formula, threshold,
seed, and status condition implemented here is transcribed from it.  This
document describes the *implementation architecture* only and must never
contradict the specification.

## 1. What the engine produces

For a Game, one daily-epoch calculation produces a versioned snapshot that
separately persists **four score sets** (for normal `N >= 20`):

1. **Method 1** — role-aware anchored aggregation (mean/SD detector 1A,
   median/Sn detector 1B, anchor hierarchy, role weights, population
   influence, high-N anchor reliability).
2. **Method 2** — six independent one-dimensional Isolation Forests
   (512 trees/dimension, subsample `min(256, N)`, height `ceil(log2 psi)`,
   threshold 0.60 strict, seed 42).
3. **Method 3** — six independent one-dimensional LoOP analyses
   (k = 10, λ = 3, τ = 0.75 strict, tie-inclusive neighborhoods).
4. **BHPCM_V1 unified Final Classification** — the Bayesian Hierarchical
   Pluralistic Consensus Model over the three continuous method outputs.

Methods 1/2/3 are pseudo-final analytical results and are never
arithmetic-averaged into the unified result, and the individual Method
results are never overwritten by the unified result.

### Regimes

| Raw N | Regime | Published result |
|---|---:|---|
| 0 | — | `NO_SUBMISSIONS`, no scores |
| 1–19 | provisional | Method 1 (if READY) + `PROVISIONAL_CONFIDENCE_V1` |
| ≥ 20 | unified | Methods 1/2/3 + BHPCM + `CONFIDENCE_V2` |

`N` is always the **raw pre-rejection** count of validated submissions.

## 2. Confidence stack (unified regime)

```
BHPCM READY
-> CONFIDENCE_BASE_V1      (population saturation + authoritative support
                            + deviation/variance coherence penalties)
-> CONFIDENCE_RESILIENCE_V1 (bounded population resilience, never lifts
                            a base below 50 to 50+)
-> BOUNDARY_CONTINUITY_V1   (static per-Game/per-version negative-cliff
                            calibration, decaying with N)
-> CONFIDENCE_V2           (final displayed Confidence Level, capped at 100)
```

The provisional regime uses `PROVISIONAL_CONFIDENCE_V1` (Qn-style Aitchison
dispersion with frozen finite-sample factors; strictly `< 50`).

## 3. Persistence

Models in `apps/backend/classifications/models.py`:

- `CalculationEpoch` — one daily batch (`epoch_id`, `cutoff_at`, timing,
  version, aggregate counts).
- `ClassificationSnapshot` — one immutable result per Game/epoch.  Carries
  the four score sets (raw continuous + reconciled integers), confidence,
  conflict classification, and full provenance JSON (posterior diagnostics,
  credible intervals, method-weight summaries, sensitivity profiles).
- `BoundaryCalibration` — the static per-Game/per-calculation-version
  boundary constant with full calibration provenance.
- `CalculationAttempt` — one attempt (initial or retry) per Game/epoch.

Exactly one `ClassificationSnapshot` per Game is `is_current`; a partial
unique index (`classification_snapshot_single_current_uniq`) makes the DB
the last-resort enforcement layer for single-current promotion.

### Atomic publication

A snapshot becomes current only after the entire applicable regime computed
successfully and invariants passed.  Partial snapshots never become
current.  All derived data is **read-only**: no Admin form, superuser, or
API consumer may edit calculated scores, confidence, or provenance.

### Previous-success fallback

A failed current run never blanks yesterday's successful classification.
The previous successful snapshot remains the published result and is marked
stale internally.  With no prior successful snapshot the read contract
returns an explicit unavailable state — never 0/0/0, a mean, or a
substitute.

## 4. Daily epoch, retries, notifications

- A scheduler (platform cron or equivalent) invokes
  `manage.py run_daily_classification` once per day.  The engine itself is
  scheduler-vendor independent.
- Eligibility uses `cutoff_at`: a submission whose `updated_at` is after
  the cutoff belongs to the next epoch (Part E.2).
- Inputs are frozen, calculated **outside** any long transaction, then
  persisted and promoted in a short atomic block.
- Engine failures are retried: initial attempt + 3 retries = maximum
  **four attempts per Game per epoch**; only failed Games are retried.
  Retry delay is configuration-driven
  (`CLASSIFICATION_RETRY_DELAY_SECONDS`, default 60).
- Domain outcomes (`NO_SUBMISSIONS`, `INSUFFICIENT_ANCHOR`,
  `INSUFFICIENT_SAMPLE_*`, `NO_SURVIVING_SUBMISSIONS`,
  `INSUFFICIENT_METHOD_*`, `UNIFIED_CALCULATION_UNSTABLE`) are
  mathematical results, not infrastructure failures, and are not retried.
- After the final failed attempt the
  `CalculationFailureNotifier` scaffold is invoked with the Game id/name,
  epoch id, version, attempt count, failure category, safe error summary,
  and timestamp.  **Email delivery is deferred future work**; today the
  scaffold logs the structured notice.

## 5. Read contract for future consumers

`classifications.services.calculations.get_published_classification(game)`
returns the product-facing result: availability/status, the unified
Challenge/Reward integer profiles, Confidence Level + label, submission
count, conflict classification, the three Method profiles, calculated-at,
stale flag, and calculation versions.  Numeric values stay numeric; no
consumer reconstructs the mathematics.

No speculative API endpoint exists yet; when the frontend needs it, the
read service is the intended boundary.

## 6. Input snapshot

At run start, for each Game the service collects every valid submission
(effective state at/before the cutoff), canonicalizes ordering by stable
identifier (`submission-<pk>`), includes the immutable role snapshots, and
computes a SHA-256 `input_population_hash`.  Invalid submissions
(missing profile, out-of-range, non-100 total) are excluded **before** N is
established; received/invalid/validated counts are recorded.

## 7. Simulation and performance evidence

`manage.py run_classification_simulation` runs the required Part F program
(N boundaries, 30 population scenarios, role structures, 19→20 boundary
study, resilience pathological study, random invariants) and writes
`docs/classification-simulation-report.md` with seeds and provenance.

Representative single-run timing (measured on local hardware, bootstrap =
simulation configuration, see report): at N=20 a full unified calculation
with the frozen production B=10,000 bootstrap takes on the order of an
hour; at N=1000 the same frozen run is on the order of two days of CPU.
The engine is intentionally asynchronous daily computation; interactive
latency is not the target, and the mathematics is not weakened for
benchmark numbers.

## 8. Out of scope

- Email delivery for final-failure notifications (scaffold only).
- Frontend integration, charts, and the AstroJS read endpoint.
- SBGC-66 (classification-rule tests) and any future calculation-version
  changes.

## 9. Determinism and provenance

Identical population, stable identifiers, role snapshots, versions, and
randomization provenance reproduce identical stored outputs
(`random_stream_identifier` derives from the input-population hash).
Row/retrieval order never affects results.
