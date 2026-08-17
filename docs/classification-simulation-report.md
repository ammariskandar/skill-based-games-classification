# SBGC-65 Classification Simulation Report

Generated: 2026-08-17T13:36:41.109845+00:00

Simulation configuration (scenario matrix): bootstrap=12, governance_draws=2; large-N bootstrap=4. Frozen production settings (B=10,000, S=20) are exercised by the dedicated BHPCM acceptance test.


## 1. Frozen N boundaries

| N | status | regime | m1 | m2 | m3 | elapsed_s |
|---|---|---|---|---|---|---|
| 0 | NO_SUBMISSIONS | unified | - | - | - | 0.0 |
| 1 | READY | provisional | READY | - | - | 0.0 |
| 2 | READY | provisional | READY | - | - | 0.0 |
| 5 | READY | provisional | READY | - | - | 0.0 |
| 6 | READY | provisional | READY | - | - | 0.0 |
| 8 | READY | provisional | READY | - | - | 0.0 |
| 9 | READY | provisional | READY | - | - | 0.0 |
| 10 | READY | provisional | READY | - | - | 0.0 |
| 15 | READY | provisional | READY | - | - | 0.0 |
| 18 | READY | provisional | READY | - | - | 0.0 |
| 19 | READY | provisional | READY | - | - | 0.0 |
| 20 | READY | unified | READY | READY | READY | 3.7 |
| 21 | READY | unified | READY | READY | READY | 3.8 |
| 25 | READY | unified | READY | READY | READY | 4.4 |
| 26 | READY | unified | READY | READY | READY | 4.5 |
| 50 | READY | unified | READY | READY | READY | 9.0 |
| 51 | READY | unified | READY | READY | READY | 9.0 |
| 100 | READY | unified | READY | READY | READY | 7.2 |
| 250 | READY | unified | READY | READY | READY | 18.8 |
| 400 | READY | unified | READY | READY | READY | 26.0 |
| 401 | READY | unified | READY | READY | READY | 26.0 |
| 500 | READY | unified | READY | READY | READY | 31.0 |
| 1000 | READY | unified | READY | READY | READY | 65.3 |
| 1001 | READY | unified | READY | READY | READY | 65.2 |

## 2. Required population scenarios

### 2.1 perfect_unanimous

- Description: All submissions identical.
- Input generation: seed=1
- Raw N: 50; roles: {'superuser': 1, 'community': 49}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 30, 25), M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(0, 0), M2=0, M3=0
- BHPCM: status=READY, unified=(45, 30, 25), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 54.46, 'resilience': 54.46}
- Invariant result: PASS

### 2.2 tight_unimodal

- Description: Tight unimodal agreement (spread 2).
- Input generation: seed=2
- Raw N: 50; roles: {'superuser': 1, 'community': 49}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(46, 31, 23), M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(0, 0), M2=7, M3=0
- BHPCM: status=READY, unified=(45, 31, 24), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 52.33, 'resilience': 52.33}
- Invariant result: PASS

### 2.3 moderate_dispersion

- Description: Moderate symmetric dispersion (spread 8).
- Input generation: seed=3
- Raw N: 50; roles: {'superuser': 1, 'community': 49}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(43, 33, 24), M2=(45, 29, 26), M3=(45, 29, 26)
- Rejections: M1A/M1B=(0, 0), M2=6, M3=0
- BHPCM: status=READY, unified=(44, 31, 25), conflict=Moderate conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 43.5, 'resilience': 44.24}
- Invariant result: PASS

### 2.4 one_high_tail

- Description: One extreme high-tail respondent.
- Input generation: seed=4
- Raw N: 50; roles: {'community': 49, 'superuser': 1}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(46, 28, 26), M2=(46, 30, 24), M3=(46, 30, 24)
- Rejections: M1A/M1B=(1, 1), M2=2, M3=1
- BHPCM: status=READY, unified=(46, 29, 25), conflict=Moderate conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 49.85, 'resilience': 49.87}
- Invariant result: PASS

### 2.5 one_low_tail

- Description: One extreme low-tail respondent.
- Input generation: seed=5
- Raw N: 50; roles: {'community': 49, 'superuser': 1}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(43, 31, 26), M2=(44, 31, 25), M3=(44, 31, 25)
- Rejections: M1A/M1B=(1, 1), M2=2, M3=1
- BHPCM: status=READY, unified=(44, 31, 25), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 53.08, 'resilience': 53.08}
- Invariant result: PASS

### 2.6 symmetric_0_100_extremes

