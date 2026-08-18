# Classification Rules Verification — SBGC-66

This document records the verification evidence for the SBGC-65 derived
classification engine. It proves the mathematical rules already implemented
under `classifications/calculations/` behave as specified in
`docs/statistical_model.md`, and it closes the first true end-to-end N=1
Superuser workflow.

All expected values are derived independently from
`docs/statistical_model.md` — never by snapshotting the implementation's own
output. No mathematical constant, threshold, or equation was changed by this
ticket.

## Scope

- Isolated Method 1 verification with independently computed fixtures.
- Method independence acceptance test (Methods 1/2/3 are separate).
- A locked Method 2 vs Method 3 divergence proving the two population methods
  legitimately differ.
- Source-submission validation (invalid rejection + valid extremes).
- Largest-remainder / exact-100 reconciliation (already covered by SBGC-65
  `test_calculations_core.py`; retained as neighbourhood evidence).
- Status logic (legitimate domain outcome vs engine failure).
- Recalculation / epoch replacement semantics.
- A true N=1 Superuser end-to-end workflow through the real service, persistence,
  calculation, read-contract, and Admin-readonly boundaries.
- A found-and-fixed production defect.

## Isolated Method 1 evidence

File: `classifications/tests/test_method1_isolated.py` (26 tests).

- `_sample_sd` Bessel correction verified against a hand-computed sample
  (`[1, 2, 3, 4, 5]`), and the constant-series → 0 and single-value → 0
  branches.
- `sn_scale` verified against a hand-computed `Sn` and its constant → 0 branch.
- `_whole_submission_retain` locks the 2-of-6 rule: 0 or 1 flagged dimension
  retains the whole submission; 2+ flags reject all six scores.
- Population-influence boundaries (`9` → `0.25`, `20` → `0.0`, `49` →
  `0.0625`, `50` → `0.03125`, `400` → `0.02`, `401` → `0.0`) derived from
  `docs/statistical_model.md` §15.3, not from the function.
- Anchor hierarchy: Superuser beats Moderator beats Community Leader; two
  Moderators beat one Community Leader; one Moderator + five Community Leaders
  resolves to the Community Leader anchor.
- Frozen N boundaries 0/1/8/9/19/20/49/50/51/400/401 exercised.
- High-N coefficient non-negativity and normalization (sum to 1 for N ≥ 401).
- Deterministic replay across repeated runs.

Method 1A (mean + Bessel-corrected sample SD) and Method 1B (median + `Sn`)
detector agreement, whole-submission rejection, and role-weighted aggregation
are covered by SBGC-65 `classifications/tests/test_calculations_method1.py`
(23 tests) and remain green.

## Method 2 / Method 3 isolated evidence

File: `classifications/tests/test_calculations_method2.py` (14 tests) and
`classifications/tests/test_calculations_method3.py` (14 tests) — SBGC-65
neighbourhood, re-run green.

These cover the frozen custom six-independent-one-dimensional Isolation Forest
(minimum N, constant dimension, extreme handling, deterministic replay,
strict threshold, 2-of-6 rejection, survivor mean) and LoOP (k=10 tie-inclusive
neighbourhoods, degenerate density/PLOF/nPLOF branches, strict threshold,
2-of-6 rejection, survivor mean, row-order invariance).

### Method 2 vs Method 3 divergence

File: `classifications/tests/test_method_divergence.py` (2 tests).

A dense 3-member minority cluster (`(8, 12, 80)` against a `(45, 30, 25)`
majority) is globally isolated, so Method 2 rejects it (3 rejected, survivor
mean `(45, 30, 25)`), while Method 3's local-density view retains it
(0 rejected, survivor mean `(41, 28, 31)`). This proves the two population
methods legitimately differ. An 8-member cluster is retained by both, showing
the divergence is not an unconditional disagreement.

## Method independence acceptance test

File: `classifications/tests/test_method_independence.py` (4 tests).

- Changing only role snapshots (Superuser anchor flattened to Community)
  changes Method 1 (READY → INSUFFICIENT_ANCHOR) but leaves Method 2 and
  Method 3 `raw_challenge`/`raw_reward` byte-identical.
- All three methods see the full raw pre-rejection N (Method 1 rejection is
  not fed into Methods 2/3).
- Method 2 and Method 3 are computed independently of each other.
- After a real `run_game_calculation`, all four score sets persist on distinct
  `ClassificationSnapshot` fields (`method_1/2/3_*` plus `unified_*`), each
  integer profile sums to exactly 100, and the unified result does not overwrite
  the individual method results.

## Source-submission validation

File: `classifications/tests/test_validation_extremes.py` (7 tests).

- Rejected: missing component, negative component, component > 100,
  Challenge total ≠ 100, Reward total ≠ 100.
- Accepted: valid extremes `100/0/0`, `0/100/0`, `0/0/100` (both Challenge and
  Reward), proving extreme-but-valid compositions are not confused with
  invalid data.

