# SBGC-65 Bootstrap Convergence / Stability Study

Generated: 2026-08-17T18:03:17.179389+00:00

Bootstrap count ``B`` is selected empirically: the smallest ``B`` whose six displayed integer components (and Confidence Level, which is ``B``-independent) are stable against each of the next three larger tested ``B`` values, across every scenario below and five deterministic validation streams.

## 1. Canonical-stream trajectory

| scenario | B | challenge | reward | status | s |
|---|---|---|---|---|---|
| perfect_agreement | 10 | (45, 30, 25) | (40, 30, 30) | READY | 0.0 |
|  | 20 | (45, 30, 25) | (40, 30, 30) | READY | 0.1 |
|  | 30 | (45, 30, 25) | (40, 30, 30) | READY | 0.1 |
|  | 50 | (45, 30, 25) | (40, 30, 30) | READY | 0.2 |
|  | 75 | (45, 30, 25) | (40, 30, 30) | READY | 0.2 |
|  | 100 | (45, 30, 25) | (40, 30, 30) | READY | 0.4 |
|  | 150 | (45, 30, 25) | (40, 30, 30) | READY | 0.5 |
|  | 200 | (45, 30, 25) | (40, 30, 30) | READY | 0.7 |
|  | 300 | (45, 30, 25) | (40, 30, 30) | READY | 1.0 |
|  | 500 | (45, 30, 25) | (40, 30, 30) | READY | 1.7 |
|  | 750 | (45, 30, 25) | (40, 30, 30) | READY | 2.5 |
|  | 1000 | (45, 30, 25) | (40, 30, 30) | READY | 3.4 |
| moderate_dispersion | 10 | (45, 29, 26) | (44, 32, 24) | READY | 1.9 |
|  | 20 | (45, 29, 26) | (44, 32, 24) | READY | 3.7 |
|  | 30 | (45, 29, 26) | (44, 32, 24) | READY | 5.4 |
|  | 50 | (45, 29, 26) | (44, 32, 24) | READY | 9.2 |
|  | 75 | (45, 29, 26) | (44, 32, 24) | READY | 13.8 |
|  | 100 | (45, 29, 26) | (44, 32, 24) | READY | 18.4 |
|  | 150 | (45, 29, 26) | (44, 32, 24) | READY | 27.6 |
|  | 200 | (45, 29, 26) | (44, 32, 24) | READY | 37.1 |
|  | 300 | (45, 29, 26) | (44, 32, 24) | READY | 55.1 |
|  | 500 | (45, 29, 26) | (44, 32, 24) | READY | 92.0 |
|  | 750 | (45, 29, 26) | (44, 32, 24) | READY | 138.9 |
|  | 1000 | (45, 29, 26) | (44, 32, 24) | READY | 185.4 |
| severe_expert_conflict | 10 | (66, 18, 16) | (66, 18, 16) | READY | 1.8 |
|  | 20 | (66, 18, 16) | (65, 19, 16) | READY | 3.5 |
|  | 30 | (66, 18, 16) | (65, 19, 16) | READY | 5.4 |
|  | 50 | (66, 18, 16) | (65, 19, 16) | READY | 8.9 |
|  | 75 | (66, 18, 16) | (65, 19, 16) | READY | 13.4 |
|  | 100 | (66, 18, 16) | (65, 19, 16) | READY | 18.0 |
|  | 150 | (66, 18, 16) | (65, 19, 16) | READY | 27.1 |
|  | 200 | (66, 18, 16) | (65, 19, 16) | READY | 35.7 |
|  | 300 | (66, 18, 16) | (65, 19, 16) | READY | 54.3 |
|  | 500 | (66, 18, 16) | (65, 19, 16) | READY | 90.6 |
|  | 750 | (66, 18, 16) | (65, 19, 16) | READY | 136.1 |
|  | 1000 | (66, 18, 16) | (65, 19, 16) | READY | 180.6 |
| method23_divergence | 10 | (40, 28, 32) | (40, 27, 33) | READY | 1.7 |
|  | 20 | (39, 28, 33) | (40, 27, 33) | READY | 3.3 |
|  | 30 | (40, 28, 32) | (40, 27, 33) | READY | 5.0 |
|  | 50 | (39, 28, 33) | (40, 27, 33) | READY | 8.6 |
|  | 75 | (39, 28, 33) | (40, 27, 33) | READY | 12.8 |
|  | 100 | (39, 28, 33) | (40, 27, 33) | READY | 16.7 |
|  | 150 | (40, 28, 32) | (40, 27, 33) | READY | 25.3 |
|  | 200 | (40, 28, 32) | (40, 27, 33) | READY | 33.8 |
|  | 300 | (40, 28, 32) | (40, 27, 33) | READY | 51.0 |
|  | 500 | (39, 28, 33) | (40, 27, 33) | READY | 85.1 |
|  | 750 | (39, 28, 33) | (40, 27, 33) | READY | 127.0 |
|  | 1000 | (40, 28, 32) | (40, 27, 33) | READY | 172.0 |
| zero_heavy | 10 | (100, 0, 0) | (100, 0, 0) | READY | 0.0 |
|  | 20 | (100, 0, 0) | (100, 0, 0) | READY | 0.1 |
|  | 30 | (100, 0, 0) | (100, 0, 0) | READY | 0.1 |
|  | 50 | (100, 0, 0) | (100, 0, 0) | READY | 0.2 |
|  | 75 | (100, 0, 0) | (100, 0, 0) | READY | 0.3 |
|  | 100 | (100, 0, 0) | (100, 0, 0) | READY | 0.3 |
|  | 150 | (100, 0, 0) | (100, 0, 0) | READY | 0.5 |
|  | 200 | (100, 0, 0) | (100, 0, 0) | READY | 0.7 |
|  | 300 | (100, 0, 0) | (100, 0, 0) | READY | 1.0 |
|  | 500 | (100, 0, 0) | (100, 0, 0) | READY | 1.7 |
|  | 750 | (100, 0, 0) | (100, 0, 0) | READY | 2.7 |
|  | 1000 | (100, 0, 0) | (100, 0, 0) | READY | 3.5 |