- Description: Symmetric 0/100 extremes around a center.
- Input generation: seed=6
- Raw N: 43; roles: {'community': 42, 'superuser': 1}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 30, 25), M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(3, 3), M2=3, M3=3
- BHPCM: status=READY, unified=(45, 30, 25), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 51.25, 'resilience': 51.25}
- Invariant result: PASS

### 2.7 several_isolated_extremes

- Description: Several isolated extremes.
- Input generation: seed=7
- Raw N: 50; roles: {'superuser': 1, 'community': 49}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 28, 27), M2=(45, 30, 25), M3=(50, 27, 23)
- Rejections: M1A/M1B=(5, 5), M2=5, M3=0
- BHPCM: status=READY, unified=(47, 28, 25), conflict=Moderate conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 45.9, 'resilience': 46.37}
- Invariant result: PASS

### 2.8 bimodal_50_50

- Description: Bimodal 50/50 population.
- Input generation: seed=8
- Raw N: 51; roles: {'community': 50, 'superuser': 1}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 30, 25), M2=(32, 30, 38), M3=(33, 30, 37)
- Rejections: M1A/M1B=(0, 5), M2=6, M3=0
- BHPCM: status=READY, unified=(37, 30, 33), conflict=High conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 13.27, 'resilience': 17.53}
- Invariant result: PASS

### 2.9 majority_minority_75_25

- Description: 75/25 majority/minority.
- Input generation: seed=9
- Raw N: 50; roles: {'superuser': 1, 'community': 49}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(47, 30, 23), M2=(47, 29, 24), M3=(51, 27, 22)
- Rejections: M1A/M1B=(0, 12), M2=8, M3=0
- BHPCM: status=READY, unified=(48, 29, 23), conflict=Moderate conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 48.99, 'resilience': 49.11}
- Invariant result: PASS

### 2.10 dense_minority_cluster

- Description: Dense minority cluster.
- Input generation: seed=10
- Raw N: 48; roles: {'community': 47, 'superuser': 1}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 29, 26), M2=(46, 29, 25), M3=(40, 27, 33)
- Rejections: M1A/M1B=(0, 8), M2=11, M3=1
- BHPCM: status=READY, unified=(44, 28, 28), conflict=Moderate conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 48.25, 'resilience': 48.44}
- Invariant result: PASS

### 2.11 sparse_bridge

- Description: Sparse bridge observations between clusters.
- Input generation: seed=11
- Raw N: 46; roles: {'community': 45, 'superuser': 1}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 30, 25), M2=(57, 25, 18), M3=(57, 25, 18)
- Rejections: M1A/M1B=(0, 20), M2=6, M3=1
- BHPCM: status=READY, unified=(52, 27, 21), conflict=High conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 13.24, 'resilience': 17.14}
- Invariant result: PASS

### 2.12 uniform_spaced

- Description: Uniformly spaced profiles.
- Input generation: seed=12
- Raw N: 39; roles: {'superuser': 1, 'community': 38}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 30, 25), M2=(40, 30, 30), M3=(40, 30, 30)
- Rejections: M1A/M1B=(0, 0), M2=2, M3=2
- BHPCM: status=READY, unified=(42, 30, 28), conflict=Moderate conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 42.54, 'resilience': 43.22}
- Invariant result: PASS

### 2.13 many_duplicate_integer_profiles

- Description: Many duplicate integer profiles.
- Input generation: seed=13
- Raw N: 50; roles: {'community': 49, 'superuser': 1}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 30, 25), M2=(46, 29, 25), M3=(44, 29, 27)
- Rejections: M1A/M1B=(0, 10), M2=10, M3=0
- BHPCM: status=READY, unified=(44, 30, 26), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 53.78, 'resilience': 53.78}
- Invariant result: PASS

### 2.14 zero_heavy

- Description: Zero-heavy 100/0/0 compositions.
- Input generation: seed=14
- Raw N: 40; roles: {'superuser': 1, 'community': 39}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(100, 0, 0), M2=(75, 25, 0), M3=(75, 25, 0)
- Rejections: M1A/M1B=(0, 10), M2=0, M3=0
- BHPCM: status=READY, unified=(99, 1, 0), conflict=Very high conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 0.0, 'resilience': 4.67}
- Invariant result: PASS

### 2.15 balanced_33_33_34