## Largest-remainder / exact-100

Retained from SBGC-65 (`classifications/tests/test_calculations_core.py`):
raw exact-100, residual 0/1/2, deterministic Micro > Macro > Mystiko tie
priority, Challenge and Reward independence, all displayed READY profiles sum
exactly 100, and impossible-residual → calculation error. No historical ±3
repair rule is present.

## Status logic

File: `classifications/tests/test_recalculation_status.py` (3 tests), plus
SBGC-65 `classifications/tests/test_calculations_persistence.py`.

- `NO_SUBMISSIONS` and `INSUFFICIENT_ANCHOR` are legitimate domain outcomes that
  become the current published state (replacing an obsolete READY), never a
  stale fallback.
- Only engine/system failure (e.g. `CALCULATION_ERROR`, an unhandled exception)
  retains the previous current snapshot as a stale fallback.
- A legitimate non-ready domain outcome is not retried as infrastructure failure.

## Recalculation / epoch replacement

File: `classifications/tests/test_recalculation_status.py`.

- A new valid submission changes the population hash, triggers a recalculated
  successful snapshot that becomes current, and leaves the old snapshot
  historical.
- An unexpected engine failure does not partially replace the current snapshot.

## N=1 Superuser end-to-end workflow

File: `classifications/tests/test_n1_superuser_e2e.py` (1 test).

- Superuser `thenamesammaris` (test-only credential, no committed password).
- Disposable Game `SBGC 66 N1 Classification Test`
  (`sbgc-66-n1-classification-test`).
- One submission via `create_submission`: Challenge `50/30/20`, Reward
  `20/30/50` (Micro/Macro/Mystiko order in the profile fields).
- Verified N=1, immutable role snapshot = `superuser`, and all six source values
  persisted exactly.
- Canonical `run_game_calculation` produces a provisional `READY` snapshot:
  Method 1 = READY, Methods 2/3 not applicable (`""` status / `None` in the
  read contract), full BHPCM unified regime not executed, current Final
  Classification = `[50, 30, 20]` / `[20, 30, 50]` (the correct Method 1 N=1
  result — the source submission itself).
- Provisional Confidence ≈ 5.98 (independently derived), label `Low`, and
  < 50 as required.
- `get_published_classification` returns identical numeric values/status/regime/
  confidence.

## Admin read-only evidence

File: `classifications/tests/test_admin_readonly.py` (4 tests).

For `ClassificationSnapshot`, `CalculationEpoch`, and `BoundaryCalibration`:

- every model field is in `readonly_fields`;
- `has_add_permission`, `has_change_permission`, and `has_delete_permission`
  are all `False`.

Calculated scores, confidence, provenance, and method results cannot be
created/edited/deleted through Admin.

## Defect found and fixed

`classifications/calculations/profiles.py::_validate_submission` crashed with a
`TypeError` before its `isinstance` check when a component was non-numeric: it
called `profile.total()` (a `str + float` / `float + bool` sum) before the
per-component type check. This is a real production bug — a malformed source
record could bypass the friendly validation boundary and surface a traceback
instead of being excluded as invalid.

Fix: compute `components = (profile.micro, profile.macro, profile.mystiko)`,
perform the per-component numeric/finite/range checks first, then compute
`total = sum(components)` and apply the total-exactly-100 check. No equation,
threshold, or validation semantics changed.

The `test_validation_extremes.py::test_missing_component_excluded` fixture
preserves this regression (a non-numeric component is now excluded cleanly
rather than crashing).

## Testing philosophy applied

- Many cheap, independent pure-math fixtures; few integration tests.
- Level 1 (isolated math/status/E2E): 47 new tests, all green.
- Level 2 (classification neighbourhood): `classifications` suite passes
  (415 executed + 12 skipped on SQLite; discovery reports 448 test methods).
- Level 3 (full backend): run once after the production defect fix —
  1,687 discovered tests pass (24 skipped). Not re-run after test-only
  type-annotation edits, per SBGC-66 §14 (no ceremony).

## Heavy suites intentionally skipped

- PostgreSQL: no SBGC-66 change touches PostgreSQL-specific semantics; the
  fixed defect is pure input validation. SBGC-65's PostgreSQL verification
  (migration 0006, partial-unique current index, concurrency) remains valid and
  unchanged.
- Frontend, live Steam, reverse/shuffle, warnings: not applicable — no frontend,
  network, resource-lifecycle, or shared-fixture/order changes.

## Human verification checklist (4 steps)

1. Open the temporary N=1 submission and verify `thenamesammaris`, `Superuser`
   provenance, and the six submitted values.
2. Open the current Final Classification and verify the Challenge result, Reward
   result, provisional Confidence Level, and status.
3. Verify N=1 does not misleadingly show Method 2 / Method 3 / full BHPCM as
   available.
4. Verify all calculated Final Classification / confidence / provenance fields
   are read-only in Admin.

Human verification is pending; automated evidence above is complete.