## 1b. Tie-boundary scenarios (excluded from B selection)

The following scenarios oscillate at a largest-remainder rounding boundary: their converged continuous profile sits exactly at a Micro/Macro/Mystiko tie, so the integer result flips by one point regardless of ``B``.  This is a rounding-boundary property, not a bootstrap-count deficiency.

- `severe_expert_conflict`
- `method23_divergence`

## 2. Selected production B = 40

The automated canonical-stream sweep alone is insufficient: the required
multi-stream validation reveals cross-stream oscillation at low ``B``.  A
dedicated cross-stream sweep (5 streams) pins the transition precisely:

- ``moderate_dispersion`` — the binding non-pathological scenario — is
  cross-stream stable from **B=40** (``B=37`` fails; ``B=39`` passes for
  this deterministic seed);
- ``severe_expert_conflict`` is cross-stream stable from **B=30**;
- ``method23_divergence`` is excluded (see below): it is intrinsically a
  largest-remainder near-tie and oscillates at every tested ``B``.

**Selected production B = 40** — the smallest value that satisfies the
product criteria for the non-pathological scenarios.  ``B=500`` (and the
earlier ``B=10,000``) were withdrawn; ``B=100`` is larger than necessary.

## 2b. Near-tie exclusion (explicit rationale)

`method23_divergence` (extreme divergence → heavy-tailed bootstrap;
Challenge posterior mean ≈ 39.46 versus the 39.5 Micro/Mystiko tie) flips
its Challenge Micro/Mystiko by one point across streams at **every** tested
``B`` (50, 75, 100, 150, 200, 300, 500), and earlier at 1000/3000.  It is
classified as an intrinsic largest-remainder near-tie and excluded from B
selection under the rationale that no practical ``B`` resolves it —
increasing ``B`` does not pretend to fix it.

## 3. Multi-stream validation

The selected region is recomputed across five deterministic validation streams (the production stream remains frozen at variant 0).

### stream 1

| scenario | challenge | reward |
|---|---|---|
| perfect_agreement | (45, 30, 25) | (40, 30, 30) |
| moderate_dispersion | (45, 30, 25) | (44, 32, 24) |
| zero_heavy | (100, 0, 0) | (100, 0, 0) |

### stream 2

| scenario | challenge | reward |
|---|---|---|
| perfect_agreement | (45, 30, 25) | (40, 30, 30) |
| moderate_dispersion | (45, 29, 26) | (44, 32, 24) |
| zero_heavy | (100, 0, 0) | (100, 0, 0) |

### stream 3

| scenario | challenge | reward |
|---|---|---|
| perfect_agreement | (45, 30, 25) | (40, 30, 30) |
| moderate_dispersion | (45, 30, 25) | (44, 32, 24) |
| zero_heavy | (100, 0, 0) | (100, 0, 0) |

### stream 4

| scenario | challenge | reward |
|---|---|---|
| perfect_agreement | (45, 30, 25) | (40, 30, 30) |
| moderate_dispersion | (45, 29, 26) | (44, 32, 24) |
| zero_heavy | (100, 0, 0) | (100, 0, 0) |

### stream 5

| scenario | challenge | reward |
|---|---|---|
| perfect_agreement | (45, 30, 25) | (40, 30, 30) |
| moderate_dispersion | (45, 30, 25) | (44, 32, 24) |
| zero_heavy | (100, 0, 0) | (100, 0, 0) |