- Description: Approximately balanced compositions.
- Input generation: seed=15
- Raw N: 50; roles: {'superuser': 1, 'community': 49}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(33, 33, 34), M2=(33, 33, 34), M3=(33, 33, 34)
- Rejections: M1A/M1B=(0, 0), M2=0, M3=0
- BHPCM: status=READY, unified=(33, 33, 34), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 54.46, 'resilience': 54.46}
- Invariant result: PASS

### 2.16 expert_population_agreement

- Description: Experts agree with the population.
- Input generation: seed=16
- Raw N: 50; roles: {'superuser': 1, 'moderator': 5, 'community': 44}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 30, 25), M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(0, 0), M2=7, M3=0
- BHPCM: status=READY, unified=(45, 30, 25), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 58.57, 'resilience': 58.57}
- Invariant result: PASS

### 2.17 moderate_expert_conflict

- Description: Moderate expert/population conflict.
- Input generation: seed=17
- Raw N: 50; roles: {'superuser': 1, 'moderator': 5, 'community': 44}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(55, 30, 15), M2=(45, 30, 25), M3=(46, 30, 24)
- Rejections: M1A/M1B=(0, 0), M2=7, M3=0
- BHPCM: status=READY, unified=(49, 30, 21), conflict=High conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 15.19, 'resilience': 19.17}
- Invariant result: PASS

### 2.18 severe_expert_conflict

- Description: Severe expert/population conflict.
- Input generation: seed=18
- Raw N: 50; roles: {'superuser': 1, 'moderator': 5, 'community': 44}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(88, 6, 6), M2=(45, 30, 25), M3=(50, 27, 23)
- Rejections: M1A/M1B=(6, 6), M2=8, M3=0
- BHPCM: status=READY, unified=(66, 18, 16), conflict=Very high conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 0.0, 'resilience': 5.71}
- Invariant result: PASS

### 2.19 unanimous_experts

- Description: Internally unanimous experts.
- Input generation: seed=19
- Raw N: 50; roles: {'superuser': 1, 'moderator': 2, 'community_leader': 3, 'community': 44}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(55, 30, 15), M2=(45, 30, 25), M3=(46, 30, 24)
- Rejections: M1A/M1B=(0, 0), M2=10, M3=0
- BHPCM: status=READY, unified=(49, 30, 21), conflict=High conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 14.58, 'resilience': 18.63}
- Invariant result: PASS

### 2.20 divided_experts

- Description: Internally highly divided experts.
- Input generation: seed=20
- Raw N: 47; roles: {'superuser': 2, 'moderator': 1, 'community': 44}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(47, 8, 45), M2=(46, 30, 24), M3=(46, 30, 24)
- Rejections: M1A/M1B=(2, 2), M2=2, M3=2
- BHPCM: status=READY, unified=(44, 21, 35), conflict=Very high conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 0.1, 'resilience': 5.49}
- Invariant result: PASS

### 2.21 no_authorities

- Description: No authoritative respondents.
- Input generation: seed=21
- Raw N: 50; roles: {'community': 50}
- Method statuses: M1=READY (anchor=COMMUNITY_FALLBACK), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 30, 25), M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(0, 0), M2=6, M3=0
- BHPCM: status=READY, unified=(45, 30, 25), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 52.88, 'resilience': 52.88}
- Invariant result: PASS

### 2.22 one_authority

- Description: Exactly one authoritative respondent.
- Input generation: seed=22
- Raw N: 50; roles: {'community': 49, 'superuser': 1}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 30, 25), M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(0, 0), M2=4, M3=1
- BHPCM: status=READY, unified=(45, 30, 25), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 54.4, 'resilience': 54.4}
- Invariant result: PASS

### 2.23 opposite_superusers

- Description: Multiple superusers giving opposite profiles.
- Input generation: seed=23
- Raw N: 50; roles: {'community': 48, 'superuser': 2}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(47, 6, 47), M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(2, 2), M2=3, M3=2
- BHPCM: status=READY, unified=(51, 20, 29), conflict=Very high conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 0.06, 'resilience': 5.76}
- Invariant result: PASS

### 2.24 all_community_below_50

- Description: All-Community below 50: Method 1 must not publish without an anchor.
- Input generation: seed=24
- Raw N: 30; roles: {'community': 30}
- Method statuses: M1=INSUFFICIENT_ANCHOR (anchor=NONE), M2=READY, M3=READY
- Integer Challenge profiles: M1=None, M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(None, None), M2=2, M3=0
- BHPCM: status=INSUFFICIENT_METHOD_1, unified=None, conflict=None, bootstrap(valid/invalid)=(None, None)
- Confidence: {}
- Invariant result: PASS

### 2.25 superuser_plus_large_community

- Description: One superuser plus a large Community population.
- Input generation: seed=25
- Raw N: 200; roles: {'community': 199, 'superuser': 1}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(45, 30, 25), M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(0, 0), M2=5, M3=1
- BHPCM: status=READY, unified=(45, 30, 25), conflict=Low conflict, bootstrap(valid/invalid)=(4, 0)
- Confidence: {'base': 83.56, 'resilience': 83.56}
- Invariant result: PASS

### 2.26 role_change_identical_scores

- Description: Role changes with identical score values (Methods 2/3 unaffected).
- Input generation: seed=26
- Raw N: 30; roles: {'community': 30}
- Method statuses: M1=INSUFFICIENT_ANCHOR (anchor=NONE), M2=READY, M3=READY
- Integer Challenge profiles: M1=None, M2=(46, 30, 24), M3=(46, 29, 25)
- Rejections: M1A/M1B=(None, None), M2=4, M3=0
- BHPCM: status=INSUFFICIENT_METHOD_1, unified=None, conflict=None, bootstrap(valid/invalid)=(None, None)
- Confidence: {}
- role-change invariance: M2 identical=True, M3 identical=True
- Invariant result: PASS

### 2.27 method23_agreement

- Description: Methods 2 and 3 near-identical (single tight cluster).
- Input generation: seed=27
- Raw N: 30; roles: {'superuser': 1, 'community': 29}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(44, 30, 26), M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(0, 0), M2=3, M3=0
- BHPCM: status=READY, unified=(45, 30, 25), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 42.92, 'resilience': 43.42}
- Invariant result: PASS

### 2.28 method23_disagreement

- Description: Methods 2 and 3 materially divergent (extreme + cluster).
- Input generation: seed=28
- Raw N: 50; roles: {'community': 49, 'superuser': 1}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(44, 29, 27), M2=(45, 30, 25), M3=(41, 27, 32)
- Rejections: M1A/M1B=(5, 5), M2=5, M3=0
- BHPCM: status=READY, unified=(44, 29, 27), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 53.5, 'resilience': 53.5}
- Invariant result: PASS

### 2.29 method1_divergent

- Description: Method 1 materially divergent from both population methods.
- Input generation: seed=29
- Raw N: 50; roles: {'superuser': 1, 'moderator': 4, 'community': 45}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(79, 15, 6), M2=(44, 31, 25), M3=(48, 29, 23)
- Rejections: M1A/M1B=(5, 5), M2=8, M3=0
- BHPCM: status=READY, unified=(60, 25, 15), conflict=Very high conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 0.0, 'resilience': 5.71}
- Invariant result: PASS

### 2.30 all_methods_similar

- Description: All three methods nearly identical.
- Input generation: seed=30
- Raw N: 30; roles: {'superuser': 1, 'community': 29}
- Method statuses: M1=READY (anchor=SUPERUSER), M2=READY, M3=READY
- Integer Challenge profiles: M1=(46, 30, 24), M2=(45, 30, 25), M3=(45, 30, 25)
- Rejections: M1A/M1B=(0, 0), M2=4, M3=0
- BHPCM: status=READY, unified=(45, 30, 25), conflict=Low conflict, bootstrap(valid/invalid)=(12, 0)
- Confidence: {'base': 43.81, 'resilience': 44.25}
- Invariant result: PASS


## 3. Mandatory 19-to-20 boundary study

| family | C19 (provisional) | C20 base | C20 resilience | delta20 | decay@50 |
|---|---|---|---|---|---|
| perfect agreement | 46.13 | 36.49 | 37.12 | 9.02 | 0.741 |
| modest disagreement | 40.27 | 35.44 | 36.12 | 4.12 | 0.741 |
| strong disagreement | 2.01 | 13.93 | 15.61 | 0.0 | 0.741 |
| no authorities | None | 35.22 | 35.91 | 0.0 | 0.741 |
| divided authorities | 28.89 | 33.3 | 34.08 | 0.0 | 0.741 |

## 4. Population-resilience pathological study

- N = 398 (population broadly coherent)
- Authoritative internal variance: 4.5014
- Base confidence: 0.0
- After resilience: 24.89 (capacity 24.89)
- Verifications:
  - base remains low: True
  - resilience is bounded: True
  - expert conflict remains visible in diagnostics: True
  - adjustment does not imply majority correctness: True

## 5. Invariants under random simulation

All invariant checks passed across 8 random populations.