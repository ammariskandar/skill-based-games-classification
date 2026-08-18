# statistical_model.md

## Canonical Statistical Model for Editorial Classification

**Master specification identifier:** `STATISTICAL_MODEL_V1.0.0`  
**Status:** Canonical, normative mathematical source of truth  
**Owner:** Ammar Iskandar  
**Scope:** Editorial Classification submissions, Methods 1/2/3, BHPCM unification, provisional and full Confidence Level, boundary calibration, calculation epochs, reproducibility, simulation acceptance, and published mathematical provenance  
**Supersedes as a single source of truth:** all prior standalone calculation-method, BHPCM, confidence, submission-calculation, SAM/MAD, and informal mathematical notes to the extent that they conflict with this file  
**Implementation independence:** This document specifies mathematics and required reproducibility behavior. It does not mandate a programming language, ORM structure, queue implementation, scheduler vendor, or user-interface framework.

---

# 0. Normative authority and reading rules

## 0.1 Normative language

The words **must**, **must not**, **shall**, **shall not**, **required**, **prohibited**, and **exactly** are normative.

The words **may**, **optional**, **diagnostic**, and **recommended** are non-normative unless the same sentence explicitly makes them mandatory.

No implementation agent, developer, framework default, statistical package default, or future maintainer may silently reinterpret a frozen equation, branch, threshold, role weight, seed, tie rule, sample boundary, transformation, correction layer, or output status.

Any mathematical behavior change requires a deliberate master calculation-version change.

## 0.2 Precedence inside this file

This file intentionally incorporates the complete mathematical content of three previously separate specifications.

Where older embedded wording conflicts with a later integration rule in this same master file, the precedence is:

1. **Part 0 / Master integration rules**;
2. **Part D / Final confidence and boundary rules**;
3. **Part B / BHPCM_V1 unification rules**;
4. **Part A / Method 1, 2, and 3 rules**;
5. **Part C / CONFIDENCE_BASE_V1 base equation**;
6. rationale, examples, diagnostics, and non-normative commentary.

This precedence exists only to reconcile historical source text that has now been consolidated. It is not permission to guess.

## 0.3 Canonical calculation components and versions

| Component | Identifier | Purpose |
|---|---|---|
| Submission/method domain | `METHODS_V2.0.0` | Method 1, Isolation Forest, LoOP, shared validation and reconciliation |
| Unified score | `BHPCM_V1` | Governed Bayesian/compositional synthesis of Methods 1, 2 and 3 |
| Base full-regime confidence | `CONFIDENCE_BASE_V1` | Statistical base confidence evidence for unified results |
| Low-confidence resilience | `CONFIDENCE_RESILIENCE_V1` | Bounded population support when base confidence is below 50 |
| Provisional small-N confidence | `PROVISIONAL_CONFIDENCE_V1` | Confidence when `1 <= N < 20` and Method 1 alone is publishable |
| N=20 boundary calibration | `BOUNDARY_CONTINUITY_V1` | Prevents an artificial negative confidence cliff at the provisional/full-model boundary |
| Final user-facing confidence | `CONFIDENCE_V2` | Published Confidence Level after applicable layers |
| Master integration | `STATISTICAL_MODEL_V1.0.0` | Complete governing specification |

A stored Final Classification must record enough version provenance to reconstruct all applicable components.

## 0.4 Two score regimes

### Provisional regime

For:

\[
1\le N<20,
\]

Methods 2 and 3 are intentionally unavailable.

If Method 1 is `READY`, the user-visible classification is the Method 1 result and the confidence status is `PROVISIONAL_READY`.

The ordinary UI may still label the number simply **Confidence Level**, but must communicate through a concise badge, tooltip, or equivalent:

> Provisional — limited submissions

If Method 1 is not ready because no required anchor exists, no provisional score may be invented.

### Unified regime

For:

\[
N\ge20,
\]

Methods 1, 2, and 3 may become simultaneously available.

A unified score exists only when `BHPCM_V1` is `READY`.

The ordinary headline score is the BHPCM unified result.

Methods 1, 2, and 3 remain separately stored and available for advanced diagnostics.

## 0.5 No objective-truth claim

Editorial classifications are subjective governed judgments.

No number in this specification is the probability that an objectively true Micro/Macro/Mystiko classification has been discovered.

Nevertheless, the product-facing phrase **Confidence Level** is deliberately retained because it communicates to ordinary users how reliable and stable the published governed score is given the evidence available.

A concise UI explanation may say:

> Confidence Level measures how reliable the displayed classification is given the number of submissions, their agreement, authoritative-role evidence, and the stability of the statistical synthesis.

The UI need not burden ordinary users with philosophical language about universal truth.

## 0.6 Canonical component ordering

Human-facing deterministic tie priority is:

```text
Micro > Macro > Mystiko
```

Mathematical source sections historically use both `(Micro, Mystiko, Macro)` and `(Micro, Macro, Mystiko)` notation. Implementations must map by semantic component name, never by blind positional assumption.

The canonical serialization/display order for new derived outputs is:

```text
Micro, Macro, Mystiko
```

for both Challenge and Reward.

## 0.7 Raw N

Unless an equation explicitly introduces another count:

\[
N
\]

means the number of valid submissions before any outlier rejection.

Invalid submissions are removed before N is established.

No retained, survivor, bootstrap, anchor, role, or post-rejection count may silently replace N.

## 0.8 Daily asynchronous visibility

Classification mathematics is not evaluated synchronously in response to a user submission.

A submission, edit, deletion, validation-state change, or corrected role snapshot at time \(T\) becomes eligible to affect the user-visible derived score at the next successful daily calculation epoch whose cutoff includes that change.

```text
submission at T
-> stored immediately
-> previous derived snapshot remains visible
-> next successful daily calculation epoch
-> new derived snapshot published atomically
```

This is intentional. The product is a games library, not a real-time statistical dashboard.

---

# Master architecture

```text
Validated Editorial Classification submissions
│
├─ N < 20
│   ├─ Method 1 only
│   ├─ PROVISIONAL_CONFIDENCE_V1
│   └─ provisional Final Classification
│
└─ N >= 20
    ├─ Method 1: expertise-sensitive / role-aware
    ├─ Method 2: global population robustness / Isolation Forest
    ├─ Method 3: local population robustness / LoOP
    │
    └─ BHPCM_V1
        ├─ Methods 2 + 3 nested as one population perspective
        ├─ Method 1 retained as expertise-sensitive perspective
        ├─ compositional ilr/Aitchison geometry
        ├─ stratified bootstrap uncertainty
        └─ unified continuous + reconciled score
            │
            ├─ CONFIDENCE_BASE_V1
            ├─ CONFIDENCE_RESILIENCE_V1
            └─ BOUNDARY_CONTINUITY_V1
                │
                └─ CONFIDENCE_V2
```

The three methods are never arithmetically averaged.

`BHPCM_V1` is the only permitted unified-score synthesis in this master version.

---

# Part A — Three Method Calculation Specification

**Status:** Canonical mathematical specification  
**Calculation specification version:** 2.0.0  
**Owner:** Ammar Iskandar  
**Scope:** Final Editorial Classification Methods 1, 2, and 3  
**Authority:** This document is the mathematical source of truth for future development  
**Supersedes:** `submission_calculation_logic.md`, `submission_calculation_logic_2.md`, and `submission_calculation_logic_3.md`  
**Implementation independence:** This specification defines mathematical behavior, not a required programming language, software package, storage design, or user-interface design.

---

## 0. Normative interpretation

The words **must**, **must not**, **shall**, **shall not**, **required**, and **prohibited** are normative.

The words **may**, **optional**, **diagnostic**, and **recommended** are non-normative unless a later sentence explicitly makes them mandatory.

If an implementation detail, third-party default, software convention, or previous source conflicts with this document, this document governs the mathematics.

No implementation may reinterpret, smooth, normalize, generalize, tune, or substitute any formula or threshold in this document without a deliberate calculation-version change.

---

# Part I — Mathematical domain

## 1. One Game, one population, three independent outputs

For each Game, let the set of valid Editorial Classification submissions be

\[
\mathcal X=\{X_1,X_2,\ldots,X_N\},
\]

where \(N\) is the number of valid submissions before any statistical rejection.

The system produces three independent final outputs:

1. **Method 1:** expert-sensitive, role-aware, anchor-based aggregation using two classical statistical filters;
2. **Method 2:** role-neutral Isolation Forest aggregation;
3. **Method 3:** role-neutral Local Outlier Probability aggregation.

The three method outputs are parallel interpretations of the same raw valid population:

\[
\mathcal X
\longrightarrow
\begin{cases}
\text{Method 1 result},\\
\text{Method 2 result},\\
\text{Method 3 result}.
\end{cases}
\]

The output of one Method 1/2/3 calculation must never be used as the raw input of another Method 1/2/3 calculation.

The three final method profiles must never be combined by a simple arithmetic mean or any implicit, ad hoc consensus rule.

This master specification now explicitly defines the permitted unification layer, **BHPCM_V1**, in Part B. BHPCM is not Method 1, 2, or 3; it is the separately specified governed synthesis that consumes the three continuous pre-reconciliation method outputs and their common bootstrap evidence.

---

## 2. Submission structure

Each submission \(X_i\) consists of two three-component profiles.

### 2.1 Challenge profile

\[
C_i=
\left(
C_{i,\mathrm{Micro}},
C_{i,\mathrm{Mystiko}},
C_{i,\mathrm{Macro}}
\right).
\]

### 2.2 Reward profile

\[
R_i=
\left(
R_{i,\mathrm{Micro}},
R_{i,\mathrm{Mystiko}},
R_{i,\mathrm{Macro}}
\right).
\]

### 2.3 Six-dimensional representation

For dimension-wise statistical analysis, write

\[
X_i=
\left(
C_{i,\mathrm{Micro}},
C_{i,\mathrm{Mystiko}},
C_{i,\mathrm{Macro}},
R_{i,\mathrm{Micro}},
R_{i,\mathrm{Mystiko}},
R_{i,\mathrm{Macro}}
\right).
\]

The six scalar dimensions are indexed by

\[
\mathcal D=
\{
C_\mu,C_y,C_a,R_\mu,R_y,R_a
\},
\]

where \(\mu\) denotes Micro, \(y\) denotes Mystiko, and \(a\) denotes Macro.

---

## 3. The normalized profile simplex

Define the 100-point three-part simplex

\[
\Delta_{100}^{2}
=
\left\{
(x_\mu,x_y,x_a)\in\mathbb R_{\ge 0}^{3}
:
x_\mu+x_y+x_a=100
\right\}.
\]

Every valid Challenge profile and every valid Reward profile belongs to this simplex:

\[
C_i\in\Delta_{100}^{2},
\qquad
R_i\in\Delta_{100}^{2}.
\]

Consequently,

\[
C_{i,\mathrm{Micro}}
+
C_{i,\mathrm{Mystiko}}
+
C_{i,\mathrm{Macro}}
=100,
\]

and

\[
R_{i,\mathrm{Micro}}
+
R_{i,\mathrm{Mystiko}}
+
R_{i,\mathrm{Macro}}
=100.
\]

Submitted component scores are integers in the closed interval

\[
[0,100]\cap\mathbb Z.
\]

A final raw average may be non-integer, but every READY final displayed profile must again consist of non-negative integers summing exactly to 100.

---

## 4. Valid population

Only submissions that have already passed canonical validation enter any calculation method.

A valid submission must have:

- all six scores present;
- all six scores finite;
- every score in the permitted score range;
- Challenge total exactly 100;
- Reward total exactly 100;
- one identifiable submitting user;
- one immutable role snapshot for Method 1;
- no duplicate submission by the same user for the same Game.

No method may impute a missing component.

No method may repair an invalid submitted profile.

Invalid submissions are excluded before \(N\) is measured.

---

## 5. Raw submission count

For every method,

\[
N=|\mathcal X|
\]

means the raw valid pre-rejection submission count.

All sample-size boundaries, population-influence values, minimum-sample rules, and anchor fallback rules use this original \(N\).

No method may replace \(N\) with:

- a retained count;
- a surviving count;
- a unified role-instance count;
- an anchor count;
- a post-rejection count.

---

## 6. Role snapshots for Method 1

Every submission has exactly one role snapshot from the following mutually exclusive hierarchy:

\[
\text{Superuser}
>
\text{Moderator}
>
\text{Community Leader}
>
\text{Community}.
\]

Superuser status takes precedence.

Moderator and Community Leader status are mutually exclusive.

Community is the default role.

The role snapshot relevant to a submission is the role at submission time. Later changes to a user's current role must not retroactively reclassify historical submissions unless a separate migration deliberately creates a new calculation history.

The fixed base role weights are

| Role | Symbol | Base weight |
|---|---:|---:|
| Superuser | \(w_S\) | \(1.00\) |
| Moderator | \(w_M\) | \(0.95\) |
| Community Leader | \(w_L\) | \(0.65\) |
| Community | \(w_C\) | \(0.20\) |

These weights are used only by Method 1 and only for non-anchor role influence.

Methods 2 and 3 ignore roles completely.

---

# Part II — Shared statistical and aggregation principles

## 7. Six marginal analyses and compositional dependence

All three methods perform outlier analysis independently on the six scalar dimensions.

For dimension \(d\in\mathcal D\), define

\[
\mathcal X_d=\{x_{1d},x_{2d},\ldots,x_{Nd}\}.
\]

Each method obtains up to six outlier flags for each submission.

This is a deliberate **marginal** analysis.

It is not a six-dimensional multivariate anomaly analysis.

Because the profiles are compositional,

\[
C_{i,\mathrm{Micro}}+
C_{i,\mathrm{Mystiko}}+
C_{i,\mathrm{Macro}}=100
\]

and

\[
R_{i,\mathrm{Micro}}+
R_{i,\mathrm{Mystiko}}+
R_{i,\mathrm{Macro}}=100,
\]

the three Challenge components are dependent, and the three Reward components are dependent.

Therefore, two flagged dimensions are not necessarily two statistically independent pieces of evidence. A single conceptual change in one profile can necessarily alter two or three components. This dependence is accepted as part of the product rule.

The methods answer questions about marginal rarity of component values. They do not claim to identify every unusual joint composition.

---

## 8. Universal whole-submission rejection rule

For a given statistical detector, let

\[
f_{id}\in\{0,1\}
\]

indicate whether submission \(i\) is flagged in dimension \(d\).

Define the flag count

\[
F_i=\sum_{d\in\mathcal D}f_{id}.
\]

The whole-submission decision is

\[
\operatorname{retain}(i)
=
\begin{cases}
1,&F_i\le 1,\\
0,&F_i\ge 2.
\end{cases}
\]

Equivalently:

```text
0 flagged dimensions -> retain the complete submission
1 flagged dimension  -> retain the complete submission
2-6 flagged dimensions -> reject the complete submission
```

No method may delete one component while retaining the other five.

No method may calculate a final Challenge profile from one set of users and a final Reward profile from a different set of users.

A surviving or rejected unit is always the complete six-score submission.

---

## 9. Single-pass rule

Every detector is single-pass.

For a given method or submethod:

\[
\text{raw population}
\rightarrow
\text{statistics/model}
\rightarrow
\text{six flags per submission}
\rightarrow
\text{whole-submission decision}
\rightarrow
\text{stop}.
\]

No method may:

1. detect outliers;
2. remove them;
3. recalculate the detector;
4. discover additional outliers;
5. repeat until convergence.

All flags are determined from the original valid population of size \(N\).

---

## 10. Arithmetic means preserve the simplex

Let \(P_1,\ldots,P_m\in\Delta_{100}^{2}\), and let non-negative weights \(v_1,\ldots,v_m\) satisfy

\[
\sum_{i=1}^{m}v_i>0.
\]

The weighted profile

\[
\bar P
=
\frac{\sum_{i=1}^{m}v_iP_i}
{\sum_{i=1}^{m}v_i}
\]

also belongs to \(\Delta_{100}^{2}\), because

\[
\sum_j\bar P_j
=
\frac{
\sum_i v_i\sum_jP_{ij}
}{
\sum_i v_i
}
=
\frac{
\sum_i v_i(100)
}{
\sum_i v_i
}
=100.
\]

This closure property is fundamental.

All valid final raw profiles must be obtained through operations that preserve the simplex.

Any raw final profile whose components do not total 100 is evidence of a mathematical or calculation defect.

---

# Part III — Exact integer reconciliation

## 11. Largest-remainder reconciliation

Independent component-wise half-up rounding is superseded.

Every READY raw profile

\[
P=(p_\mu,p_y,p_a)\in\Delta_{100}^{2}
\]

is converted to a non-negative integer profile summing exactly to 100 through the largest-remainder procedure.

### 11.1 Floors

Define

\[
b_j=\lfloor p_j\rfloor
\]

for \(j\in\{\mu,y,a\}\).

### 11.2 Remaining integer mass

Define

\[
r=100-\sum_j b_j.
\]

Because

\[
\sum_jp_j=100
\]

and there are three components,

\[
r\in\{0,1,2\}.
\]

A value outside this set is a calculation invariant failure.

### 11.3 Fractional remainders

Define

\[
\phi_j=p_j-b_j.
\]

### 11.4 Allocation

Add one point to each of the \(r\) components with the largest fractional remainder.

No component receives more than one added point because \(r\le2\).

### 11.5 Tie priority

If fractional remainders are tied, use the fixed priority

\[
\mathrm{Micro}
>
\mathrm{Macro}
>
\mathrm{Mystiko}.
\]

The same priority applies to Challenge and Reward.

### 11.6 Final integer profile

Let \(a_j\in\{0,1\}\) indicate whether component \(j\) receives a remainder point.

Then

\[
P^{\mathrm{int}}_j=b_j+a_j
\]

and

\[
\sum_jP^{\mathrm{int}}_j=100.
\]

### 11.7 Example

For

\[
P=(60.5,20.5,19.0),
\]

the floors are

\[
(60,20,19),
\]

so

\[
r=100-99=1.
\]

Micro and Mystiko both have remainder \(0.5\). Micro wins the tie priority:

\[
P^{\mathrm{int}}=(61,20,19).
\]

### 11.8 Optimality within floor/ceiling reconciliation

Among integer profiles obtained by assigning each component either its floor or its ceiling while preserving a total of 100, allocating the remaining units to the largest fractional remainders minimizes total rounding displacement.

An exchange argument establishes this: if a smaller remainder receives a point while a larger remainder does not, swapping the point reduces absolute rounding error.

### 11.9 Prohibited correction logic

The previous special cases for totals 97 through 103 are removed.

A conforming calculation must never produce a raw profile requiring an arbitrary multi-point repair.

---

# Part IV — Result statuses

## 12. Common statuses

Each method has an explicit status.

At minimum, the calculation domain must distinguish:

| Status | Meaning |
|---|---|
| `READY` | All six final integer scores exist and each profile totals 100 |
| `NO_SUBMISSIONS` | \(N=0\) |
| `INSUFFICIENT_ANCHOR` | Method 1 cannot form a required anchor |
| `INSUFFICIENT_SAMPLE_FOR_IFOREST` | Method 2 has fewer than its minimum required submissions |
| `INSUFFICIENT_SAMPLE_FOR_LOOP` | Method 3 has fewer than its minimum required submissions |
| `NO_SURVIVING_SUBMISSIONS` | A statistical method rejects every submission |
| `CALCULATION_ERROR` | A mathematical invariant is violated |

For any non-READY status, all six final score fields are null or N/A.

No non-ready result may use

```text
0 / 0 / 0
```

as a substitute for unavailable data.

---

# Part V — Method 1: role-aware anchored aggregation

## 13. Purpose of Method 1

Method 1 answers:

> What classification results when expert-role structure, a protected or reliability-adjusted anchor, population size, and two complementary classical outlier filters are combined under an exactly normalized aggregation model?

Method 1 is intentionally not role-neutral.

It is designed to remain meaningful when the population is sparse and to give expert or trusted-role information a controlled anchoring function.

Method 1 contains two independent internal detectors:

- **Method 1A:** mean and sample-standard-deviation detector;
- **Method 1B:** median and robust-\(S_n\)-scale detector.

The two internal detectors are not separate final classification methods. They are an ensemble inside Method 1.

---

## 14. Frozen Method 1 constants

| Symbol | Meaning | Value |
|---|---|---:|
| \(N_{1,\min}\) | Minimum \(N\) for Method 1A/1B rejection | \(9\) |
| \(\delta\) | Minimum practically meaningful scalar deviation | \(5\) points |
| \(k_A^{\mathrm{low}}\) | Method 1A SD multiplier for \(9\le N\le50\) | \(2.5\) |
| \(k_A^{\mathrm{high}}\) | Method 1A SD multiplier for \(N\ge51\) | \(3.0\) |
| \(k_B\) | Method 1B \(S_n\) multiplier | \(3.5\) |
| \(c_S\) | \(S_n\) consistency factor | \(1.1926\) |
| \(a_{\mathrm{both}}\) | High-\(N\) anchor evidence weight: retained by both | \(1.0\) |
| \(a_{\mathrm{one}}\) | High-\(N\) anchor evidence weight: retained by one | \(0.5\) |
| \(a_{\mathrm{neither}}\) | High-\(N\) anchor evidence weight: retained by neither | \(0.1\) |

The value \(\delta=5\) is a domain-scale floor, not a universal statistical constant.

It prevents tiny integer-score differences from being classified as practically extreme solely because a sample has zero or near-zero estimated dispersion.

---

## 15. Population influence coefficient

### 15.1 Definition

Method 1 uses a monotone population influence coefficient

\[
c(N)\in[0,1].
\]

It controls how far non-anchor roles may move the result away from the anchor.

It is not a confidence interval.

It is not a posterior probability.

It is not the probability that the final classification is correct.

The authoritative name is:

```text
population influence
```

If displayed as a percentage, display

\[
100c(N)\%.
\]

### 15.2 Piecewise function

\[
c(N)=
\begin{cases}
0,
&0\le N\le5,
\\[6pt]
0.10\left(\dfrac{N-5}{20}\right),
&6\le N\le25,
\\[10pt]
0.10+0.25\left(\dfrac{N-25}{25}\right),
&26\le N\le50,
\\[10pt]
0.35+0.50\left(\dfrac{N-50}{200}\right),
&51\le N\le250,
\\[10pt]
0.85,
&251\le N\le400,
\\[8pt]
0.85+0.15\left(\dfrac{N-400}{600}\right),
&401\le N\le1000,
\\[10pt]
1,
&N>1000.
\end{cases}
\]

### 15.3 Boundary values

| \(N\) | \(c(N)\) |
|---:|---:|
| 0 | 0 |
| 5 | 0 |
| 6 | 0.005 |
| 25 | 0.10 |
| 26 | 0.11 |
| 50 | 0.35 |
| 51 | 0.3525 |
| 250 | 0.85 |
| 251 | 0.85 |
| 400 | 0.85 |
| 401 | 0.85025 |
| 1000 | 1.00 |
| \(>1000\) | 1.00 |

### 15.4 Properties

The function is:

- non-negative;
- bounded above by one;
- non-decreasing in \(N\);
- continuous at the real-valued interval boundaries represented by the piecewise lines;
- free of downward influence jumps at \(N=51\);
- free of a large upward jump at \(N=401\).

The previous discontinuous confidence equations and the previous 51–400 half-dilution rule are superseded.

---

# Part VI — Method 1A: mean and sample SD

## 16. Method 1A centre

For each dimension \(d\in\mathcal D\), define the arithmetic mean

\[
\bar x_d
=
\frac{1}{N}
\sum_{i=1}^{N}x_{id}.
\]

---

## 17. Method 1A scale

For \(N\ge2\), define the sample standard deviation

\[
s_d
=
\sqrt{
\frac{
\sum_{i=1}^{N}
(x_{id}-\bar x_d)^2
}{
N-1
}
}.
\]

This uses Bessel's correction.

For \(N=1\), sample SD is undefined and may be reported diagnostically as null. Method 1A performs no rejection because \(N<9\).

For \(N=0\), no statistic is calculated.

---

## 18. Method 1A minimum sample behavior

For

\[
N<9,
\]

Method 1A flags no values.

This is a deliberate conservative rule.

It also agrees with a structural property of internally studentized distances: using the same sample to calculate the mean and sample SD, no observation can be strictly more than \(2.5\) sample SD from the mean for \(N\le8\).

---

## 19. Method 1A threshold

Define

\[
k_A(N)
=
\begin{cases}
2.5,&9\le N\le50,\\
3.0,&N\ge51.
\end{cases}
\]

Define the absolute threshold

\[
T_{A,d}
=
\max
\left(
k_A(N)s_d,
\delta
\right),
\]

where

\[
\delta=5.
\]

Submission \(i\) is flagged by Method 1A in dimension \(d\) exactly when

\[
|x_{id}-\bar x_d|
>
T_{A,d}.
\]

The inequality is strictly greater-than.

Therefore:

```text
distance exactly equal to the threshold -> not flagged
distance greater than the threshold     -> flagged
```

---

## 20. Method 1A zero-spread behavior

If

\[
s_d=0,
\]

then every value in the dimension is identical to the mean.

Consequently,

\[
|x_{id}-\bar x_d|=0
\]

for every submission, and no value is flagged.

No division by \(s_d\) is required.

---

## 21. Removal of the CV gate

Coefficient of variation is not used as an outlier gate.

The former quantity

\[
CV=\frac{s}{\bar x}
\]

may be retained as optional diagnostic metadata when \(\bar x>0\), but it has no normative role.

This removal is deliberate because component values are bounded percentages and the three categories are exchangeable parts of a composition. A deviation should not become easier or harder to test merely because a component's mean is numerically small or large.

---

## 22. Optional Method 1A dispersion diagnostic

A bounded sample-SD diagnostic may be defined as

\[
SDI_d
=
\min
\left(
1,
\frac{s_d}
{50\sqrt{N/(N-1)}}
\right)
\]

for \(N\ge2\).

Interpretation:

- \(SDI_d\) near 0 indicates concentration;
- larger \(SDI_d\) indicates broader global dispersion.

This diagnostic must not gate outlier checking.

---

# Part VII — Method 1B: median and robust \(S_n\) scale

## 23. Purpose of Method 1B

Method 1B provides a robust, median-centered detector that uses the full sample's pairwise distances.

It replaces the former Spread Around Median statistic.

The former SAM statistic is prohibited because it depends only on the minimum, median, and maximum and can report zero asymmetry when two equally distant extreme observations are present.

Method 1B measures robust scale, not endpoint asymmetry.

---

## 24. Median convention

Sort the values in dimension \(d\):

\[
x_{(1)d}\le x_{(2)d}\le\cdots\le x_{(N)d}.
\]

The sample median is

\[
M_d
=
\begin{cases}
x_{((N+1)/2)d},
&N\text{ odd},
\\[6pt]
\dfrac{
x_{(N/2)d}
+
x_{(N/2+1)d}
}{2},
&N\text{ even}.
\end{cases}
\]

The same median convention applies to every inner and outer median in the \(S_n\) definition.

---

## 25. Robust \(S_n\) scale

For each observation \(i\), define its median pairwise distance

\[
m_{id}
=
\operatorname{median}_{1\le j\le N}
|x_{id}-x_{jd}|.
\]

The term \(j=i\) is included, so one distance is zero.

Define

\[
S_{n,d}
=
1.1926
\operatorname{median}_{1\le i\le N}
m_{id}.
\]

No additional finite-sample correction factor is applied in calculation version 2.0.0.

The factor \(1.1926\) places the statistic on a scale approximately consistent with ordinary standard deviation under an ideal normal model.

The estimator has a high-breakdown robust construction and uses the full sample rather than only the range endpoints.

---

## 26. Method 1B minimum sample behavior

For

\[
N<9,
\]

Method 1B flags no values.

The median and \(S_n\) may still be reported diagnostically, but they do not cause rejection.

---

## 27. Method 1B threshold

Define

\[
T_{B,d}
=
\max
\left(
k_BS_{n,d},
\delta
\right),
\]

where

\[
k_B=3.5
\]

and

\[
\delta=5.
\]

Submission \(i\) is flagged by Method 1B in dimension \(d\) exactly when

\[
|x_{id}-M_d|
>
T_{B,d}.
\]

The inequality is strictly greater-than.

Therefore:

```text
distance exactly equal to the threshold -> not flagged
distance greater than the threshold     -> flagged
```

---

## 28. Method 1B zero-scale behavior

If

\[
S_{n,d}=0,
\]

then

\[
T_{B,d}=5.
\]

A non-median value is not automatically an outlier.

Instead:

\[
|x_{id}-M_d|\le5
\quad\Longrightarrow\quad
\text{not flagged},
\]

and

\[
|x_{id}-M_d|>5
\quad\Longrightarrow\quad
\text{flagged}.
\]

This rule is essential for discrete integer data with heavy duplication.

It prevents a one-point or similarly small difference from being treated as infinitely standardized merely because the estimated robust scale is zero.

---

## 29. Robust dispersion and central concentration diagnostics

The authoritative robust scale is \(S_{n,d}\).

For bounded presentation, define the Robust Dispersion Index

\[
RDI_d
=
\min
\left(
1,
\frac{S_{n,d}}{50}
\right).
\]

Define the complementary Central Concentration Index

\[
CCI_d=1-RDI_d.
\]

Interpretation:

- \(RDI_d=0\), equivalently \(CCI_d=1\), indicates complete or near-complete concentration under the robust scale;
- increasing \(RDI_d\) indicates weakening central concentration;
- \(RDI_d=1\) is a capped indication of exceptionally broad dispersion.

Neither \(RDI_d\) nor \(CCI_d\) is a hypothesis-test probability.

Neither acts as a trigger or gate.

Method 1B always applies its threshold when \(N\ge9\).

---

## 30. Optional MAD diagnostic

The unscaled median absolute deviation may be reported:

\[
MAD_d
=
\operatorname{median}_{i}
|x_{id}-M_d|.
\]

A normal-consistent diagnostic scale may be reported as

\[
MAD_{\sigma,d}
=
1.4826MAD_d.
\]

MAD is not the normative Method 1B rejection scale.

---

# Part VIII — Combining Method 1A and Method 1B

## 31. Independent detector decisions

Method 1A and Method 1B each begin with the original population \(\mathcal X\).

For submission \(i\), let

\[
r_{Ai}
=
\begin{cases}
1,&\text{retained by Method 1A},\\
0,&\text{rejected by Method 1A},
\end{cases}
\]

and

\[
r_{Bi}
=
\begin{cases}
1,&\text{retained by Method 1B},\\
0,&\text{rejected by Method 1B}.
\end{cases}
\]

---

## 32. Method-agreement weight

Define

\[
u_i
=
\frac{r_{Ai}+r_{Bi}}{2}.
\]

Therefore:

| Method 1A | Method 1B | \(u_i\) |
|---|---|---:|
| retained | retained | \(1.0\) |
| retained | rejected | \(0.5\) |
| rejected | retained | \(0.5\) |
| rejected | rejected | \(0.0\) |

This is the explicit mathematical form of the former multiset-union behavior.

It means:

- agreement on retention gives full influence;
- disagreement gives half influence;
- agreement on rejection gives zero ordinary-role influence.

No physical duplication of observations is mathematically necessary.

---

## 33. Role-specific unified average

Let \(\mathcal I_g\) be the set of non-anchor submissions belonging to role \(g\).

If

\[
U_g=\sum_{i\in\mathcal I_g}u_i>0,
\]

the role's unified six-score average is

\[
\bar X_g
=
\frac{
\sum_{i\in\mathcal I_g}
u_iX_i
}{
U_g
}.
\]

Challenge and Reward profile notation is

\[
\bar C_g
=
\frac{
\sum_{i\in\mathcal I_g}
u_iC_i
}{
U_g
},
\]

\[
\bar R_g
=
\frac{
\sum_{i\in\mathcal I_g}
u_iR_i
}{
U_g
}.
\]

By simplex closure,

\[
\bar C_g\in\Delta_{100}^{2}
\]

and

\[
\bar R_g\in\Delta_{100}^{2}.
\]

If

\[
U_g=0,
\]

that role is absent from ordinary role aggregation.

---

# Part IX — Method 1 anchor selection

## 34. Anchor qualification uses raw role counts

Anchor qualification is determined from raw valid role snapshots before Method 1A or Method 1B rejection.

Filtering must not change which hierarchy level initially qualifies.

The hierarchy is evaluated in order.

---

## 35. Anchor hierarchy

### 35.1 Superuser anchor

If at least one Superuser submission exists, every Superuser submission belongs to the selected anchor group.

### 35.2 Moderator substitute anchor

If no Superuser exists and at least two Moderator submissions exist, every Moderator submission belongs to the selected anchor group.

### 35.3 Community Leader substitute anchor

If no Superuser exists, fewer than two Moderators exist, and at least five Community Leader submissions exist, every Community Leader submission belongs to the selected anchor group.

### 35.4 Mixed substitute anchor

If:

- no Superuser exists;
- exactly one Moderator submission exists;
- fewer than five Community Leader submissions exist;
- at least three Community Leader submissions exist;

then the selected anchor group consists of:

- the one Moderator submission; and
- every available Community Leader submission.

Because the preceding Community Leader rule captures five or more Community Leaders, the mixed group contains either three or four Community Leaders.

No arbitrary choice of three Community Leaders is permitted.

The mixed anchor is an equal-submission anchor average. Role weights are not used within the anchor.

### 35.5 No privileged anchor

If none of the preceding conditions holds, no privileged anchor exists.

Fallback behavior then depends on \(N\).

---

## 36. Anchor and ordinary-group separation

A submission used in the anchor group must not also appear in an ordinary role group.

The anchor is exactly one aggregation group, regardless of how many users form it.

Examples:

- if Superusers form the anchor, there is no ordinary Superuser group;
- if Moderators form the anchor, there is no ordinary Moderator group;
- if Community Leaders form the anchor, there is no ordinary Community Leader group;
- if a mixed Moderator/Community-Leader anchor is selected, those anchor submissions are excluded from both ordinary role groups.

This prevents double-counting.

---

## 37. Community fallback

If no privileged anchor exists:

### 37.1 \(N<50\)

The result is

```text
INSUFFICIENT_ANCHOR
```

with null scores.

### 37.2 \(50\le N\le400\)

All Community submissions form the fallback anchor.

The effective population influence is capped at

\[
c_{\mathrm{eff}}
=
\min(c(N),0.30).
\]

### 37.3 \(N\ge401\)

All Community submissions form the fallback anchor.

The effective population influence is capped at

\[
c_{\mathrm{eff}}
=
\min(c(N),0.95).
\]

If no Community submission exists in a logically possible fallback case, the result is `INSUFFICIENT_ANCHOR`.

For a privileged anchor,

\[
c_{\mathrm{eff}}=c(N).
\]

---

# Part X — Method 1 anchor profile

## 38. Protected anchor for \(N\le400\)

For

\[
N\le400,
\]

the selected anchor group is protected.

If its submission set is \(\mathcal A\) with size \(m\ge1\), define its Challenge and Reward profiles as ordinary equal arithmetic means:

\[
A_C
=
\frac{1}{m}
\sum_{i\in\mathcal A}C_i,
\]

\[
A_R
=
\frac{1}{m}
\sum_{i\in\mathcal A}R_i.
\]

Method 1A and Method 1B may still calculate diagnostic flags for anchor submissions, but those flags do not alter protected anchor membership or protected anchor averaging.

---

## 39. Reliability-adjusted anchor for \(N\ge401\)

For

\[
N\ge401,
\]

each anchor submission receives an evidence weight based on the two Method 1 detectors:

\[
a_i
=
\begin{cases}
1.0,
&r_{Ai}=1,\ r_{Bi}=1,
\\
0.5,
&r_{Ai}+r_{Bi}=1,
\\
0.1,
&r_{Ai}=0,\ r_{Bi}=0.
\end{cases}
\]

Every anchor submission remains represented because

\[
a_i\ge0.1.
\]

Define

\[
A_C
=
\frac{
\sum_{i\in\mathcal A}a_iC_i
}{
\sum_{i\in\mathcal A}a_i
},
\]

\[
A_R
=
\frac{
\sum_{i\in\mathcal A}a_iR_i
}{
\sum_{i\in\mathcal A}a_i
}.
\]

Define aggregate anchor reliability

\[
\rho_A
=
\frac{1}{m}
\sum_{i\in\mathcal A}a_i.
\]

Then

\[
0.1\le\rho_A\le1.
\]

Interpretation:

| Anchor evidence pattern | Evidence weight |
|---|---:|
| retained by both filters | \(1.0\) |
| retained by one filter | \(0.5\) |
| rejected by both filters | \(0.1\) |

This resolves mixed-anchor cases without discarding the anchor.

---

# Part XI — Method 1 normalized role/anchor aggregation

## 40. Separate evaluation of Challenge and Reward

The same aggregation equations are applied separately to:

- the three-dimensional Challenge profile;
- the three-dimensional Reward profile.

The formulas below use a generic profile symbol \(P\), where

\[
P\in\Delta_{100}^{2}.
\]

---

## 41. Participating ordinary role groups

Let

\[
\mathcal G
\]

be the set of non-anchor roles whose unified agreement weight is positive.

Let

\[
m=|\mathcal G|.
\]

Define the total group count

\[
G=1+m.
\]

The one additional group is the anchor group.

\(G\) counts groups, not users.

---

## 42. Role departure coefficient

For each participating role \(g\in\mathcal G\), define

\[
q_g=w_gc_{\mathrm{eff}}.
\]

Because

\[
0\le w_g\le1
\]

and

\[
0\le c_{\mathrm{eff}}\le1,
\]

it follows that

\[
0\le q_g\le1.
\]

The quantity \(q_g\) controls how far that role's group block departs from the anchor.

---

## 43. Anchor-blended role block

For a generic profile type, let

- \(A\) be the selected anchor profile;
- \(P_g\) be role \(g\)'s unified profile.

Define the role block

\[
B_g
=
q_gP_g+(1-q_g)A.
\]

This is a convex combination.

Therefore,

\[
B_g\in\Delta_{100}^{2}.
\]

At \(q_g=0\),

\[
B_g=A.
\]

At \(q_g=1\),

\[
B_g=P_g.
\]

---

## 44. Ordinary normalized final profile

Before high-\(N\) anchor-reliability redistribution, define

\[
F_0
=
\frac{
A+\sum_{g\in\mathcal G}B_g
}{
G
}.
\]

Expanded:

\[
F_0
=
\frac{
A+
\sum_{g\in\mathcal G}
\left[
q_gP_g+(1-q_g)A
\right]
}{
G
}.
\]

Equivalent coefficient form:

\[
F_0
=
\beta_AA
+
\sum_{g\in\mathcal G}\beta_gP_g,
\]

where

\[
\beta_g=\frac{q_g}{G}
\]

and

\[
\beta_A
=
1-\sum_{g\in\mathcal G}\frac{q_g}{G}.
\]

---

## 45. Normalization proof

Because each \(B_g\) totals 100 and \(A\) totals 100,

\[
\sum_j(F_0)_j
=
\frac{
100+m(100)
}{
m+1
}
=100.
\]

Equivalently,

\[
\beta_A+\sum_g\beta_g=1.
\]

Moreover,

\[
\sum_gq_g\le m,
\]

so

\[
\beta_A
=
1-\frac{\sum_gq_g}{m+1}
\ge
1-\frac{m}{m+1}
=
\frac{1}{m+1}
>0.
\]

All coefficients are non-negative.

Therefore,

\[
F_0\in\Delta_{100}^{2}.
\]

The raw Method 1 profile cannot total 150, 200, or any value other than 100 under this formula.

---

## 46. Interpretation of group influence

Each ordinary role first receives one conceptual group block.

That block is itself anchored:

\[
B_g=q_gP_g+(1-q_g)A.
\]

The final result is the equal average of:

- one pure anchor block; and
- one anchor-blended block for each participating ordinary role.

Role weights do not assign direct user counts.

They determine the degree of departure from the anchor inside each role block.

---

# Part XII — High-\(N\) anchor reliability redistribution

## 47. Applicability

For

\[
N\le400,
\]

the final raw profile is

\[
F=F_0.
\]

For

\[
N\ge401,
\]

anchor reliability \(\rho_A\) modifies the profile coefficients as follows.

---

## 48. Ordinary coefficients

Define

\[
\beta_A
=
1-\sum_g\frac{q_g}{G}
\]

and

\[
\beta_g=\frac{q_g}{G}.
\]

Let

\[
Q=\sum_gq_g.
\]

---

## 49. Reduced anchor coefficient

Define

\[
\widetilde\beta_A
=
\rho_A\beta_A.
\]

The removed anchor mass is

\[
L
=
(1-\rho_A)\beta_A.
\]

---

## 50. Redistribution to ordinary roles

If

\[
Q>0,
\]

define

\[
p_g=\frac{q_g}{Q}.
\]

Then

\[
\sum_gp_g=1.
\]

Define adjusted role coefficients

\[
\widetilde\beta_g
=
\beta_g+Lp_g.
\]

The high-\(N\) final profile is

\[
F
=
\widetilde\beta_AA
+
\sum_g
\widetilde\beta_gP_g.
\]

---

## 51. High-\(N\) normalization proof

\[
\widetilde\beta_A
+
\sum_g\widetilde\beta_g
=
\rho_A\beta_A
+
\sum_g\beta_g
+
L\sum_gp_g.
\]

Since

\[
L=(1-\rho_A)\beta_A
\]

and

\[
\sum_gp_g=1,
\]

\[
\widetilde\beta_A
+
\sum_g\widetilde\beta_g
=
\rho_A\beta_A
+
\sum_g\beta_g
+
(1-\rho_A)\beta_A
=
\beta_A+\sum_g\beta_g
=1.
\]

All coefficients are non-negative.

Therefore,

\[
F\in\Delta_{100}^{2}.
\]

---

## 52. Anchor-only high-\(N\) case

If there is no participating ordinary role, or if

\[
Q=0,
\]

there is nowhere to redistribute removed anchor mass.

In that case,

\[
F=A.
\]

The result remains READY if the anchor exists.

Diagnostic metadata may describe the result as `ANCHOR_ONLY`.

`ANCHOR_ONLY` is not a replacement for the formal calculation status.

---

## 53. Two levels of high-\(N\) anchor dilution

At \(N\ge401\), outlying anchor evidence affects Method 1 in two distinct ways:

1. **Within-anchor weighting:** anchor submissions receive weights \(1.0\), \(0.5\), or \(0.1\) when constructing \(A\).
2. **Between-group weighting:** aggregate reliability \(\rho_A\) reduces the anchor's ordinary coefficient, and the removed mass is transferred to non-anchor roles.

This is intentional.

An outlying anchor remains present but does not retain the same influence as a fully supported anchor.

---

# Part XIII — Method 1 boundary behavior

## 54. \(N=0\)

No statistics are calculated.

The result is

```text
NO_SUBMISSIONS
```

with null scores.

---

## 55. \(1\le N\le5\)

\[
c(N)=0.
\]

If an anchor qualifies, then for every ordinary role

\[
q_g=w_gc(N)=0,
\]

so

\[
B_g=A.
\]

Consequently,

\[
F=A.
\]

Thus the low-\(N\) result is exactly the selected anchor average.

If no anchor qualifies, the result is

```text
INSUFFICIENT_ANCHOR
```

with null scores.

---

## 56. \(6\le N<9\)

Population influence is positive according to \(c(N)\), but Method 1A and Method 1B perform no rejection.

Every submission receives

\[
u_i=1.
\]

The role and anchor aggregation remains valid.

---

## 57. \(N=9\)

Both Method 1 detectors become active.

This boundary must be explicitly tested.

---

## 58. \(N=50\)

If no privileged anchor exists, Community fallback becomes available.

The fallback influence cap is

\[
0.30.
\]

---

## 59. \(N=401\)

The anchor changes from protected equal averaging to evidence-weighted averaging and coefficient reliability redistribution.

The population influence function itself remains nearly continuous:

\[
c(400)=0.85,
\]

\[
c(401)=0.85025.
\]

---

# Part XIV — Method 1 worked examples

## 60. Two-group normalized example

Suppose one dimension has:

\[
A=30,
\]

\[
P_L=50,
\]

\[
w_L=0.65,
\]

\[
c_{\mathrm{eff}}=0.10.
\]

Then

\[
q_L=0.65(0.10)=0.065.
\]

There is one ordinary role, so

\[
G=2.
\]

The role block is

\[
B_L
=
0.065(50)+0.935(30)
=
31.3.
\]

The final dimension is

\[
F
=
\frac{30+31.3}{2}
=
30.65.
\]

The corresponding three-component vector calculation remains exactly normalized to 100.

---

## 61. Detector-agreement example

Suppose one role has four submissions with detector outcomes:

| Submission | Method 1A | Method 1B | \(u_i\) |
|---|---|---|---:|
| 1 | retain | retain | 1.0 |
| 2 | retain | reject | 0.5 |
| 3 | reject | retain | 0.5 |
| 4 | reject | reject | 0.0 |

The role average is

\[
\bar X_g
=
\frac{
1.0X_1+0.5X_2+0.5X_3
}{
2.0
}.
\]

Submission 4 contributes no ordinary-role influence.

---

## 62. High-\(N\) mixed-anchor example

Suppose an anchor contains two submissions.

One survives both filters and one survives neither.

Then

\[
a_1=1.0,
\qquad
a_2=0.1,
\]

and

\[
\rho_A
=
\frac{1.0+0.1}{2}
=
0.55.
\]

The anchor profile is

\[
A
=
\frac{
1.0X_1+0.1X_2
}{
1.1
}.
\]

The anchor still contains both submissions, but the unsupported one has one-tenth the within-anchor influence of the fully supported one.

The ordinary anchor coefficient is then multiplied by \(0.55\), and the removed coefficient mass is transferred to non-anchor roles proportionally to \(q_g\).

---

## 63. Symmetric-extreme robustness example

Consider a scalar sample whose central mass is near 50 and whose two extremes are 0 and 100.

A range-asymmetry statistic can equal zero because the two endpoints are symmetric around the median.

Method 1B does not turn itself off.

Its \(S_n\) statistic uses pairwise distances across the full sample, after which each extreme is evaluated through

\[
|x_i-M|>\max(3.5S_n,5).
\]

Symmetric extremes therefore remain eligible for detection.

---

# Part XV — Method 2: Isolation Forest

## 64. Purpose of Method 2

Method 2 answers:

> What classification results when every submission is treated equally and global isolation-based anomaly detection determines which complete submissions are excluded?

Method 2 has:

- no role hierarchy;
- no role weight;
- no anchor;
- no population influence coefficient;
- no protected user;
- no Method 1 input;
- no Method 3 input.

Every surviving submission has equal weight one.

---

## 65. Frozen Method 2 constants

| Symbol | Meaning | Value |
|---|---|---:|
| \(N_{IF,\min}\) | Minimum sample size | \(20\) |
| \(t\) | Number of isolation trees per dimension | \(512\) |
| \(\psi\) | Tree subsample size | \(\min(256,N)\) |
| \(\ell\) | Tree height limit | \(\lceil\log_2\psi\rceil\) |
| \(\tau_{IF}\) | Scalar anomaly threshold | \(0.60\) |
| \(s_{\mathrm{seed}}\) | Calculation-version randomization seed | \(42\) |

The threshold comparison is strictly greater-than:

\[
s_{id}>\tau_{IF}.
\]

A score exactly equal to \(0.60\) is not flagged.

---

## 66. Six independent forests

For each dimension \(d\in\mathcal D\), Method 2 constructs one independent one-dimensional Isolation Forest from

\[
\mathcal X_d
=
\{x_{1d},\ldots,x_{Nd}\}.
\]

No six-dimensional forest is permitted.

No scaling across dimensions is performed.

The scalar distance between dimensions is irrelevant because dimensions are not jointly modeled.

---

## 67. Isolation-tree subsampling

For each of the \(t=512\) trees:

1. select a subset of \(\psi=\min(256,N)\) observations without replacement;
2. construct one one-dimensional isolation tree;
3. evaluate every original observation through the tree, whether or not it was selected in that tree's subsample.

The randomization schedule must be deterministic for a fixed calculation version, fixed seed, fixed dimension, and fixed input population.

The mathematical result is defined relative to that frozen randomization schedule.

Changing the randomization schedule changes the calculation version.

---

## 68. Isolation-tree construction

Let a tree node contain a multiset \(Z\) at depth \(e\).

The node is terminal if any of the following holds:

1. \(e\ge\ell\);
2. \(|Z|\le1\);
3. every value in \(Z\) is equal.

Otherwise, define

\[
z_{\min}=\min Z,
\qquad
z_{\max}=\max Z.
\]

Select a split point

\[
p\sim\operatorname{Uniform}(z_{\min},z_{\max}).
\]

Partition:

\[
Z_{\mathrm{left}}
=
\{z\in Z:z<p\},
\]

\[
Z_{\mathrm{right}}
=
\{z\in Z:z\ge p\}.
\]

Recursively construct the left and right children at depth \(e+1\).

Because \(p\) lies strictly between distinct minimum and maximum values, both children are non-empty.

---

## 69. Expected unsuccessful-search adjustment

Define the harmonic number

\[
H_m=\sum_{j=1}^{m}\frac1j.
\]

Define

\[
c(n)
=
\begin{cases}
0,&n\le1,\\[4pt]
2H_{n-1}-\dfrac{2(n-1)}{n},&n\ge2.
\end{cases}
\]

If observation \(x\) reaches a terminal node at depth \(e\) containing \(n_e\) training observations, its path length for that tree is

\[
h(x)=e+c(n_e).
\]

The \(c(n_e)\) term accounts for unresolved points in a terminal node.

---

## 70. Forest anomaly score

For observation \(x_i\) in dimension \(d\), let

\[
\bar h_{id}
=
\frac1t
\sum_{b=1}^{t}
h_{bid}
\]

be its mean path length across the forest.

Define the Isolation Forest anomaly score

\[
s_{id}
=
2^{-\bar h_{id}/c(\psi)}.
\]

Because \(N\ge20\) whenever Method 2 runs,

\[
\psi\ge20
\]

and

\[
c(\psi)>0.
\]

Interpretation:

- shorter average path length gives a score closer to 1;
- a score near 0.5 indicates an observation whose path length resembles the expected reference length;
- smaller scores indicate deeper isolation.

---

## 71. Method 2 scalar outlier rule

Submission \(i\) is flagged in dimension \(d\) exactly when

\[
s_{id}>0.60.
\]

The rule does not select a fixed percentage of observations.

No contamination quota or forced rejection rate exists.

The number of flags may be zero, one, many, or all observations, depending on the data.

---

## 72. Method 2 constant dimension

If every value in a dimension is identical, every tree terminates at its root for that dimension.

The canonical anomaly score is

\[
s_{id}=0.5
\]

for every submission.

No value is flagged.

This branch may be evaluated directly because there is no anomaly information in a constant dimension.

---

## 73. Method 2 minimum sample behavior

If

\[
N=0,
\]

the status is `NO_SUBMISSIONS`.

If

\[
1\le N<20,
\]

the status is

```text
INSUFFICIENT_SAMPLE_FOR_IFOREST
```

and all final scores are null.

Method 2 does not fall back to an unfiltered arithmetic mean.

Method 2 does not import Method 1 anchor behavior.

---

## 74. Method 2 whole-submission rejection

After six scalar Isolation Forest flags are obtained, apply the universal 2-of-6 rule.

Let

\[
S_{IF}
=
\{i:F_i\le1\}
\]

be the surviving index set.

Let

\[
n_{IF}=|S_{IF}|.
\]

If

\[
n_{IF}=0,
\]

the status is

```text
NO_SURVIVING_SUBMISSIONS
```

with null scores.

---

## 75. Method 2 final raw means

For \(n_{IF}>0\), define

\[
C_{IF}
=
\frac1{n_{IF}}
\sum_{i\in S_{IF}}C_i,
\]

\[
R_{IF}
=
\frac1{n_{IF}}
\sum_{i\in S_{IF}}R_i.
\]

Then

\[
C_{IF}\in\Delta_{100}^{2},
\qquad
R_{IF}\in\Delta_{100}^{2}.
\]

Apply largest-remainder reconciliation separately to \(C_{IF}\) and \(R_{IF}\).

The final status is `READY`.

---

## 76. Method 2 determinism

Method 2 is randomized in construction but deterministic as a product calculation.

For identical:

- Game;
- valid submission multiset;
- canonical submission ordering;
- calculation version;
- forest parameters;
- randomization seed and schedule;

the result must be identical.

Row order or retrieval order must not be allowed to act as an unrecorded mathematical input.

---

## 77. Method 2 edge interpretation

Isolation Forest is a global isolation model.

It may:

- identify an isolated tail value;
- fail to identify a sufficiently large anomalous cluster because of masking;
- alter sensitivity as the subsample size changes;
- score duplicate values together;
- disagree with a local-density method.

These are characteristics of the method, not automatic calculation defects.

The method's purpose is comparative diversity, not forced agreement with Methods 1 or 3.

---

# Part XVI — Method 3: Local Outlier Probabilities

## 78. Purpose of Method 3

Method 3 answers:

> What classification results when every submission is treated equally and local density relative to neighboring values determines which complete submissions are excluded?

Method 3 has:

- no role hierarchy;
- no role weight;
- no anchor;
- no population influence coefficient;
- no protected user;
- no Method 1 input;
- no Method 2 input;
- no preliminary clustering.

Every surviving submission has equal weight one.

---

## 79. Frozen Method 3 constants

| Symbol | Meaning | Value |
|---|---|---:|
| \(N_{L,\min}\) | Minimum sample size | \(20\) |
| \(k\) | Base nearest-neighbor count | \(10\) |
| \(\lambda\) | Probabilistic-distance extent | \(3\) |
| \(\tau_L\) | Binary LoOP threshold | \(0.75\) |

The threshold comparison is strictly greater-than:

\[
LoOP_{id}>0.75.
\]

A score exactly equal to \(0.75\) is not flagged.

---

## 80. Six independent local analyses

For each dimension \(d\in\mathcal D\), Method 3 operates on

\[
\mathcal X_d
=
\{x_{1d},\ldots,x_{Nd}\}.
\]

No six-dimensional LoOP analysis is permitted.

No cross-dimension standardization is performed.

The one-dimensional distance is

\[
d(x,y)=|x-y|.
\]

---

## 81. Tie-inclusive \(k\)-neighborhood

For observation \(i\), calculate distances to all other observations:

\[
d_{ij}=|x_{id}-x_{jd}|,
\qquad
j\ne i.
\]

Sort these \(N-1\) distances.

Let

\[
r_{i,k}
\]

be the \(k\)-th smallest distance.

Define the tie-inclusive neighborhood

\[
\mathcal N_i
=
\{j\ne i:d_{ij}\le r_{i,k}\}.
\]

Therefore,

\[
|\mathcal N_i|\ge k.
\]

All observations tied at the \(k\)-th distance are included.

This avoids arbitrary neighbor selection among equal integer values.

Because Method 3 requires \(N\ge20\) and \(k=10\),

\[
k<N.
\]

---

## 82. Local standard distance

For each observation \(i\), define

\[
\sigma_i
=
\sqrt{
\frac{
\sum_{j\in\mathcal N_i}
d_{ij}^{2}
}{
|\mathcal N_i|
}
}.
\]

This is a root-mean-square distance to the local neighborhood.

---

## 83. Probabilistic distance

Define

\[
pdist_i
=
\lambda\sigma_i,
\]

with

\[
\lambda=3.
\]

The parameter \(\lambda=3\) is a standard-deviation extent parameter.

It is not the probability value \(0.997\).

---

## 84. Neighbor reference distance

Define the neighborhood mean probabilistic distance

\[
\overline{pdist}_i
=
\frac{
\sum_{j\in\mathcal N_i}pdist_j
}{
|\mathcal N_i|
}.
\]

---

## 85. Probabilistic Local Outlier Factor

For regular non-degenerate cases with

\[
\overline{pdist}_i>0,
\]

define

\[
PLOF_i
=
\frac{
pdist_i
}{
\overline{pdist}_i
}
-1.
\]

Interpretation:

- \(PLOF_i>0\): observation \(i\) has greater local spread than its neighbors;
- \(PLOF_i=0\): local spread matches the neighborhood reference;
- \(PLOF_i<0\): observation \(i\) lies in a locally denser region than its comparison neighbors.

---

## 86. LoOP normalization factor

Let \(\mathcal F\) be the set of observations whose \(PLOF_i\) is finite under the degenerate-case rules below.

If \(\mathcal F\ne\varnothing\), define

\[
nPLOF
=
\lambda
\sqrt{
\frac{
\sum_{i\in\mathcal F}PLOF_i^2
}{
|\mathcal F|
}
}.
\]

---

## 87. Local Outlier Probability

For a finite \(PLOF_i\) and

\[
nPLOF>0,
\]

define

\[
LoOP_i
=
\max
\left[
0,
\operatorname{erf}
\left(
\frac{
PLOF_i
}{
nPLOF\sqrt2
}
\right)
\right],
\]

where

\[
\operatorname{erf}(z)
=
\frac{2}{\sqrt\pi}
\int_0^z e^{-t^2}\,dt.
\]

Then

\[
0\le LoOP_i<1
\]

for finite arguments, with values approaching 1 as normalized positive outlier strength increases.

The score is a normalized probability-like outlier measure.

It must not be interpreted as a posterior probability that a user is wrong or malicious.

---

# Part XVII — Method 3 degenerate-density rules

## 88. Entire dimension constant

If every value in the dimension is identical, define

\[
LoOP_i=0
\]

for all observations.

No value is flagged.

No neighborhood-density distinction exists.

---

## 89. Zero numerator and zero denominator

If

\[
pdist_i=0
\]

and

\[
\overline{pdist}_i=0,
\]

define

\[
PLOF_i=0.
\]

This represents a zero-spread point whose comparison neighborhood also has zero spread.

---

## 90. Positive numerator and zero denominator

If

\[
pdist_i>0
\]

and

\[
\overline{pdist}_i=0,
\]

observation \(i\) is maximally separated from a locally zero-spread reference set.

Define directly:

\[
LoOP_i=1.
\]

This observation is excluded from the finite-\(PLOF\) set \(\mathcal F\).

---

## 91. Zero normalization factor

If all finite \(PLOF\) values are zero, then

\[
nPLOF=0.
\]

For every finite case, define

\[
LoOP_i=0.
\]

Any observation already assigned \(LoOP_i=1\) under the positive-numerator/zero-denominator rule remains 1.

---

## 92. Non-finite values outside defined branches

If any undefined, infinite, or non-real quantity remains after applying the explicit degenerate-density rules, the Method 3 status is

```text
CALCULATION_ERROR
```

No non-finite score may silently become zero.

---

# Part XVIII — Method 3 rejection and final average

## 93. Method 3 scalar outlier rule

Submission \(i\) is flagged in dimension \(d\) exactly when

\[
LoOP_{id}>0.75.
\]

The rule does not force a fixed proportion of outliers.

---

## 94. Method 3 minimum sample behavior

If

\[
N=0,
\]

the status is `NO_SUBMISSIONS`.

If

\[
1\le N<20,
\]

the status is

```text
INSUFFICIENT_SAMPLE_FOR_LOOP
```

with null scores.

Method 3 does not reduce \(k\) silently.

Method 3 does not fall back to Method 1, Method 2, or an unfiltered mean.

---

## 95. Method 3 whole-submission rejection

After all six probabilities are converted to flags, apply the universal 2-of-6 rule.

Let

\[
S_L
=
\{i:F_i\le1\}
\]

be the surviving set.

Let

\[
n_L=|S_L|.
\]

If

\[
n_L=0,
\]

the result is

```text
NO_SURVIVING_SUBMISSIONS
```

with null scores.

---

## 96. Method 3 final raw means

For \(n_L>0\), define

\[
C_L
=
\frac1{n_L}
\sum_{i\in S_L}C_i,
\]

\[
R_L
=
\frac1{n_L}
\sum_{i\in S_L}R_i.
\]

Then

\[
C_L\in\Delta_{100}^{2},
\qquad
R_L\in\Delta_{100}^{2}.
\]

Apply largest-remainder reconciliation separately.

The final status is `READY`.

---

## 97. Method 3 determinism

LoOP is deterministic under the frozen mathematical rules.

Identical valid populations must produce identical neighborhoods, probabilities, rejections, and final profiles.

Tie-inclusive neighborhoods are mandatory to prevent arbitrary dependence on row ordering among equal values.

---

## 98. Method 3 edge interpretation

LoOP is a local-density method.

It may:

- retain a point that is globally far away but locally supported by a dense minority cluster;
- reject a point in a sparse local region even when its absolute value is not globally extreme;
- be sensitive to the neighborhood parameter \(k\);
- assign zero probability throughout a uniform or locally homogeneous population;
- disagree substantially with Isolation Forest.

These are legitimate differences in method philosophy.

---

# Part XIX — Shared final-output invariants

## 99. READY invariants

For every READY result from every method:

\[
C_{\mathrm{Micro}}
+
C_{\mathrm{Mystiko}}
+
C_{\mathrm{Macro}}
=100,
\]

\[
R_{\mathrm{Micro}}
+
R_{\mathrm{Mystiko}}
+
R_{\mathrm{Macro}}
=100.
\]

Every final component is an integer in

\[
[0,100].
\]

All raw pre-reconciliation values are finite and non-negative.

---

## 100. No partial availability

A method may not return three Challenge values while Reward is unavailable, or vice versa.

A READY method has all six values.

A non-ready method has six null values.

---

## 101. Method independence in presentation

A Game may validly have:

- Method 1 READY while Methods 2 and 3 are insufficient-sample;
- Method 1 insufficient-anchor while Method 2 or Method 3 is READY;
- three READY methods with materially different profiles;
- one statistical method with no survivors while another remains READY.

No disagreement is itself a calculation error.

---

# Part XX — Required mathematical provenance

## 102. Common provenance

Every method result must be reproducible from mathematical provenance that identifies at least:

- Game;
- calculation method;
- calculation specification version;
- raw valid submission count \(N\);
- canonical input population identity or hash;
- calculation timestamp;
- status;
- raw final profiles when READY;
- reconciled integer profiles when READY;
- surviving and rejected counts where applicable.

---

## 103. Method 1 provenance

Method 1 additionally requires:

- base and effective population influence;
- raw role counts;
- selected anchor type;
- anchor membership count;
- Method 1A retained/rejected counts;
- Method 1B retained/rejected counts;
- detector-agreement weight totals by role;
- participating ordinary roles;
- \(q_g\) for each participating role;
- \(G\);
- anchor reliability \(\rho_A\) when \(N\ge401\);
- final anchor and role coefficients;
- calculation status.

Per-dimension diagnostic metadata may include:

- mean;
- sample SD;
- median;
- \(S_n\);
- MAD;
- SDI;
- RDI;
- CCI;
- scalar flag counts.

---

## 104. Method 2 provenance

Method 2 additionally requires:

- tree count \(t\);
- subsample size \(\psi\);
- height limit \(\ell\);
- anomaly threshold \(\tau_{IF}\);
- deterministic randomization version and seed;
- per-dimension scalar flag counts;
- whole-submission surviving count;
- whole-submission rejected count.

---

## 105. Method 3 provenance

Method 3 additionally requires:

- \(k\);
- \(\lambda\);
- threshold \(\tau_L\);
- tie-inclusive-neighborhood rule identifier;
- per-dimension scalar flag counts;
- whole-submission surviving count;
- whole-submission rejected count;
- count of zero/zero density branches;
- count of maximal positive/zero density branches.

---

# Part XXI — Calculation errors

## 106. General invariant failures

The status is `CALCULATION_ERROR` if any of the following occurs after valid input has entered a method:

- a required denominator is zero outside a defined special case;
- a raw READY component is negative;
- a raw READY component is non-finite;
- a raw READY profile does not sum mathematically to 100;
- largest-remainder residual \(r\notin\{0,1,2\}\);
- an integer READY profile does not total 100;
- an integer READY component is negative;
- a required coefficient is negative;
- final aggregation coefficients do not sum to one;
- deterministic recalculation with identical provenance changes the result;
- an undefined statistical branch is silently coerced to a number.

A calculation error is not a valid classification outcome.

---

# Part XXII — Explicitly prohibited transformations

## 107. Prohibited across all methods

The following are prohibited:

- replacing raw \(N\) with retained count;
- iterative outlier removal;
- partial component removal;
- hidden imputation;
- hidden normalization of invalid source submissions;
- banker's rounding;
- arbitrary 97–103 repair rules;
- arithmetic averaging of the three final methods instead of the explicitly specified BHPCM unification layer;
- changing thresholds to force an expected rejection count;
- using current user role instead of the role snapshot for historical Method 1 submissions;
- allowing manual editing of final derived classifications.

---

## 108. Prohibited in Method 1

Method 1 must not:

- use the former SAM statistic;
- use CV as an outlier gate;
- use the former non-normalized group/anchor equations;
- count the anchor once per ordinary group;
- include anchor submissions again in ordinary role groups;
- discard all influence of a high-\(N\) anchor submission rejected by both detectors;
- recalculate Method 1A or Method 1B after rejection;
- treat agreement-weight duplication as an unacknowledged set union.

---

## 109. Prohibited in Method 2

Method 2 must not:

- use role weights;
- protect Superusers;
- use a six-dimensional forest;
- force a contamination percentage;
- use Method 1 population influence;
- use Method 3 probabilities;
- retrain after exclusions;
- silently change tree count, subsample size, threshold, or randomization schedule within one calculation version.

---

## 110. Prohibited in Method 3

Method 3 must not:

- use role weights;
- protect Superusers;
- use a six-dimensional LoOP analysis;
- add clustering;
- reduce \(k\) silently;
- use `extent = 0.997` as if it were the parameter \(\lambda=3\);
- choose arbitrary members among tied \(k\)-nearest neighbors;
- import Method 1 or Method 2 exclusions;
- recompute neighborhoods after exclusions.

---

# Part XXIII — Boundary and regression test matrix

## 111. Shared input boundaries

Test at least:

```text
N = 0
N = 1
N = 5
N = 6
N = 8
N = 9
N = 19
N = 20
N = 25
N = 26
N = 50
N = 51
N = 250
N = 251
N = 400
N = 401
N = 999
N = 1000
N = 1001
```

Test:

- all-zero component in otherwise valid profiles;
- all-100 component;
- many duplicate submissions;
- invalid source total;
- missing score;
- duplicate user submission;
- non-finite source value.

Invalid source cases must fail before the methods receive them.

---

## 112. Method 1 population-influence boundaries

Verify exactly:

```text
c(5)    = 0
c(6)    = 0.005
c(25)   = 0.10
c(26)   = 0.11
c(50)   = 0.35
c(51)   = 0.3525
c(250)  = 0.85
c(251)  = 0.85
c(400)  = 0.85
c(401)  = 0.85025
c(1000) = 1
c(1001) = 1
```

Verify monotonicity for every integer \(N\) over a broad range.

---

## 113. Method 1A boundaries

Test:

```text
N < 9 -> no flags
N = 9 -> active
N = 50 -> multiplier 2.5
N = 51 -> multiplier 3.0
sample SD = 0
threshold governed by 5-point floor
threshold governed by SD term
distance exactly threshold -> retained
distance greater than threshold -> flagged
one high extreme
one low extreme
symmetric high and low extremes
many duplicates
```

---

## 114. Method 1B boundaries

Test:

```text
N < 9 -> no flags
N = 9 -> active
Sn = 0
Sn > 0
threshold governed by 5-point floor
threshold governed by 3.5 Sn
distance exactly threshold -> retained
distance greater than threshold -> flagged
symmetric extremes
one-sided extreme
50/50 bimodal population
75/25 secondary population
many equal median values
even-N median
odd-N median
```

---

## 115. Whole-submission boundaries

For every detector:

```text
0 flags -> retain
1 flag  -> retain
2 flags -> reject
6 flags -> reject
```

Test two flags within one profile.

Test one Challenge flag plus one Reward flag.

---

## 116. Method 1 anchor boundaries

Test:

```text
at least one Superuser
no Superuser and exactly two Moderators
no Superuser, one Moderator, exactly five Community Leaders
one Moderator plus exactly three Community Leaders
one Moderator plus exactly four Community Leaders
one Moderator plus five Community Leaders -> CL anchor, not mixed
no privileged anchor and N = 49
no privileged anchor and N = 50
no privileged anchor and N = 400
no privileged anchor and N = 401
anchor-only result
anchor plus every possible ordinary role combination
```

---

## 117. High-\(N\) anchor evidence boundaries

Test:

```text
all anchor submissions retained by both -> rho = 1
all retained by exactly one -> rho = 0.5
all rejected by both -> rho = 0.1
mixed 1.0 / 0.5 / 0.1 evidence
Q = 0
one ordinary role
multiple ordinary roles
coefficient sum exactly 1
all coefficients non-negative
final profile sum exactly 100
```

---

## 118. Largest-remainder boundaries

Test:

```text
all components integer
fractional remainders sum to 1
fractional remainders sum to 2
all three remainders tied
Micro/Macro tie
Macro/Mystiko tie
one component equal to 0
one component equal to 100
raw example (60.5, 20.5, 19.0)
raw example (33.333..., 33.333..., 33.333...)
residual outside {0,1,2} -> calculation error
```

Tie priority must always be:

```text
Micro > Macro > Mystiko
```

---

## 119. Isolation Forest boundaries

Test:

```text
N = 19 -> insufficient sample
N = 20 -> active
N = 256
N = 257 -> subsample remains 256
constant dimension
two-valued dimension with duplicates
one isolated high value
one isolated low value
dense secondary cluster
score exactly 0.60 -> retained
score greater than 0.60 -> flagged
identical input in different row order
repeated calculation with same randomization provenance
different calculation seed requires different version
all submissions rejected
```

---

## 120. LoOP boundaries

Test:

```text
N = 19 -> insufficient sample
N = 20 -> active
constant dimension
exactly k equal nearest neighbors
more than k neighbors tied at kth distance
pdist = 0 and mean neighbor pdist = 0
pdist > 0 and mean neighbor pdist = 0
nPLOF = 0
negative PLOF
positive PLOF
LoOP exactly 0.75 -> retained
LoOP greater than 0.75 -> flagged
dense minority cluster
sparse bridge point
uniformly spaced values
all submissions rejected
```

---

# Part XXIV — Comparative interpretation

## 121. Method 1 interpretation

Method 1 is a domain-prior model.

It assumes:

- trusted roles contain useful prior information;
- an anchor is valuable, especially when the population is sparse;
- global mean-based and robust median-based filters provide complementary evidence;
- disagreement between filters should reduce, but not necessarily erase, ordinary role influence;
- at high \(N\), statistically unsupported anchor submissions should remain represented but be diluted.

Method 1 should be expected to remain closer to the anchor than the purely statistical methods.

---

## 122. Method 2 interpretation

Method 2 is a global isolation model.

It asks whether individual scalar values are unusually easy to isolate through repeated random partitions.

It is not a density probability model.

It is not role-aware.

It is capable of detecting globally isolated values even when the mean and median filters behave differently.

---

## 123. Method 3 interpretation

Method 3 is a local-density comparison model.

It asks whether an observation's local probabilistic distance is large relative to the local probabilistic distances of its neighbors.

It may preserve a globally distant but internally dense subgroup.

It may detect local sparsity not emphasized by a global method.

---

## 124. Meaning of disagreement

Disagreement among methods may reveal:

- expert/population tension;
- a coherent minority playstyle;
- globally isolated observations;
- locally sparse observations;
- heavy ties;
- multi-modal submission behavior;
- sensitivity to marginal rather than joint composition.

A disagreement is analytically useful.

It must not automatically be repaired or averaged away.

---

# Part XXV — Mathematical limitations and non-claims

## 125. No ground-truth guarantee

None of the methods proves that a surviving submission is correct.

None proves that a rejected submission is wrong.

Outlier status means statistical atypicality under the specified detector, not deception, incompetence, bad faith, or invalidity.

---

## 126. Marginal rather than compositional geometry

The detectors analyze six scalar margins.

They do not use a dedicated geometry for compositions.

The methods may therefore:

- flag two components produced by one redistribution of profile mass;
- miss an unusual joint combination of individually common values;
- treat a coherent alternative composition as a minority pattern.

This is a deliberate limitation of calculation version 2.0.0.

A future compositional method would be a new method or calculation version, not a silent modification.

---

## 127. Single-centre limitation of Method 1A and Method 1B

Method 1A has one global mean per dimension.

Method 1B has one global median per dimension.

A strongly multi-modal population may not be well represented by either single centre.

Method 3 exists partly to provide a local-density comparison that can behave differently in multi-modal data.

---

## 128. Parameter values are product mathematics

The following are product-owned mathematical parameters rather than universal scientific truths:

- five-point practical deviation floor;
- Method 1A multipliers;
- Method 1B multiplier;
- minimum sample sizes;
- population-influence schedule;
- Isolation Forest tree count and threshold;
- LoOP neighborhood size and threshold;
- high-\(N\) anchor evidence weights.

Changing any one of them requires:

1. a new calculation specification version;
2. explicit documentation;
3. regression fixtures;
4. reproducibility provenance.

---

# Part XXVI — Compact formula authority

## 129. Method 1A

For \(N\ge9\):

\[
\bar x
=
\frac1N\sum_ix_i,
\]

\[
s
=
\sqrt{
\frac{\sum_i(x_i-\bar x)^2}{N-1}
},
\]

\[
T_A
=
\max(k_A(N)s,5),
\]

\[
k_A(N)
=
\begin{cases}
2.5,&9\le N\le50,\\
3.0,&N\ge51,
\end{cases}
\]

\[
\text{flag}
\iff
|x_i-\bar x|>T_A.
\]

---

## 130. Method 1B

For \(N\ge9\):

\[
M=\operatorname{median}(x_i),
\]

\[
S_n
=
1.1926
\operatorname{median}_i
\left[
\operatorname{median}_j
|x_i-x_j|
\right],
\]

\[
T_B
=
\max(3.5S_n,5),
\]

\[
\text{flag}
\iff
|x_i-M|>T_B.
\]

---

## 131. Method 1 detector agreement

\[
u_i=\frac{r_{Ai}+r_{Bi}}2.
\]

For role \(g\):

\[
P_g
=
\frac{
\sum_{i\in g}u_iP_i
}{
\sum_{i\in g}u_i
}.
\]

---

## 132. Method 1 ordinary aggregation

\[
q_g=w_gc_{\mathrm{eff}},
\]

\[
B_g=q_gP_g+(1-q_g)A,
\]

\[
F_0
=
\frac{
A+\sum_gB_g
}{
1+|\mathcal G|
}.
\]

---

## 133. Method 1 high-\(N\) anchor adjustment

\[
a_i\in\{1.0,0.5,0.1\},
\]

\[
A
=
\frac{\sum_i a_iP_i}{\sum_i a_i},
\]

\[
\rho_A=\frac1m\sum_i a_i,
\]

\[
\beta_g=\frac{q_g}{G},
\]

\[
\beta_A=1-\sum_g\beta_g,
\]

\[
L=(1-\rho_A)\beta_A,
\]

\[
\widetilde\beta_A=\rho_A\beta_A,
\]

\[
\widetilde\beta_g
=
\beta_g
+
L\frac{q_g}{\sum_hq_h},
\]

\[
F
=
\widetilde\beta_AA
+
\sum_g\widetilde\beta_gP_g.
\]

---

## 134. Isolation Forest

\[
c(n)
=
2H_{n-1}
-
\frac{2(n-1)}n
\qquad(n\ge2),
\]

\[
s(x)
=
2^{-\bar h(x)/c(\psi)},
\]

\[
\text{flag}
\iff
s(x)>0.60.
\]

---

## 135. LoOP

\[
\sigma_i
=
\sqrt{
\frac1{|\mathcal N_i|}
\sum_{j\in\mathcal N_i}
d_{ij}^2
},
\]

\[
pdist_i=\lambda\sigma_i,
\]

\[
PLOF_i
=
\frac{
pdist_i
}{
|\mathcal N_i|^{-1}
\sum_{j\in\mathcal N_i}pdist_j
}
-1,
\]

\[
nPLOF
=
\lambda
\sqrt{
\frac1{|\mathcal F|}
\sum_{i\in\mathcal F}PLOF_i^2
},
\]

\[
LoOP_i
=
\max
\left[
0,
\operatorname{erf}
\left(
\frac{PLOF_i}{nPLOF\sqrt2}
\right)
\right],
\]

\[
\text{flag}
\iff
LoOP_i>0.75.
\]

Defined zero-density branches take precedence over the ordinary ratio formulas.

---

## 136. Whole-submission decision

For every detector:

\[
F_i=\sum_{d\in\mathcal D}f_{id},
\]

\[
\operatorname{retain}(i)
=
\mathbf 1[F_i\le1].
\]

---

## 137. Largest remainder

\[
b_j=\lfloor p_j\rfloor,
\]

\[
r=100-\sum_jb_j,
\]

then add one to the \(r\) largest fractional remainders using

\[
\mathrm{Micro}
>
\mathrm{Macro}
>
\mathrm{Mystiko}
\]

for ties.

---

# Part XXVII — Frozen checklist

## 138. Frozen Method 1 rules

- Raw \(N\) is measured before rejection.
- Population influence is the monotone piecewise function in this document.
- Method 1A uses mean and sample SD.
- Method 1A has no CV gate.
- Method 1A begins rejection at \(N=9\).
- Method 1A uses \(2.5s\) through \(N=50\) and \(3s\) from \(N=51\).
- Method 1A and Method 1B use a five-point practical floor.
- Method 1B uses median and \(S_n\).
- SAM is removed.
- Method 1B uses threshold \(3.5S_n\), subject to the floor.
- Both internal detectors are single-pass.
- Two or more scalar flags reject the complete submission for that detector.
- Detector agreement weights are \(1.0\), \(0.5\), and \(0.0\).
- Role averages are calculated within role.
- Anchor qualification uses raw role counts.
- Anchor submissions do not also appear in ordinary role groups.
- Anchor hierarchy is Superuser, qualifying Moderator, qualifying Community Leader, qualifying mixed group, then Community fallback when permitted.
- The protected anchor is a raw equal average for \(N\le400\).
- The high-\(N\) anchor uses evidence weights \(1.0\), \(0.5\), and \(0.1\).
- The final formula is convex and exactly normalized.
- High-\(N\) lost anchor mass is redistributed proportionally to \(q_g\).
- No 51–400 half-dilution rule remains.
- No non-normalized anchor amplification remains.

---

## 139. Frozen Method 2 rules

- Every user is equal.
- Six independent one-dimensional Isolation Forests are used.
- Minimum sample size is 20.
- Each forest has 512 trees.
- Tree subsample size is \(\min(256,N)\).
- Height limit is \(\lceil\log_2\psi\rceil\).
- Forest anomaly score is the normalized expected-path score.
- A scalar value is flagged only when its score is strictly greater than 0.60.
- No fixed rejection percentage exists.
- The process is single-pass.
- The whole-submission threshold is two flags.
- The final raw profile is the arithmetic mean of survivors.
- The final integer profile uses largest remainder.

---

## 140. Frozen Method 3 rules

- Every user is equal.
- Six independent one-dimensional LoOP analyses are used.
- Minimum sample size is 20.
- \(k=10\).
- All neighbors tied at the \(k\)-th distance are included.
- Distance is absolute scalar distance.
- \(\lambda=3\).
- No clustering is used.
- Degenerate zero-density cases follow the explicit branches in this document.
- A scalar value is flagged only when LoOP is strictly greater than 0.75.
- The process is single-pass.
- The whole-submission threshold is two flags.
- The final raw profile is the arithmetic mean of survivors.
- The final integer profile uses largest remainder.

---

# Part XXVIII — Scientific references

## 141. Robust \(S_n\) scale

Peter J. Rousseeuw and Christophe Croux, “Alternatives to the Median Absolute Deviation,” *Journal of the American Statistical Association*, volume 88, number 424, pages 1273–1283, 1993.

The present specification uses the explicit asymptotic form

\[
S_n
=
1.1926
\operatorname{median}_i
\operatorname{median}_j
|x_i-x_j|
\]

without an additional finite-sample correction.

---

## 142. Isolation Forest

Fei Tony Liu, Kai Ming Ting, and Zhi-Hua Zhou, “Isolation Forest,” *Proceedings of the 2008 IEEE International Conference on Data Mining*, pages 413–422, 2008.

DOI:

```text
10.1109/ICDM.2008.17
```

---

## 143. Local Outlier Probabilities

Hans-Peter Kriegel, Peer Kröger, Erich Schubert, and Arthur Zimek, “LoOP: Local Outlier Probabilities,” *Proceedings of the 18th ACM Conference on Information and Knowledge Management*, pages 1649–1652, 2009.

DOI:

```text
10.1145/1645953.1646195
```

---

# Part XXIX — Authority statement

## 144. Mathematical source of truth

This document defines the complete normative mathematical behavior of the three Final Editorial Classification methods.

Any future change to:

- input semantics;
- role weights;
- population influence;
- outlier centre or scale;
- detector thresholds;
- minimum sample sizes;
- anchor hierarchy;
- anchor evidence weights;
- group aggregation;
- Isolation Forest construction;
- LoOP neighborhoods or probability mapping;
- whole-submission rejection;
- integer reconciliation;
- result statuses;

requires a new calculation specification version.

Final classifications are derived, read-only mathematical outputs.

They must be reproducible from valid submissions and the frozen calculation-version parameters.

No manual final-score override is part of these methods.


---

# Appendix A — Mathematical rationale and analytical notes

This appendix explains the reasoning behind the frozen rules. It is interpretive and educational, but it does not override the normative formulas above.

## A.1 Why Method 1A begins rejection at \(N=9\)

Let one observation have deviation

\[
d=x_i-\bar x.
\]

The remaining \(N-1\) deviations sum to \(-d\). By the Cauchy–Schwarz inequality, the sum of their squared deviations is at least

\[
\frac{d^2}{N-1}.
\]

Therefore the total sum of squared deviations satisfies

\[
\sum_{j=1}^{N}(x_j-\bar x)^2
\ge
d^2+\frac{d^2}{N-1}
=
d^2\frac{N}{N-1}.
\]

Because

\[
s^2
=
\frac{
\sum_j(x_j-\bar x)^2
}{
N-1
},
\]

we obtain

\[
s^2
\ge
d^2\frac{N}{(N-1)^2}.
\]

Thus

\[
\frac{|d|}{s}
\le
\frac{N-1}{\sqrt N}.
\]

For \(N=8\),

\[
\frac{N-1}{\sqrt N}
=
\frac7{\sqrt8}
\approx2.4749,
\]

so no observation can be strictly more than \(2.5\) sample SD from the sample mean.

For \(N=9\),

\[
\frac8{3}
\approx2.6667,
\]

so a \(2.5s\) exceedance becomes mathematically possible.

The minimum \(N=9\) rule makes this structural boundary explicit.

---

## A.2 Why CV is not an outlier gate

The coefficient of variation is

\[
CV=\frac{s}{\bar x}.
\]

It is useful in domains where standard deviation is naturally proportional to a positive ratio-scale mean.

The editorial components do not have that interpretation.

A component with mean 10 and SD 5 has

\[
CV=0.5,
\]

while a component with mean 50 and the same SD has

\[
CV=0.1.
\]

The same absolute disagreement would therefore trigger different detector behavior solely because of the component's location in the 0–100 composition.

The mean may also be zero. In this domain a zero mean implies all valid non-negative values are zero, but the ratio itself remains unnecessary.

Removing the CV gate makes Method 1A depend on deviation and spread directly.

---

## A.3 Why a practical deviation floor is required

Suppose almost every value equals 50 and one value equals 51.

A robust or classical scale estimate may be zero or extremely small.

Without a floor, the one-point difference can produce an arbitrarily large standardized residual.

Statistical rarity and practical materiality are not identical.

The floor

\[
\delta=5
\]

requires a deviation to exceed five percentage points before zero or near-zero estimated spread can cause a flag.

Because the inequality is strict, a deviation of exactly five points is retained.

The floor applies symmetrically to high and low deviations.

---

## A.4 Why SAM is removed

The former statistic can be written as

\[
SAM
=
\frac{
|(\max-M)-(M-\min)|
}{
(\max-M)+(M-\min)
}.
\]

When \(\max>\min\), this simplifies to

\[
SAM
=
\frac{
|\max+\min-2M|
}{
\max-\min
}.
\]

It measures endpoint asymmetry around the median.

It does not measure how observations are distributed between the endpoints.

For example, if

\[
\min=0,\qquad M=50,\qquad\max=100,
\]

then

\[
SAM=0
\]

even when 0 and 100 are isolated extreme values.

A second extreme on the opposite side can therefore disable the detector.

The \(S_n\) scale avoids this failure because it is built from median pairwise distances across the full sample.

---

## A.5 Why \(S_n\) is used instead of raw MAD

The raw median absolute deviation is

\[
MAD=\operatorname{median}|x_i-M|.
\]

It has excellent robustness, but it often equals zero in discrete, heavily tied data.

The \(S_n\) statistic moves the median operation into a pairwise-distance construction:

\[
S_n
=
1.1926
\operatorname{median}_i
\operatorname{median}_j|x_i-x_j|.
\]

It retains a high-breakdown robust character while using more information about pairwise spacing.

It can still equal zero when ties dominate strongly, so the practical floor remains necessary.

The multiplier \(3.5\) is deliberately more conservative than using \(2.5\) times unscaled MAD. Since \(S_n\) is normalized to approximate ordinary standard deviation under a normal reference model, \(3.5S_n\) is interpretable as a broad robust-distance threshold rather than a raw-MAD threshold.

No normal-distribution assumption is required for the rule to operate.

---

## A.6 Why the population influence is monotone

A population-size coefficient should not make non-anchor evidence weaker merely because one additional valid submission is added.

The function \(c(N)\) preserves the intended milestones:

\[
c(25)=0.10,
\]

\[
c(50)=0.35,
\]

\[
c(250)=0.85,
\]

\[
c(400)=0.85,
\]

\[
c(1000)=1,
\]

while interpolating monotonically between them.

This avoids a downward influence collapse at \(N=51\) and a large step at \(N=401\).

---

## A.7 Why the Method 1 aggregation is convex

Every valid profile lies in \(\Delta_{100}^{2}\).

A mathematically safe aggregation should remain in that set automatically rather than require normalization after the fact.

The role block

\[
B_g=q_gP_g+(1-q_g)A
\]

is convex because

\[
q_g\in[0,1].
\]

The group average

\[
F_0
=
\frac{
A+\sum_gB_g
}{
G
}
\]

is also convex.

This guarantees:

\[
F_0\in\Delta_{100}^{2}.
\]

The guarantee is structural, not empirical.

No valid input configuration can make the raw total 150 or 200.

---

## A.8 Coefficient interpretation at full population influence

Suppose a Superuser anchor is present and the three non-anchor roles participate.

At

\[
c_{\mathrm{eff}}=1,
\]

the role departure coefficients are

\[
q_M=0.95,
\]

\[
q_L=0.65,
\]

\[
q_C=0.20.
\]

With

\[
G=4,
\]

the direct role coefficients are

\[
\beta_M=0.2375,
\]

\[
\beta_L=0.1625,
\]

\[
\beta_C=0.05.
\]

The anchor coefficient is

\[
\beta_A
=
1-(0.2375+0.1625+0.05)
=
0.55.
\]

Thus even at maximum population influence, the anchor retains 55% of the ordinary coefficient mass in this role configuration.

This is a strong-anchor model by design.

---

## A.9 Full-vector Method 1 example

Let

\[
A=(30,40,30),
\]

\[
P_M=(50,30,20),
\]

\[
P_L=(20,30,50),
\]

\[
P_C=(40,40,20),
\]

and let

\[
c_{\mathrm{eff}}=0.5.
\]

Then

\[
q_M=0.95(0.5)=0.475,
\]

\[
q_L=0.65(0.5)=0.325,
\]

\[
q_C=0.20(0.5)=0.10.
\]

The Moderator block is

\[
B_M
=
0.475P_M+0.525A
=
(39.5,35.25,25.25).
\]

The Community Leader block is

\[
B_L
=
0.325P_L+0.675A
=
(26.75,36.75,36.5).
\]

The Community block is

\[
B_C
=
0.10P_C+0.90A
=
(31,40,29).
\]

With \(G=4\),

\[
F_0
=
\frac{
A+B_M+B_L+B_C
}{4}
\]

and therefore

\[
F_0
=
(31.8125,38,30.1875).
\]

The total is

\[
31.8125+38+30.1875=100.
\]

Largest-remainder reconciliation produces floors

\[
(31,38,30)
\]

with one point remaining.

Micro has the largest remainder, so the final integer profile is

\[
(32,38,30).
\]

---

## A.10 Why detector disagreement receives half influence

The two Method 1 detectors express different statistical philosophies.

Method 1A is globally mean-centered and sensitive to ordinary squared dispersion.

Method 1B is median-centered and robust to a minority of extremes.

If both retain a submission, both perspectives support ordinary role inclusion.

If both reject it, neither supports ordinary role inclusion.

If they disagree, assigning half influence represents partial statistical support without allowing either detector to dominate automatically.

Mathematically,

\[
u_i=\frac{r_{Ai}+r_{Bi}}2
\]

is the arithmetic mean of two binary detector votes.

---

## A.11 Why high-\(N\) anchor submissions retain weight \(0.1\)

The anchor is a domain-prior construct.

At high \(N\), population evidence is strong enough that an unsupported anchor submission should not be fully protected.

However, removing it entirely would contradict the anchor's semantic role and would make a selected anchor disappear after selection.

The weight

\[
0.1
\]

preserves representation while imposing strong dilution.

The two-stage adjustment further reduces between-group anchor mass through \(\rho_A\).

---

## A.12 Why Isolation Forest uses subsamples

Isolation-based anomaly detection depends on how quickly random partitions isolate observations.

Very large samples can mask anomalies by surrounding them with many normal points or by making anomalous clusters appear less rare.

A fixed maximum subsample size controls this effect.

The canonical rule

\[
\psi=\min(256,N)
\]

also keeps the score normalization stable once \(N\) exceeds 256.

The tree count

\[
t=512
\]

reduces Monte Carlo variability relative to a small forest.

The calculation remains dependent on the frozen randomization schedule, which is why deterministic provenance is mandatory.

---

## A.13 Why the Isolation Forest threshold is \(0.60\)

The normalized anomaly score has reference behavior:

\[
s\approx0.5
\]

when average path length resembles the expected reference path length.

Scores closer to 1 indicate unusually short paths.

The threshold

\[
0.60
\]

requires a material upward departure from the ambiguous region around 0.5.

It does not impose a rejection quota.

The strict comparison preserves deterministic threshold equality:

\[
s=0.60
\quad\Longrightarrow\quad
\text{not flagged}.
\]

---

## A.14 Why Method 2 and Method 3 require \(N\ge20\)

Both methods can produce numerical outputs for some smaller populations, but numerical existence is not the same as meaningful population structure.

For Method 3, \(k=10\) requires at least 11 observations merely to define ten other neighbors.

A minimum of 20 ensures that the neighborhood is not almost the entire population in the smallest ready case.

Using the same minimum for Method 2 provides a consistent lower boundary for the purely statistical outputs.

Method 1 remains the method intended for sparse expert-sensitive populations.

---

## A.15 Why LoOP uses tie-inclusive neighborhoods

Integer percentages create frequent duplicate distances.

Suppose the tenth-nearest distance is 5 and four observations are tied at distance 5.

Selecting an arbitrary subset of those tied observations would make LoOP depend on row ordering or identifier ordering.

The inclusive rule

\[
\mathcal N_i
=
\{j:d_{ij}\le r_{i,k}\}
\]

treats equal-distance observations equally.

The resulting neighborhood may contain more than \(k\) observations, which is mathematically preferable to arbitrary exclusion.

---

## A.16 Why \(\lambda=3\) and not \(0.997\)

The LoOP extent parameter multiplies local RMS distance:

\[
pdist_i=\lambda\sigma_i.
\]

The value

\[
\lambda=3
\]

is a standard-deviation multiplier.

The number

\[
0.997
\]

is approximately a coverage probability associated with a three-standard-deviation interpretation under a Gaussian analogy.

They are not interchangeable numeric parameters.

The canonical mathematical parameter is

\[
\lambda=3.
\]

---

## A.17 Why the LoOP binary threshold is \(0.75\)

LoOP produces a continuous normalized score.

The six scalar scores are then passed into a 2-of-6 whole-submission rule.

A low scalar threshold can produce a substantially larger whole-submission rejection rate.

The product threshold

\[
0.75
\]

is deliberately conservative.

It requires strong local outlier evidence in at least two dimensions before rejecting a complete profile.

---

## A.18 Interaction between scalar flag rates and the 2-of-6 rule

For calibration intuition only, suppose each of six dimensions independently flags with probability \(p\).

Then whole-submission rejection probability would be

\[
P(F_i\ge2)
=
1-P(F_i=0)-P(F_i=1),
\]

so

\[
P(F_i\ge2)
=
1-(1-p)^6-6p(1-p)^5.
\]

Illustrative values are:

| Scalar flag probability \(p\) | Hypothetical whole-submission rejection probability |
|---:|---:|
| \(0.05\) | approximately \(0.0328\) |
| \(0.10\) | approximately \(0.1143\) |
| \(0.20\) | approximately \(0.3446\) |

The six dimensions are not independent because of the two 100-point constraints.

The table is therefore not a prediction.

It demonstrates why scalar thresholds must be chosen with the whole-submission rule in mind.

---

## A.19 Why largest remainder supersedes half-up correction

Independent half-up rounding can create a total of 99 or 101.

Repairing that total by modifying the numerically largest or smallest component may move a component that had no rounding error.

Largest remainder instead allocates the finite integer mass according to fractional evidence.

For

\[
(60.5,20.5,19.0),
\]

independent half-up gives

\[
(61,21,19),
\]

which totals 101.

Subtracting from the smallest component would give

\[
(61,21,18),
\]

moving the exact integer 19 away from its raw value.

Largest remainder gives

\[
(61,20,19),
\]

which preserves the exact Macro value and resolves the tied \(0.5\) remainder through the fixed priority.

---

## A.20 Why the three methods remain separately observable

Each method encodes a different inferential stance.

Method 1 contains domain priors.

Method 2 uses global isolation.

Method 3 uses local density.

A simple arithmetic average of their final profiles would blur the source of disagreement and is mathematically prohibited.

This master specification instead defines BHPCM_V1 as the explicit, hierarchical, compositional unification model. Even after unification, the three individual method outputs remain mandatory provenance and advanced-user diagnostics. Their disagreement remains analytically meaningful and must not be hidden.

---

# Appendix B — Recalculation and historical semantics

## B.1 Derived nature

Every final classification is a derived mathematical result.

It is not a user-authored record.

It must not be manually edited.

---

## B.2 Recalculation events

A new result becomes mathematically due when any element of the valid input population changes, including:

- submission creation;
- submission score modification;
- submission deletion;
- validation status change;
- correction of a role snapshot;
- change of calculation specification version.

Under this master specification, due recalculation is performed by the canonical daily calculation epoch defined in Part E. A write does not synchronously mutate the user-visible Final Classification. The next successful daily epoch incorporates every eligible change at or before that epoch's cutoff.

A later current-role change that does not alter the immutable submission-time snapshot does not, by itself, change historical Method 1 input.

---

## B.3 Historical reproducibility

A historical result is reproducible only from:

- the exact valid submission population used at that time;
- the role snapshots used at that time;
- the calculation specification version;
- the Method 2 randomization provenance;
- all frozen method parameters.

A new calculation version may legitimately produce a different result from the same submissions.

The old result remains interpretable through its recorded version.

---

## B.4 Version-change rule

Any change to a normative number, inequality, branch, tie rule, or formula increments the calculation specification version.

Editorial clarification that changes no mathematical behavior may increment documentation revision metadata without changing the calculation version.



---

# Part B — Bayesian Hierarchical Pluralistic Consensus Model

## A Fully Specified Mathematical and Statistical Blueprint for Unifying Methods 1, 2, and 3

**Specification identifier:** `BHPCM_V1`  
**Status:** Normative calculation specification  
**Output:** One unified six-component score comprising a three-component Challenge composition and a three-component Reward composition  
**Interpretive stance:** The output is a governed synthesis of legitimate subjective perspectives. It is not an estimate of a hidden universal truth.

---

# 1. Purpose

This specification defines a complete mathematical and statistical model for combining the outputs and underlying evidence of three established scoring methods:

1. **Method 1:** a role-sensitive, expertise-aware aggregation method;
2. **Method 2:** a globally robust population aggregation method based on Isolation Forest filtering;
3. **Method 3:** a locally robust population aggregation method based on LoOP filtering.

The model produces one unified six-component score:

\[
\mathbf U
=
\left(
U_{C,\mathrm{Micro}},
U_{C,\mathrm{Macro}},
U_{C,\mathrm{Mystiko}},
U_{R,\mathrm{Micro}},
U_{R,\mathrm{Macro}},
U_{R,\mathrm{Mystiko}}
\right),
\]

subject to:

\[
U_{C,\mathrm{Micro}}+U_{C,\mathrm{Macro}}+U_{C,\mathrm{Mystiko}}=100,
\]

and:

\[
U_{R,\mathrm{Micro}}+U_{R,\mathrm{Macro}}+U_{R,\mathrm{Mystiko}}=100.
\]

The model is designed to preserve the following principles simultaneously:

- expert-role judgment is meaningfully represented;
- expert-role judgment cannot obtain unchecked control merely because a privileged role is present;
- population judgment is meaningfully represented;
- Methods 2 and 3 are recognized as correlated population perspectives rather than independent votes;
- disagreement is treated as legitimate pluralism rather than evidence that one side is objectively wrong;
- uncertainty in the final compromise is explicitly represented;
- every normative choice is specified as a governance parameter rather than disguised as an empirical fact;
- identical validated inputs and identical calculation-version parameters produce identical reported results, subject only to explicitly defined random posterior simulation and its required reproducibility metadata.

---

# 2. Non-objective interpretation

## 2.1 No latent universal truth

This model does **not** assume the existence of an objectively correct score vector that respondents approximate with error. The submitted scores are subjective judgments. Disagreement may reflect legitimate differences in priorities, experience, authority, interpretation, or values.

The model therefore does not interpret:

- the majority as automatically correct;
- experts as automatically correct;
- outliers as automatically incorrect;
- later observations as necessarily better than earlier observations;
- convergence over time as proof of truth;
- historical predictive performance as necessary for the model to be meaningful.

## 2.2 Meaning of the unified score

The unified score is defined as:

> The posterior distribution of the composition produced by an explicit governance rule that balances an expertise-sensitive perspective against a robust population perspective while preserving uncertainty about the permitted compromise.

The posterior represents uncertainty over the governed synthesis. It does not represent uncertainty over an external objective answer.

## 2.3 Normative and statistical quantities

The model separates two categories of quantities.

### Normative quantities

Normative quantities are fixed by governance policy. They must not be estimated from the current submissions as if they were objective facts. These include:

- the permitted minimum and maximum influence of the expertise-sensitive perspective;
- the central intended influence of that perspective;
- the permitted balance between Methods 2 and 3;
- the rate at which strong expert-population disagreement reduces expert-method influence;
- the role base weights used internally by Method 1;
- the required integer reconciliation rule.

### Statistical quantities

Statistical quantities describe uncertainty generated by the observed submission population and the three calculation methods. These include:

- bootstrap variability of each method output;
- covariance among score components;
- covariance among method outputs caused by their use of the same submissions;
- the distribution of expert-population disagreement across bootstrap resamples;
- the posterior distribution of the unified score induced by the governance distributions and resampled method outputs.

---

# 3. Required inputs

## 3.1 Submission-level data

Let there be \(N\) validated submissions indexed by \(i\in\{1,\ldots,N\}\).

Each submission must contain:

\[
\mathbf x_i=
\left(
 c_{i\mu},c_{iM},c_{iY},
 r_{i\mu},r_{iM},r_{iY}
\right),
\]

where:

- \(c_{i\mu}\) is Challenge Micro;
- \(c_{iM}\) is Challenge Macro;
- \(c_{iY}\) is Challenge Mystiko;
- \(r_{i\mu}\) is Reward Micro;
- \(r_{iM}\) is Reward Macro;
- \(r_{iY}\) is Reward Mystiko.

Each submission must also contain exactly one role:

\[
g_i\in
\{\mathrm{Community},\mathrm{CommunityLeader},\mathrm{Moderator},\mathrm{Superuser}\}.
\]

## 3.2 Validation constraints

Every component must be finite and satisfy:

\[
0\le x_{ij}\le100.
\]

Every Challenge composition must satisfy:

\[
c_{i\mu}+c_{iM}+c_{iY}=100.
\]

Every Reward composition must satisfy:

\[
r_{i\mu}+r_{iM}+r_{iY}=100.
\]

For integer input, equality must be exact. For non-integer input, equality must satisfy:

\[
\left|c_{i\mu}+c_{iM}+c_{iY}-100\right|\le10^{-9},
\]

and:

\[
\left|r_{i\mu}+r_{iM}+r_{iY}-100\right|\le10^{-9}.
\]

A submission failing any validation constraint is not eligible for any method. Invalid submissions must be removed before \(N\) is established. The calculation metadata must report the raw received count, invalid count, and validated count.

## 3.3 Stable identifier

Each submission must have a unique stable identifier. All method calculations that depend on input order must use ascending lexical order of this identifier unless the underlying method specification defines a stricter ordering rule.

## 3.4 Role base weights

The normative Method 1 role weights are:

| Role | Base weight |
|---|---:|
| Community | 0.20 |
| Community Leader | 0.65 |
| Moderator | 0.95 |
| Superuser | 1.00 |

These values are institutional authority parameters. They are not probabilities, empirical accuracy estimates, or effective sample sizes.

## 3.5 Required method result functions

For any validated dataset \(D\), the system must be able to evaluate the three deterministic method functions:

\[
\mathcal M_1(D),\qquad \mathcal M_2(D),\qquad \mathcal M_3(D).
\]

Each method must return a continuous six-component result before integer reconciliation:

\[
\mathcal M_k(D)=
\left(
\mathbf m_{kC},\mathbf m_{kR}
\right),
\]

where:

\[
\mathbf m_{kt}
=
(m_{kt\mu},m_{ktM},m_{ktY}),
\qquad t\in\{C,R\},
\]

and:

\[
\sum_jm_{ktj}=100,
\qquad
m_{ktj}\ge0.
\]

The unified model must use the continuous pre-reconciliation outputs. It must not use the integer-rounded method outputs as its mathematical inputs.

---

# 4. Roles of the three methods

## 4.1 Method 1 perspective

Method 1 represents the **expertise-sensitive perspective**. It incorporates roles, the selected anchor, role weights, population influence, Method 1A and Method 1B filtering, and any high-population anchor reliability rule defined by the controlling Method 1 specification.

Define:

\[
\mathbf E_t=\mathbf m_{1t}.
\]

The symbol \(\mathbf E_t\) means “expertise-sensitive method perspective.” It does not mean that every component is supplied only by experts, and it does not mean that the perspective is objectively superior.

## 4.2 Method 2 perspective

Method 2 represents a **globally robust population perspective**. It does not use role information, role weights, or anchors.

Define:

\[
\mathbf G_t=\mathbf m_{2t}.
\]

## 4.3 Method 3 perspective

Method 3 represents a **locally robust population perspective**. It does not use role information, role weights, or anchors.

Define:

\[
\mathbf L_t=\mathbf m_{3t}.
\]

## 4.4 Correlation of Methods 2 and 3

Methods 2 and 3 use the same underlying submission population and differ primarily in their anomaly-detection philosophy. They must not be treated as two independent pieces of population evidence.

They are first combined into one population perspective. Only after this consolidation may the population perspective be combined with Method 1.

---

# 5. Compositional geometry

## 5.1 Reason for compositional transformation

A three-component profile lies on a simplex, not in unconstrained Euclidean space. Direct arithmetic operations on independently treated components may fail to respect the relative nature of compositions.

All probabilistic combination, covariance estimation, disagreement measurement, and posterior averaging in this specification must therefore occur in isometric log-ratio space.

## 5.2 Conversion to proportions

For a profile:

\[
\mathbf p=(p_\mu,p_M,p_Y),
\qquad
p_\mu+p_M+p_Y=100,
\]

define the unit-sum composition:

\[
\bar{\mathbf p}=\frac{\mathbf p}{100}.
\]

## 5.3 Strict positivity

The isometric log-ratio transformation requires strictly positive components.

Method-level continuous outputs are expected to be positive. If every component is strictly greater than zero, no adjustment is permitted.

If one or more components are zero, apply multiplicative zero replacement with fixed replacement mass:

\[
\delta=10^{-6}.
\]

Let \(Z\) be the number of zero components and let \(S\) be the set of nonzero components. Replace:

\[
\bar p_j^{*}=\delta
\quad\text{for every zero component }j,
\]

and:

\[
\bar p_j^{*}
=
\bar p_j
\frac{1-Z\delta}{\sum_{h\in S}\bar p_h}
\quad\text{for every nonzero component }j.
\]

The resulting composition must satisfy:

\[
\bar p_j^{*}>0,
\qquad
\sum_j\bar p_j^{*}=1.
\]

The zero replacement constant is a calculation-version parameter and must not be altered within `BHPCM_V1`.

## 5.4 Isometric log-ratio basis

Use the following fixed orthonormal basis:

\[
\mathbf v_1=
\left(
\frac{1}{\sqrt2},
-\frac{1}{\sqrt2},
0
\right),
\]

and:

\[
\mathbf v_2=
\left(
\frac{1}{\sqrt6},
\frac{1}{\sqrt6},
-\frac{2}{\sqrt6}
\right).
\]

For a strictly positive composition \(\bar{\mathbf p}^{*}\), define:

\[
\log\bar{\mathbf p}^{*}
=
(\log\bar p_\mu^{*},\log\bar p_M^{*},\log\bar p_Y^{*}).
\]

The isometric log-ratio transformation is:

\[
\operatorname{ilr}(\mathbf p)
=
\begin{pmatrix}
\mathbf v_1^\top\log\bar{\mathbf p}^{*}\\
\mathbf v_2^\top\log\bar{\mathbf p}^{*}
\end{pmatrix}.
\]

Equivalently:

\[
z_1=\frac{1}{\sqrt2}\log\frac{\bar p_\mu^{*}}{\bar p_M^{*}},
\]

and:

\[
z_2=\frac{1}{\sqrt6}\log\frac{\bar p_\mu^{*}\bar p_M^{*}}{(\bar p_Y^{*})^2}.
\]

## 5.5 Inverse transformation

Given \(\mathbf z=(z_1,z_2)^\top\), calculate:

\[
\boldsymbol\ell=z_1\mathbf v_1+z_2\mathbf v_2.
\]

Then:

\[
q_j=\exp(\ell_j),
\]

and:

\[
\operatorname{ilr}^{-1}(\mathbf z)_j
=
100\frac{q_j}{\sum_hq_h}.
\]

This inverse always produces positive components summing to 100.

## 5.6 Aitchison distance

For two compositions \(\mathbf a\) and \(\mathbf b\), define:

\[
d_A(\mathbf a,\mathbf b)
=
\left\|
\operatorname{ilr}(\mathbf a)-
\operatorname{ilr}(\mathbf b)
\right\|_2.
\]

Aitchison distance is the required disagreement metric throughout this specification.

---

# 6. Joint treatment of Challenge and Reward

For each method \(k\), define the four-dimensional transformed output:

\[
\mathbf z_k
=
\begin{pmatrix}
\operatorname{ilr}(\mathbf m_{kC})\\
\operatorname{ilr}(\mathbf m_{kR})
\end{pmatrix}
\in\mathbb R^4.
\]

The first two coordinates represent Challenge. The final two coordinates represent Reward.

Challenge and Reward are combined in one four-dimensional model so that bootstrap covariance between them is retained. They are converted back into separate three-component profiles only after posterior synthesis.

---

# 7. Sampling uncertainty of the three perspectives

## 7.1 Purpose

Although the judgments are subjective, the calculated method outputs depend on which validated submissions are present. Sampling uncertainty describes the sensitivity of each method perspective to the observed submission population. It does not measure distance from objective truth.

## 7.2 Stratified nonparametric bootstrap

Use a stratified nonparametric bootstrap with fixed replicate count:

\[
B=40.
\]

The production replicate count was selected empirically by the bootstrap
convergence/stability study (see the SBGC-65 bootstrap-stability record)
rather than by a predetermined gold-standard value.  ``B`` is the SMALLEST
value that stabilizes the displayed integer classification across the
non-pathological convergence scenarios under multiple deterministic streams
(the binding scenario stabilizes at ``B=40``; ``B=37`` fails).  A
pathological divergence scenario whose posterior mean sits at a
largest-remainder tie is excluded under documented rationale: it remains
one-point-ambiguous at every practical ``B`` (not a bootstrap-count
deficiency).

Let the role set be:

\[
\mathcal G=
\{\mathrm{Community},\mathrm{CommunityLeader},\mathrm{Moderator},\mathrm{Superuser}\}.
\]

For each role \(g\), let:

\[
D_g=\{\mathbf x_i:g_i=g\},
\qquad
N_g=|D_g|.
\]

For bootstrap replicate \(b\):

1. For each role \(g\), sample \(N_g\) submissions independently with replacement from \(D_g\).
2. Concatenate the four role-specific resamples into bootstrap dataset \(D^{(b)}\).
3. Preserve each sampled submission's role.
4. If a submission is sampled multiple times, each appearance is a separate bootstrap observation.
5. Evaluate all three methods on the same \(D^{(b)}\).

The bootstrap is stratified so that uncertainty concerns the judgments within the observed role structure. It does not add uncertainty about whether the current deployment should contain a different number of role holders.

## 7.3 Sparse privileged roles

If \(N_g=1\), every bootstrap sample for role \(g\) contains the same respondent. The bootstrap therefore represents no within-role variation for that role. This is intentional and must not be interpreted as certainty that the respondent represents every possible holder of the role.

Uncertainty about the institutional influence of sparse privileged roles is controlled by the bounded governance distribution defined later, not by fabricating unobserved respondents.

## 7.4 Bootstrap method outputs

For each bootstrap replicate:

\[
\mathbf z_k^{(b)}
=
\begin{pmatrix}
\operatorname{ilr}(\mathbf m_{kC}^{(b)})\\
\operatorname{ilr}(\mathbf m_{kR}^{(b)})
\end{pmatrix},
\qquad k\in\{1,2,3\}.
\]

If a method returns a non-ready status for a bootstrap replicate, that replicate is invalid for the unified model.

If more than 1% of bootstrap replicates are invalid for any method, the complete unified calculation status is:

`UNIFIED_CALCULATION_UNSTABLE`.

No unified six-point score may be published under that status.

If at most 1% are invalid, discard every replicate in which at least one method is non-ready and continue with the remaining jointly valid replicates.

## 7.5 Preservation of cross-method dependence

The same bootstrap dataset \(D^{(b)}\) must be used for Methods 1, 2, and 3 within replicate \(b\). This preserves dependence among the methods. Independently bootstrapping each method is prohibited because it would incorrectly treat their common data source as independent.

---

# 8. Population-perspective model

## 8.1 Population balance parameter

Let \(\lambda\) be the share of the consolidated population perspective allocated to Method 2, with \(1-\lambda\) allocated to Method 3.

The governance distribution is:

\[
\lambda\sim
\operatorname{Beta}(10,10)
\quad\text{truncated to}\quad
[0.35,0.65].
\]

Its untruncated mean is 0.50. The truncation guarantees that neither globally robust nor locally robust population aggregation receives less than 35% or more than 65% of the population perspective.

The distribution is normative. It represents uncertainty over the acceptable balance between two defensible robustness philosophies. It is not updated by asserting that one method is closer to truth.

## 8.2 Population perspective in ilr space

For bootstrap replicate \(b\) and governance draw \(s\), let \(\lambda^{(s)}\) be a draw from the truncated Beta distribution.

Define:

\[
\mathbf z_P^{(b,s)}
=
\lambda^{(s)}\mathbf z_2^{(b)}
+
(1-\lambda^{(s)})\mathbf z_3^{(b)}.
\]

This is a log-ratio geometric compromise, not a componentwise arithmetic average.

Split:

\[
\mathbf z_P^{(b,s)}
=
\begin{pmatrix}
\mathbf z_{PC}^{(b,s)}\\
\mathbf z_{PR}^{(b,s)}
\end{pmatrix}.
\]

The corresponding population compositions are:

\[
\mathbf P_C^{(b,s)}
=
\operatorname{ilr}^{-1}(\mathbf z_{PC}^{(b,s)}),
\]

and:

\[
\mathbf P_R^{(b,s)}
=
\operatorname{ilr}^{-1}(\mathbf z_{PR}^{(b,s)}).
\]

---

# 9. Expert-population disagreement

## 9.1 Perspective-specific distances

For replicate \((b,s)\), define Challenge disagreement:

\[
D_C^{(b,s)}
=
\left\|
\mathbf z_{1C}^{(b)}-
\mathbf z_{PC}^{(b,s)}
\right\|_2,
\]

and Reward disagreement:

\[
D_R^{(b,s)}
=
\left\|
\mathbf z_{1R}^{(b)}-
\mathbf z_{PR}^{(b,s)}
\right\|_2.
\]

## 9.2 Combined disagreement

Define combined disagreement using equal normative importance for Challenge and Reward:

\[
D^{(b,s)}
=
\sqrt{
\frac{(D_C^{(b,s)})^2+(D_R^{(b,s)})^2}{2}
}.
\]

Neither profile may dominate the disagreement calculation merely because its log-ratio coordinates happen to have a larger count; each profile contributes one-half of squared disagreement.

## 9.3 Disagreement interpretation

The disagreement value is not an error score. A large value means the expertise-sensitive and robust-population perspectives propose materially different relative compositions.

The governance response to disagreement is cautious compromise: as disagreement increases, Method 1's permitted central influence moves toward its governance minimum. This rule does not declare Method 1 incorrect. It prevents either a small privileged group or a large population from obtaining unilateral control when their perspectives conflict sharply.

---

# 10. Bounded expertise-influence model

## 10.1 Fixed bounds

Let \(\omega_E\) be the influence of the Method 1 expertise-sensitive perspective in the final synthesis.

The fixed governance bounds are:

\[
\omega_{\min}=0.30,
\qquad
\omega_{\max}=0.50.
\]

Therefore:

\[
0.30\le\omega_E\le0.50.
\]

Consequences:

- Method 1 always receives at least 30% influence;
- Method 1 can never exceed 50% influence;
- the consolidated population perspective always receives at least 50% influence;
- population aggregation can never entirely suppress the expertise-sensitive perspective.

## 10.2 Disagreement half-life

Set the disagreement half-life:

\[
D_{1/2}=0.25.
\]

This is an Aitchison distance in the fixed ilr basis. At disagreement \(D_{1/2}\), the distance between the minimum and maximum expert influence is reduced by one-half.

## 10.3 Central expert influence

For disagreement \(D\), define the central expert influence:

\[
\mu_E(D)
=
\omega_{\min}
+
(\omega_{\max}-\omega_{\min})
2^{-D/D_{1/2}}.
\]

This gives:

\[
\mu_E(0)=0.50,
\]

\[
\mu_E(D_{1/2})=0.40,
\]

and:

\[
\lim_{D\to\infty}\mu_E(D)=0.30.
\]

The function is continuous and strictly decreasing for \(D>0\).

## 10.4 Governance uncertainty around the central influence

The exact compromise is uncertain even after disagreement is observed. Define an untruncated Beta distribution whose mean is \(\mu_E(D)\) and concentration is:

\[
\kappa_E=40.
\]

For each \((b,s)\):

\[
a_E^{(b,s)}=\kappa_E\mu_E(D^{(b,s)}),
\]

\[
b_E^{(b,s)}=\kappa_E[1-\mu_E(D^{(b,s)})].
\]

Then draw:

\[
\widetilde\omega_E^{(b,s)}
\sim
\operatorname{Beta}
\left(
 a_E^{(b,s)},b_E^{(b,s)}
\right)
\quad\text{truncated to}\quad[0.30,0.50].
\]

Because truncation changes the exact mean, \(\mu_E(D)\) is the central parameter of the underlying Beta distribution, not a claim that the truncated distribution has exactly that expectation.

The concentration \(\kappa_E=40\) fixes the amount of governance uncertainty. It must not be estimated from the current subjective submissions.

## 10.5 Shared influence across Challenge and Reward

The same draw \(\widetilde\omega_E^{(b,s)}\) must be applied to Challenge and Reward. Separate expert weights for Challenge and Reward are prohibited in `BHPCM_V1`.

This restriction ensures that the institutional balance between expertise and population is consistent across the six-point score rather than being opportunistically altered by profile.

---

# 11. Unified posterior composition

## 11.1 Unified transformed score

For posterior draw \((b,s)\), define:

\[
\mathbf z_U^{(b,s)}
=
\widetilde\omega_E^{(b,s)}\mathbf z_1^{(b)}
+
\left[1-
\widetilde\omega_E^{(b,s)}
\right]
\mathbf z_P^{(b,s)}.
\]

Equivalently:

\[
\mathbf z_U^{(b,s)}
=
\widetilde\omega_E^{(b,s)}\mathbf z_1^{(b)}
+
\left[1-
\widetilde\omega_E^{(b,s)}
\right]
\left[
\lambda^{(s)}\mathbf z_2^{(b)}
+
(1-\lambda^{(s)})\mathbf z_3^{(b)}
\right].
\]

Thus the implied draw-specific method weights are:

\[
\omega_1^{(b,s)}
=
\widetilde\omega_E^{(b,s)},
\]

\[
\omega_2^{(b,s)}
=
\left[1-
\widetilde\omega_E^{(b,s)}
\right]\lambda^{(s)},
\]

and:

\[
\omega_3^{(b,s)}
=
\left[1-
\widetilde\omega_E^{(b,s)}
\right](1-\lambda^{(s)}).
\]

For every draw:

\[
\omega_1^{(b,s)}+
\omega_2^{(b,s)}+
\omega_3^{(b,s)}=1,
\]

and all method weights are nonnegative.

## 11.2 Back-transformation

Split:

\[
\mathbf z_U^{(b,s)}
=
\begin{pmatrix}
\mathbf z_{UC}^{(b,s)}\\
\mathbf z_{UR}^{(b,s)}
\end{pmatrix}.
\]

Define:

\[
\mathbf U_C^{(b,s)}
=
\operatorname{ilr}^{-1}
(\mathbf z_{UC}^{(b,s)}),
\]

and:

\[
\mathbf U_R^{(b,s)}
=
\operatorname{ilr}^{-1}
(\mathbf z_{UR}^{(b,s)}).
\]

Every posterior draw satisfies exact compositional normalization apart from numerical precision:

\[
\sum_jU_{Ct,j}^{(b,s)}=100,
\qquad
\sum_jU_{Rt,j}^{(b,s)}=100.
\]

## 11.3 Geometric pooling interpretation

Because linear pooling occurs in ilr space, the unified composition is equivalent to a normalized weighted geometric pool in the simplex.

For a single profile and strictly positive method compositions:

\[
U_j^{(b,s)}
\propto
\left(m_{1j}^{(b)}\right)^{\omega_1^{(b,s)}}
\left(m_{2j}^{(b)}\right)^{\omega_2^{(b,s)}}
\left(m_{3j}^{(b)}\right)^{\omega_3^{(b,s)}}.
\]

The proportional result is normalized to sum to 100.

This prevents the combination from treating percentage components as independent quantities and preserves relative compositional meaning.

---

# 12. Posterior draw structure

## 12.1 Number of governance draws

For every jointly valid bootstrap replicate, take:

\[
S=20
\]

independent governance draws.

The total target number of unified posterior draws is therefore:

\[
B\times S=800.
\]

If bootstrap replicates are discarded under the invalid-replicate rule, the actual total is:

\[
B_{\mathrm{valid}}\times20.
\]

## 12.2 Required dependency structure

Within each posterior draw:

1. select one jointly valid bootstrap replicate \(b\);
2. use all three method outputs calculated from that same replicate;
3. draw one \(\lambda\);
4. calculate the population perspective;
5. calculate disagreement;
6. draw one bounded expert influence;
7. apply the same expert influence to Challenge and Reward;
8. transform the unified profiles back to the simplex.

The dependency ordering above is mathematically mandatory.

## 12.3 Posterior representation

The set:

\[
\left\{
(\mathbf U_C^{(b,s)},\mathbf U_R^{(b,s)})
\right\}
\]

is the posterior distribution of the governed unified score under `BHPCM_V1`.

No additional likelihood toward a hidden objective score is applied.

---

# 13. Official continuous point estimate

## 13.1 Mean in ilr space

The official continuous point estimate must be the posterior mean in ilr space, followed by inverse transformation.

Let \(T=B_{\mathrm{valid}}S\). Define:

\[
\bar{\mathbf z}_U
=
\frac1T
\sum_{b,s}\mathbf z_U^{(b,s)}.
\]

Split:

\[
\bar{\mathbf z}_U
=
\begin{pmatrix}
\bar{\mathbf z}_{UC}\\
\bar{\mathbf z}_{UR}
\end{pmatrix}.
\]

Then the official raw unified profiles are:

\[
\widehat{\mathbf U}_C
=
\operatorname{ilr}^{-1}
(\bar{\mathbf z}_{UC}),
\]

and:

\[
\widehat{\mathbf U}_R
=
\operatorname{ilr}^{-1}
(\bar{\mathbf z}_{UR}).
\]

## 13.2 Why componentwise posterior means are not official

The componentwise arithmetic mean of simplex draws also sums to 100, but it is not the official estimate because the model's pooling geometry is defined in ilr space. Reporting the inverse of the mean ilr vector ensures the point estimate follows the same compositional geometry as the model.

Componentwise posterior means may be published as supplementary diagnostics only and must be labeled `componentwise_posterior_mean`, not `official_raw_score`.

---

# 14. Posterior uncertainty summaries

## 14.1 Marginal credible intervals

For each of the six score components, calculate the equal-tailed 90% credible interval from posterior composition draws:

\[
\mathrm{CI}_{90\%}(U_j)
=
\left[
Q_{0.05}(U_j),Q_{0.95}(U_j)
\right].
\]

Also calculate the 50% interval:

\[
\mathrm{CI}_{50\%}(U_j)
=
\left[
Q_{0.25}(U_j),Q_{0.75}(U_j)
\right].
\]

Quantiles must be calculated on back-transformed component scores, not on ilr coordinates.

## 14.2 Method-weight summaries

Report for each implied method weight \(\omega_k\):

- posterior mean;
- posterior median;
- 5th percentile;
- 95th percentile.

Also report the same summaries for:

- \(\lambda\);
- combined disagreement \(D\);
- Challenge disagreement \(D_C\);
- Reward disagreement \(D_R\);
- expert influence \(\omega_E\).

## 14.3 Directional probabilities

For each profile, report:

\[
\Pr(U_\mu>U_M),
\quad
\Pr(U_\mu>U_Y),
\quad
\Pr(U_M>U_Y).
\]

Also report the posterior probability that each component is the largest:

\[
\Pr
\left(
U_j=\max_hU_h
\right).
\]

Ties in continuous posterior draws have probability zero in ordinary operation. If a numerical tie occurs within \(10^{-12}\), split that draw's rank probability equally among tied components.

## 14.4 Posterior rounded-score probabilities

Apply the final integer reconciliation rule to every posterior composition draw. Report the probability of every integer triplet occurring in at least 0.5% of draws.

For each profile, the probabilities of all reconciled integer triplets must sum to 1 within numerical tolerance.

This summary identifies whether the published integer answer is stable or whether multiple adjacent integer profiles remain materially plausible under the governance model.

---

# 15. Expert-population conflict classification

## 15.1 Point disagreement

Using the original non-bootstrap dataset, calculate:

\[
\mathbf z_E=\mathbf z_1,
\]

and the central population balance:

\[
\lambda_0=0.5.
\]

Then:

\[
\mathbf z_{P0}
=0.5\mathbf z_2+0.5\mathbf z_3.
\]

Calculate:

\[
D_{C0}
=\|\mathbf z_{1C}-\mathbf z_{P0,C}\|_2,
\]

\[
D_{R0}
=\|\mathbf z_{1R}-\mathbf z_{P0,R}\|_2,
\]

and:

\[
D_0
=
\sqrt{\frac{D_{C0}^2+D_{R0}^2}{2}}.
\]

## 15.2 Conflict categories

Use the following fixed categories:

| Combined Aitchison distance | Classification |
|---:|---|
| \(0\le D_0<0.10\) | Low conflict |
| \(0.10\le D_0<0.25\) | Moderate conflict |
| \(0.25\le D_0<0.50\) | High conflict |
| \(D_0\ge0.50\) | Very high conflict |

These labels describe divergence between perspectives. They do not identify which perspective is correct.

## 15.3 Mandatory conflict disclosure

If conflict is High or Very High, the published unified result must be accompanied by the separate continuous outputs of Method 1 and the consolidated population perspective. The unified result must not be presented alone because doing so would conceal a material institutional disagreement.

---

# 16. Final integer reconciliation

## 16.1 Separate reconciliation

Challenge and Reward must be reconciled separately.

Let one official continuous profile be:

\[
\widehat{\mathbf U}
=(u_\mu,u_M,u_Y),
\qquad
u_\mu+u_M+u_Y=100.
\]

## 16.2 Validation

Before reconciliation, verify:

\[
\left|u_\mu+u_M+u_Y-100\right|\le10^{-9}.
\]

If this fails, return:

`UNIFIED_CALCULATION_ERROR`.

## 16.3 Largest-remainder rule

Calculate floors:

\[
f_j=\lfloor u_j\rfloor.
\]

Calculate remaining points:

\[
r=100-\sum_jf_j.
\]

Calculate fractional remainders:

\[
d_j=u_j-f_j.
\]

Add one point to the \(r\) components with the largest fractional remainders.

## 16.4 Tie priority

Resolve exact fractional-remainder ties using:

\[
\mathrm{Micro}>\mathrm{Macro}>\mathrm{Mystiko}.
\]

Two remainders are treated as tied when their absolute difference is no greater than:

\[
10^{-12}.
\]

## 16.5 Final result

The final product-facing output is:

\[
\widehat{\mathbf U}_{C,\mathrm{integer}}
\]

and:

\[
\widehat{\mathbf U}_{R,\mathrm{integer}}.
\]

Each must contain nonnegative integers summing exactly to 100.

---

# 17. Precise treatment of Method 1's expert influence

## 17.1 Method 1 remains internally authoritative to its own specification

The unified model does not alter Method 1's internal role weights, anchor rules, outlier rules, or population-influence curve. Method 1 is evaluated exactly under its controlling version.

This preserves Method 1 as a coherent expertise-sensitive perspective rather than silently replacing it with a different procedure.

## 17.2 External bounded influence

The unified model controls Method 1 at the perspective-combination layer through:

\[
0.30\le\omega_E\le0.50.
\]

Therefore, even if Method 1 internally grants a sparse expert role substantial influence, Method 1 cannot determine more than one-half of the final geometric compromise.

## 17.3 Why internal and external weighting are not duplicate operations

Method 1's internal role weights answer:

> How should roles shape the expertise-sensitive perspective?

The unified expert weight answers:

> How much should the complete expertise-sensitive perspective influence the final synthesis relative to the robust population perspective?

These are different governance questions. Applying both is intentional.

## 17.4 No automatic role correctness

A Superuser, Moderator, or Community Leader profile is not assigned a probability of being correct. Its role affects Method 1 according to institutional policy. Its final system-level influence remains bounded by the unified model.

---

# 18. Why the model is hierarchical

The model has two explicit hierarchy levels.

## 18.1 Population-method hierarchy

Methods 2 and 3 are nested inside the population perspective:

\[
\mathbf z_P
=
\lambda\mathbf z_2+(1-\lambda)\mathbf z_3.
\]

This prevents their common use of the same population from being interpreted as two independent votes against Method 1.

## 18.2 Perspective hierarchy

The population perspective is then combined with the expertise-sensitive perspective:

\[
\mathbf z_U
=
\omega_E\mathbf z_1+(1-\omega_E)\mathbf z_P.
\]

The hierarchy reflects the conceptual structure:

- global and local robustness are two variants of one population-oriented family;
- expertise-sensitive aggregation is a separate institutional perspective;
- the final synthesis balances those two perspective families.

---

# 19. Why the model is Bayesian

The model includes explicit distributions over governance quantities and propagates them jointly with resampling uncertainty:

\[
\lambda\sim\operatorname{TruncatedBeta}(10,10;0.35,0.65),
\]

and:

\[
\omega_E\mid D
\sim
\operatorname{TruncatedBeta}
\left(
40\mu_E(D),
40[1-\mu_E(D)];
0.30,0.50
\right).
\]

The posterior unified distribution follows from these distributions and the joint bootstrap distribution of method perspectives.

No pseudo-likelihood stating that one method observes a hidden true score is introduced.

---

# 20. Policy constants for `BHPCM_V1`

The following constants are frozen for this calculation version:

| Parameter | Symbol | Value |
|---|---:|---:|
| Zero replacement mass | \(\delta\) | \(10^{-6}\) |
| Bootstrap replicates | \(B\) | 40 |
| Governance draws per bootstrap replicate | \(S\) | 20 |
| Method 2 population-balance Beta shape | \(a_\lambda\) | 10 |
| Method 3 population-balance Beta shape | \(b_\lambda\) | 10 |
| Minimum Method 2 share within population perspective | \(\lambda_{\min}\) | 0.35 |
| Maximum Method 2 share within population perspective | \(\lambda_{\max}\) | 0.65 |
| Minimum expertise-perspective influence | \(\omega_{\min}\) | 0.30 |
| Maximum expertise-perspective influence | \(\omega_{\max}\) | 0.50 |
| Disagreement half-life | \(D_{1/2}\) | 0.25 |
| Expertise-weight concentration | \(\kappa_E\) | 40 |
| Credible interval level |  | 90% |
| Maximum invalid bootstrap rate |  | 1% |
| Sum tolerance |  | \(10^{-9}\) |
| Remainder-tie tolerance |  | \(10^{-12}\) |
| Integer remainder priority |  | Micro, Macro, Mystiko |

Changing any frozen constant creates a new calculation version.

---

# 21. Required result statuses

The unified calculation must return exactly one status.

## 21.1 `READY`

Return `READY` only if:

- the validated dataset permits all three methods to return ready continuous outputs;
- at least one jointly valid bootstrap replicate remains;
- invalid bootstrap replicates do not exceed 1%;
- all posterior draws are finite;
- all back-transformed profiles are valid compositions;
- official continuous profiles sum to 100 within tolerance;
- reconciled profiles contain integers summing exactly to 100.

## 21.2 `INSUFFICIENT_METHOD_1`

Return when Method 1 cannot produce a ready result because its anchor or other mandatory requirements are not satisfied.

Scores must be null.

## 21.3 `INSUFFICIENT_METHOD_2`

Return when Method 2 cannot produce a ready result under its minimum-sample or calculation requirements.

Scores must be null.

## 21.4 `INSUFFICIENT_METHOD_3`

Return when Method 3 cannot produce a ready result under its minimum-sample or calculation requirements.

Scores must be null.

## 21.5 `UNIFIED_CALCULATION_UNSTABLE`

Return when more than 1% of bootstrap replicates fail to produce all three method outputs.

Scores must be null.

## 21.6 `UNIFIED_CALCULATION_ERROR`

Return for non-finite values, invalid transformations, failed normalization, invalid governance draws, inconsistent method output, or any other mathematical invariant failure.

Scores must be null.

No fallback arithmetic mean is permitted for a non-ready status.

---

# 22. Mandatory published output

For a `READY` calculation, publish all of the following.

## 22.1 Identification

- unified model identifier;
- Method 1 calculation version;
- Method 2 calculation version;
- Method 3 calculation version;
- input population hash;
- validated submission count;
- role counts;
- calculation timestamp;
- reproducibility seed or random-stream identifier.

## 22.2 Method inputs

For Methods 1, 2, and 3, publish the original-data continuous outputs for Challenge and Reward before integer reconciliation.

## 22.3 Unified scores

Publish:

- official continuous Challenge profile;
- official continuous Reward profile;
- final reconciled Challenge profile;
- final reconciled Reward profile.

## 22.4 Uncertainty

For all six components, publish:

- 50% credible interval;
- 90% credible interval;
- componentwise posterior mean as a supplementary statistic;
- posterior median as a supplementary statistic.

## 22.5 Governance and disagreement

Publish:

- posterior summaries for \(\lambda\);
- posterior summaries for \(\omega_E\);
- implied posterior summaries for \(\omega_1,\omega_2,\omega_3\);
- \(D_{C0}\), \(D_{R0}\), and \(D_0\);
- conflict classification;
- the central expert influence \(\mu_E(D_0)\).

## 22.6 Stability

Publish:

- valid bootstrap count;
- invalid bootstrap count;
- most probable reconciled integer triplet for Challenge and its probability;
- most probable reconciled integer triplet for Reward and its probability;
- every reconciled triplet with posterior probability at least 0.5%.

---

# 23. Mathematical invariants

Every valid implementation must satisfy the following invariants.

## 23.1 Method-weight invariants

For every posterior draw:

\[
0.30\le\omega_1\le0.50,
\]

\[
0.35\le\lambda\le0.65,
\]

\[
\omega_2\ge0,
\qquad
\omega_3\ge0,
\]

and:

\[
\omega_1+\omega_2+\omega_3=1.
\]

## 23.2 Composition invariants

For every posterior draw and each profile:

\[
U_j>0,
\]

and:

\[
\sum_jU_j=100
\]

within numerical tolerance.

## 23.3 Identity invariant

If all three method outputs are identical in a bootstrap replicate, then the unified output for that replicate must equal the common method output for every governance draw.

## 23.4 Population identity invariant

If Methods 2 and 3 are identical, the population perspective must equal their common result for every \(\lambda\).

## 23.5 Expert-population identity invariant

If Method 1 equals the population perspective, the unified output must equal that common result for every expert-weight draw.

## 23.6 Bound invariant

Method 1 can never receive more than 50% or less than 30% of transformed-space influence.

## 23.7 No double-count invariant

Methods 2 and 3 enter only through the population node. They must not each receive a separate top-level weight in addition to their nested population weights.

## 23.8 Role isolation invariant

Changing only role labels while keeping scores fixed may change Method 1 and therefore the unified result. It must not change Method 2 or Method 3.

## 23.9 Reconciliation invariant

Each final integer profile must sum exactly to 100.

---

# 24. Boundary and exceptional cases

## 24.1 Method output containing zero

Apply the exact zero-replacement rule in Section 5.3. Record that zero replacement occurred and identify the method, profile, and components affected.

## 24.2 Methods 2 and 3 strongly disagree

The truncated distribution of \(\lambda\) remains unchanged. Their disagreement appears in the posterior spread of the population perspective. Neither method may be removed solely because it disagrees with the other.

## 24.3 Method 1 strongly disagrees with population

The central expert influence approaches 0.30 according to the fixed half-life function. It never falls below 0.30. The result must be labeled High or Very High conflict if the corresponding threshold is crossed.

## 24.4 One privileged respondent

No synthetic privileged respondents are created. Method 1 handles the role according to its own specification. The unified model limits the entire expertise-sensitive perspective to at most 50%.

## 24.5 No variability across bootstrap replicates

If method outputs are identical in all valid bootstrap replicates, statistical resampling uncertainty is zero. Governance uncertainty remains through \(\lambda\) and \(\omega_E\), unless all three method outputs are also identical, in which case the unified composition is fixed.

## 24.6 Integer ties

Use the specified Micro, Macro, Mystiko priority. No randomized tie-breaking is permitted.

## 24.7 Missing role group in a bootstrap replicate

Stratified resampling preserves every observed nonempty role count. A role present in the original validated data cannot disappear from a bootstrap replicate.

## 24.8 Empty role group in original data

The method-specific rules determine whether Method 1 can proceed. The unified model does not invent a missing role group.

---

# 25. Required sensitivity disclosures

The official score uses the frozen `BHPCM_V1` parameters. In addition, the system must calculate three deterministic sensitivity profiles from the original non-bootstrap method outputs.

First define the central population perspective using:

\[
\lambda=0.50.
\]

Then calculate unified profiles at:

\[
\omega_E=0.30,
\qquad
\omega_E=0.40,
\qquad
\omega_E=0.50.
\]

All calculations must occur in ilr space and be back-transformed before reporting.

For each expert weight, publish:

- continuous Challenge profile;
- reconciled Challenge profile;
- continuous Reward profile;
- reconciled Reward profile.

These are not alternative official results. They disclose how much the final score depends on the normative expertise-population balance.

If any component differs by at least 3 integer points between the 30% and 50% sensitivity profiles, label that component:

`GOVERNANCE_SENSITIVE`.

---

# 26. Interpretation rules

## 26.1 What may be claimed

A `READY` result may be described as:

- a bounded Bayesian synthesis;
- an expertise-and-population compromise;
- a role-aware but expert-limited unified score;
- a compositional posterior summary;
- a result that propagates method and governance uncertainty;
- a result that makes perspective conflict visible.

## 26.2 What must not be claimed

The result must not be described as:

- objectively correct;
- the true underlying score;
- proof that experts are right;
- proof that the majority is right;
- a data-discovered optimal authority balance;
- a forecast that necessarily improves as more subjective data accumulates;
- a measurement of respondent truthfulness;
- a guarantee that anomaly-filtered submissions are incorrect.

## 26.3 Meaning of credible intervals

Credible intervals describe uncertainty under:

- the observed role-stratified submission population;
- the three fixed method definitions;
- the bootstrap resampling scheme;
- the frozen governance distributions;
- the fixed compositional geometry.

They do not describe uncertainty around a universal objective truth.

---

# 27. Rationale for the chosen structure

## 27.1 Why not average the three final scores

A simple arithmetic mean would:

- treat Method 1, Method 2, and Method 3 as equally authoritative without justification;
- count Methods 2 and 3 as independent despite their shared population and similar purpose;
- ignore compositional geometry;
- conceal uncertainty;
- conceal expert-population conflict;
- make no explicit statement about the permissible influence of expert roles.

## 27.2 Why not let Bayesian learning choose the method weights

Without an objective target, external adjudication, or an agreed utility function, the data cannot identify which perspective deserves more normative authority. Estimating authority weights from the same subjective submissions would confuse popularity, internal agreement, and low variance with correctness.

The method weights are therefore governed distributions with explicit bounds.

## 27.3 Why Method 1 receives 30% to 50%

The lower bound ensures that institutional expertise cannot be erased by population volume. The upper bound prevents privileged roles from obtaining unilateral control through Method 1. The range encodes a balanced governance policy in which expertise is always material but never a strict majority of transformed-space influence.

## 27.4 Why disagreement lowers central expert influence

When the expertise-sensitive and population perspectives are close, greater Method 1 influence does not materially override population judgment. When they are far apart, granting maximum expert influence would allow a small role-based perspective to impose a large shift. The decreasing function applies procedural caution under conflict without declaring either side wrong.

## 27.5 Why Methods 2 and 3 are nested

Both methods are robustness treatments of the broad submission population. Nesting them prevents the population from receiving duplicate top-level representation merely because two anomaly-detection techniques are available.

## 27.6 Why use geometric rather than arithmetic pooling

The components are relative parts of a fixed total. Isometric log-ratio pooling respects this structure and produces a normalized weighted geometric compromise. It avoids treating a change in one component as independent of the other two.

## 27.7 Why use stratified bootstrap uncertainty

Stratification preserves the actual institutional role composition while measuring sensitivity to which judgments appear within each role. It does not pretend that the role counts were randomly sampled from a universal workforce.

## 27.8 Why preserve separate method outputs

The unified score is a compromise, not a replacement for the underlying perspectives. Separate outputs remain necessary for auditability and for identifying cases where a single midpoint would conceal strong disagreement.

---

# 28. Formal end-to-end definition

Given validated dataset \(D\):

1. Calculate continuous method outputs:

\[
\mathbf m_1=\mathcal M_1(D),
\quad
\mathbf m_2=\mathcal M_2(D),
\quad
\mathbf m_3=\mathcal M_3(D).
\]

2. Transform each Challenge and Reward composition using the fixed ilr basis.

3. Create 40 role-stratified bootstrap datasets.

4. For each bootstrap dataset, calculate all three continuous method outputs and transform them to four-dimensional ilr vectors.

5. Retain only jointly valid bootstrap replicates subject to the maximum failure rule.

6. For each valid bootstrap replicate, take 20 governance draws.

7. For each governance draw, sample:

\[
\lambda\sim\operatorname{TruncatedBeta}(10,10;0.35,0.65).
\]

8. Calculate:

\[
\mathbf z_P
=\lambda\mathbf z_2+(1-\lambda)\mathbf z_3.
\]

9. Calculate combined expert-population disagreement:

\[
D
=
\sqrt{
\frac{
\|\mathbf z_{1C}-\mathbf z_{PC}\|_2^2
+
\|\mathbf z_{1R}-\mathbf z_{PR}\|_2^2
}{2}
}.
\]

10. Calculate:

\[
\mu_E(D)
=0.30+0.20\times2^{-D/0.25}.
\]

11. Sample:

\[
\omega_E
\sim
\operatorname{TruncatedBeta}
\left(
40\mu_E(D),
40[1-\mu_E(D)];
0.30,0.50
\right).
\]

12. Calculate:

\[
\mathbf z_U
=\omega_E\mathbf z_1+(1-\omega_E)\mathbf z_P.
\]

13. Back-transform Challenge and Reward portions to the simplex.

14. Collect all posterior draws.

15. Calculate the official raw score as the inverse ilr transformation of the posterior mean ilr vector.

16. Apply largest-remainder integer reconciliation separately to Challenge and Reward.

17. Publish the official score, uncertainty summaries, method-weight summaries, conflict disclosure, and sensitivity profiles.

---

# 29. Acceptance tests

A calculation implementation is conformant only if it passes all tests below.

## 29.1 Equal-method test

Input three identical method profiles. The unified result must be identical for all posterior draws regardless of governance weights.

## 29.2 Method 2 and 3 equality test

Set Methods 2 and 3 equal and Method 1 different. Varying \(\lambda\) must not alter the population perspective.

## 29.3 Zero-disagreement test

Set Method 1 equal to the consolidated population perspective. The central expert influence must be 0.50, and the unified profile must equal the common profile for every expert weight.

## 29.4 Half-life test

Set combined disagreement to exactly 0.25. The central underlying Beta mean parameter must be:

\[
\mu_E=0.40.
\]

## 29.5 Large-disagreement test

As disagreement increases, \(\mu_E(D)\) must decrease monotonically toward 0.30 and never cross it.

## 29.6 Weight-bound test

No posterior draw may have Method 1 influence below 0.30 or above 0.50.

## 29.7 Population-balance-bound test

No posterior draw may give Method 2 less than 35% or more than 65% of the population perspective.

## 29.8 Normalization test

Every back-transformed Challenge and Reward draw must sum to 100 within \(10^{-9}\).

## 29.9 Role-change test

Change roles without changing score values. Methods 2 and 3 must remain identical. Method 1 and the unified result may change.

## 29.10 Row-order test

Shuffle input row order while preserving stable identifiers. All original-data method outputs, bootstrap distributions under the same reproducibility stream, and unified summaries must remain identical within numerical tolerance.

## 29.11 Reconciliation test

Test all remainder-tie combinations, including exact Micro-Macro, Micro-Mystiko, Macro-Mystiko, and three-way ties. The specified priority must be followed.

## 29.12 Extreme-expert test

Use a Method 1 composition near a face of the simplex and identical moderate Methods 2 and 3. Confirm that Method 1 transformed-space weight never exceeds 0.50 and that conflict is disclosed.

## 29.13 Extreme-population test

Use Methods 2 and 3 near a face of the simplex and a moderate Method 1. Confirm that Method 1 influence never falls below 0.30.

## 29.14 Invalid-bootstrap test

Force more than 1% of bootstrap replicates to produce a non-ready method. The unified result must return `UNIFIED_CALCULATION_UNSTABLE` with null scores.

---

# 30. Normative summary

`BHPCM_V1` defines one unified score through the following institutional position:

1. Subjective judgments do not converge toward a presumed universal truth.
2. Method 1 expresses an expertise-sensitive perspective worth preserving.
3. Methods 2 and 3 jointly express a robust population perspective.
4. Methods 2 and 3 are correlated and therefore form one nested perspective family.
5. Expert influence is always material but is bounded between 30% and 50%.
6. Strong disagreement reduces the central expert influence toward 30% but never eliminates it.
7. Population influence is always at least 50% but cannot eliminate the expert perspective.
8. Governance uncertainty is represented probabilistically rather than hidden behind one arbitrary fixed weight.
9. Composition calculations use isometric log-ratio geometry.
10. The final integer profile is derived only after posterior synthesis.
11. Conflict and sensitivity must be disclosed rather than concealed by the unified midpoint.
12. The result is a governed pluralistic synthesis, not a claim of objective correctness.

---

# Appendix A. Symbol dictionary

| Symbol | Definition |
|---|---|
| \(N\) | Number of validated submissions |
| \(N_g\) | Number of validated submissions in role \(g\) |
| \(D\) | Validated dataset or combined disagreement, distinguished by context |
| \(D_g\) | Submissions in role \(g\) |
| \(\mathbf x_i\) | Six-component submission \(i\) |
| \(g_i\) | Role of submission \(i\) |
| \(\mathcal M_k\) | Deterministic calculation function for Method \(k\) |
| \(\mathbf m_{kt}\) | Continuous Method \(k\) output for profile \(t\) |
| \(\mathbf z_k\) | Four-dimensional transformed Method \(k\) output |
| \(\mathbf E\) | Method 1 expertise-sensitive perspective |
| \(\mathbf G\) | Method 2 globally robust perspective |
| \(\mathbf L\) | Method 3 locally robust perspective |
| \(\mathbf P\) | Consolidated population perspective |
| \(\mathbf U\) | Unified perspective |
| \(\lambda\) | Method 2 share within the population perspective |
| \(\omega_E\) | Method 1 share within the final synthesis |
| \(\omega_1,\omega_2,\omega_3\) | Implied method weights |
| \(D_C\) | Challenge expert-population Aitchison distance |
| \(D_R\) | Reward expert-population Aitchison distance |
| \(D\) | Combined expert-population disagreement |
| \(D_{1/2}\) | Disagreement half-life for expert influence |
| \(\mu_E(D)\) | Central underlying expert-influence parameter |
| \(\kappa_E\) | Expertise-weight Beta concentration |
| \(B\) | Number of bootstrap replicates |
| \(S\) | Governance draws per valid bootstrap replicate |
| \(\delta\) | Zero replacement mass |
| \(\operatorname{ilr}\) | Isometric log-ratio transformation |
| \(d_A\) | Aitchison distance |

---

# Appendix B. Required calculation metadata schema

The result record must include at least:

- `model`: `BHPCM`;
- `model_version`: `BHPCM_V1`;
- `status`;
- `method_1_version`;
- `method_2_version`;
- `method_3_version`;
- `input_population_hash`;
- `raw_submission_count`;
- `invalid_submission_count`;
- `validated_submission_count`;
- `role_counts`;
- `bootstrap_target_count`;
- `bootstrap_valid_count`;
- `bootstrap_invalid_count`;
- `governance_draws_per_bootstrap`;
- `posterior_draw_count`;
- `zero_replacement_count`;
- `random_stream_identifier`;
- `calculated_at`;
- `method_1_raw_challenge`;
- `method_1_raw_reward`;
- `method_2_raw_challenge`;
- `method_2_raw_reward`;
- `method_3_raw_challenge`;
- `method_3_raw_reward`;
- `unified_raw_challenge`;
- `unified_raw_reward`;
- `unified_integer_challenge`;
- `unified_integer_reward`;
- `component_intervals_50`;
- `component_intervals_90`;
- `method_weight_summaries`;
- `population_balance_summary`;
- `expert_influence_summary`;
- `challenge_disagreement`;
- `reward_disagreement`;
- `combined_disagreement`;
- `conflict_classification`;
- `rounded_profile_probabilities`;
- `sensitivity_profiles`;
- `governance_sensitive_components`.

---

# Appendix C. Frozen role table supplied to Method 1

| Role | Base weight |
|---|---:|
| Superuser | 1.00 |
| Moderator | 0.95 |
| Community Leader | 0.65 |
| Community | 0.20 |

This table is included for completeness. Its interpretation and application are governed by the controlling Method 1 specification. The unified model does not reinterpret these values as probabilities or empirical accuracies.


---

# Part C — Base Unified Confidence Equation

## Population Saturation, Authoritative Sample Support, Expert-Population Deviation, and Authoritative Variance

**Embedded base-model identifier:** `CONFIDENCE_BASE_V1`  
**Status:** Normative mathematical specification  
**Output range:** \([0,100)\), reported as a percentage  
**Interpretive stance:** This embedded section defines the base confidence value `C0`. `C0` is not the final displayed Confidence Level under this master specification; Parts D and E apply the normative resilience and boundary-continuity layers.

---

# 1. Purpose

This specification defines one scalar **Confidence Level** for a unified six-point score consisting of:

- Challenge Micro, Macro, and Mystiko; and
- Reward Micro, Macro, and Mystiko.

The Confidence Level must:

1. increase rapidly with the total validated population size;
2. exhibit diminishing returns as the population becomes large;
3. already be very high at approximately 500 validated submissions;
4. increase when the authoritative sample is sufficiently large;
5. distinguish literal authoritative headcount from effective authoritative sample size when role weights differ;
6. decrease when the authoritative center materially deviates from the robust population center;
7. decrease when authoritative respondents disagree strongly among themselves;
8. avoid treating variance estimated from only one or two authoritative respondents as equally reliable to variance estimated from a larger authoritative sample;
9. respect the compositional nature of the Challenge and Reward triplets;
10. avoid claiming that majority or authoritative respondents are objectively correct.

The equation measures how strongly the available submissions support a **stable and representative governed synthesis** under the specified aggregation policy.

---

# 2. Complete confidence equation

The retained base confidence value is:

\[
\boxed{
C_0
=
100
\left[
1-
\exp
\left\{
-\ln(20)
\left(\frac{N}{500}\right)^{\alpha}
\left[
1+\rho
\left(
1-\exp\left(-\frac{n_{\mathrm{eff}}}{n_0}\right)
\right)
\right]
\exp
\left[
-\gamma_D
\frac{
D_A^2
}{
d_0^2+\dfrac{V_A}{\max(n_{\mathrm{eff}},1)}
}
-
\gamma_V
\left(
\frac{n_{\mathrm{eff}}}{n_{\mathrm{eff}}+n_V}
\right)
\frac{V_A}{v_0^2}
\right]
\right\}
\right]
}
\]

with:

\[
0\le C_0<100.
\]

The recommended frozen parameterization is:

\[
\boxed{
\begin{aligned}
C_0
=
100
\Bigg[
1-
\exp
\Bigg(
&-\ln(20)
\left(\frac{N}{500}\right)^{0.60}
\left[
1+0.25
\left(
1-\exp\left(-\frac{n_{\mathrm{eff}}}{5}\right)
\right)
\right]
\\
&\times
\exp
\left[
-0.50
\frac{
D_A^2
}{
0.25^2+\dfrac{V_A}{\max(n_{\mathrm{eff}},1)}
}
-
0.50
\left(
\frac{n_{\mathrm{eff}}}{n_{\mathrm{eff}}+3}
\right)
\frac{V_A}{0.25^2}
\right]
\Bigg)
\Bigg].
\end{aligned}
}
\]

This frozen base equation is identified as `CONFIDENCE_BASE_V1`. The final user-facing confidence model is `CONFIDENCE_V2`, defined later in this master specification.

---

# 3. Structural decomposition

The equation can be written compactly as:

\[
C_0
=
100\left[1-\exp(-E)\right],
\]

where the nonnegative confidence evidence quantity \(E\) is:

\[
E
=
E_N\times E_A\times E_C.
\]

The three factors are:

\[
E_N
=
\ln(20)
\left(\frac{N}{500}\right)^\alpha,
\]

\[
E_A
=
1+\rho
\left[
1-\exp\left(-\frac{n_{\mathrm{eff}}}{n_0}\right)
\right],
\]

and:

\[
E_C
=
\exp
\left[
-\gamma_D
\frac{D_A^2}{d_0^2+V_A/\max(n_{\mathrm{eff}},1)}
-
\gamma_V
\left(
\frac{n_{\mathrm{eff}}}{n_{\mathrm{eff}}+n_V}
\right)
\frac{V_A}{v_0^2}
\right].
\]

They represent:

- \(E_N\): rapidly saturating population evidence;
- \(E_A\): bounded authoritative sample support;
- \(E_C\): authoritative-population and within-authority coherence.

The outer transformation:

\[
100[1-\exp(-E)]
\]

ensures that confidence rises monotonically with positive evidence, has diminishing returns, equals zero when the evidence quantity is zero, and approaches but does not mathematically exceed 100.

---

# 4. Total validated population

Let:

\[
N=\text{number of validated submissions used by the unified calculation}.
\]

Only submissions satisfying all input-validation requirements may contribute to \(N\).

The population evidence term is:

\[
E_N
=
\ln(20)
\left(\frac{N}{500}\right)^\alpha.
\]

For `CONFIDENCE_BASE_V1`:

\[
\alpha=0.60.
\]

Because:

\[
0<\alpha<1,
\]

population evidence grows sublinearly. Early additions to the population produce larger confidence gains than equally sized additions to an already large population.

The constant \(\ln(20)\) is selected because:

\[
1-\exp[-\ln(20)]=1-\frac1{20}=0.95.
\]

Therefore, when the authoritative adjustment is neutral:

\[
N=500
\quad\Longrightarrow\quad
C_0=95\%.
\]

This fixes 500 validated submissions as the population-only 95% reference point.

---

# 5. Definition of authoritative respondents

Define the authoritative role set:

\[
\mathcal A
=
\{
\mathrm{CommunityLeader},
\mathrm{Moderator},
\mathrm{Superuser}
\}.
\]

Community respondents contribute to the population perspective and total population size but are not included in the authoritative sample-size or authoritative-variance terms.

The authoritative role weights are:

| Role | Weight |
|---|---:|
| Community Leader | 0.65 |
| Moderator | 0.95 |
| Superuser | 1.00 |

For each authoritative respondent \(i\), define \(w_i\) as the weight corresponding to that respondent's role.

These weights represent institutional authority in the confidence calculation. They are not probabilities of correctness.

Let:

\[
n_A=|\mathcal A|
\]

be the literal number of authoritative submissions in the current calculation population.

---

# 6. Effective authoritative sample size

When at least one authoritative respondent exists, define the Kish effective authoritative sample size:

\[
\boxed{
n_{\mathrm{eff}}
=
\frac{
\left(\displaystyle\sum_{i\in\mathcal A}w_i\right)^2
}{
\displaystyle\sum_{i\in\mathcal A}w_i^2
}.
}
\]

If no authoritative respondent exists, define:

\[
n_{\mathrm{eff}}=0.
\]

For a nonempty authoritative sample:

\[
1\le n_{\mathrm{eff}}\le n_A.
\]

If all authoritative respondents have identical weights, then:

\[
n_{\mathrm{eff}}=n_A.
\]

When influence is concentrated in respondents with unequal weights, the effective sample size is lower than the literal authoritative count.

The authoritative sample support term is:

\[
E_A
=
1+
ho
\left[
1-\exp\left(-\frac{n_{\mathrm{eff}}}{n_0}\right)
\right].
\]

For `CONFIDENCE_BASE_V1`:

\[
\rho=0.25,
\qquad
n_0=5.
\]

The term satisfies:

\[
1\le E_A<1.25.
\]

Therefore:

- no authoritative sample produces no uplift beyond the population baseline;
- one authoritative respondent produces only a modest uplift;
- approximately five effective authoritative respondents produce most of the attainable uplift;
- additional authoritative respondents continue to help with diminishing returns;
- authoritative sample size can never increase the evidence quantity by more than 25%.

The uplift is deliberately bounded so that a large authoritative group cannot make confidence arbitrarily high independently of total population size and coherence.

---

# 7. Compositional transformation

## 7.1 Why compositional geometry is required

Each Challenge profile and each Reward profile consists of three nonnegative components summing to 100. Such profiles lie on a simplex. Their components are relative parts of a fixed whole and must not be treated as six independent Euclidean variables.

All authoritative centers, population centers, deviations, and variances in this specification must therefore be calculated in the same fixed isometric log-ratio space used by the unified score model.

## 7.2 Unit-sum conversion

For a three-component profile:

\[
\mathbf p=(p_\mu,p_M,p_Y),
\qquad
p_\mu+p_M+p_Y=100,
\]

define:

\[
\bar{\mathbf p}=\frac{\mathbf p}{100}.
\]

## 7.3 Zero replacement

If every component is strictly positive, no replacement is permitted.

If one or more components are zero, use multiplicative zero replacement with:

\[
\delta=10^{-6}.
\]

If \(Z\) components are zero, replace each zero with \(\delta\) and rescale all nonzero components proportionally so the adjusted composition sums to one.

## 7.4 Fixed ilr basis

Use:

\[
\mathbf v_1
=
\left(
\frac1{\sqrt2},
-\frac1{\sqrt2},
0
\right),
\]

and:

\[
\mathbf v_2
=
\left(
\frac1{\sqrt6},
\frac1{\sqrt6},
-\frac2{\sqrt6}
\right).
\]

Then:

\[
\operatorname{ilr}(\mathbf p)
=
\begin{pmatrix}
\dfrac1{\sqrt2}\log\dfrac{\bar p_\mu^*}{\bar p_M^*}\\[8pt]
\dfrac1{\sqrt6}\log\dfrac{\bar p_\mu^*\bar p_M^*}{(\bar p_Y^*)^2}
\end{pmatrix}.
\]

---

# 8. Four-dimensional authoritative profiles

For authoritative respondent \(i\), define:

\[
\mathbf z_i
=
\begin{pmatrix}
\operatorname{ilr}(\mathbf x_{iC})\\
\operatorname{ilr}(\mathbf x_{iR})
\end{pmatrix}
\in\mathbb R^4.
\]

The first two coordinates represent Challenge. The final two coordinates represent Reward.

This joint representation allows confidence to account for authoritative behavior across both profiles while preserving covariance between Challenge and Reward judgments.

---

# 9. Authoritative center

When at least one authoritative respondent exists, define normalized authority weights:

\[
\widetilde w_i
=
\frac{w_i}{\displaystyle\sum_{h\in\mathcal A}w_h}.
\]

Then define the authoritative center:

\[
\boxed{
\overline{\mathbf z}_A
=
\sum_{i\in\mathcal A}
\widetilde w_i\mathbf z_i.
}
\]

The authoritative center is a weighted geometric center in the original simplex because averaging occurs in ilr space.

If there is exactly one authoritative respondent:

\[
\overline{\mathbf z}_A=\mathbf z_i.
\]

Split the center into Challenge and Reward coordinates:

\[
\overline{\mathbf z}_A
=
\begin{pmatrix}
\overline{\mathbf z}_{A,C}\\
\overline{\mathbf z}_{A,R}
\end{pmatrix}.
\]

---

# 10. Robust population center

The population center must not use Method 1 because Method 1 already contains role-sensitive authoritative influence.

Let:

\[
\mathbf z_2
=
\begin{pmatrix}
\operatorname{ilr}(\mathbf m_{2C})\\
\operatorname{ilr}(\mathbf m_{2R})
\end{pmatrix},
\]

and:

\[
\mathbf z_3
=
\begin{pmatrix}
\operatorname{ilr}(\mathbf m_{3C})\\
\operatorname{ilr}(\mathbf m_{3R})
\end{pmatrix},
\]

where \(\mathbf m_2\) and \(\mathbf m_3\) are the continuous pre-reconciliation outputs of Methods 2 and 3.

Define the fixed confidence-calculation population center:

\[
\boxed{
\mathbf z_P
=
\frac12\mathbf z_2+
\frac12\mathbf z_3.
}
\]

The use of fixed equal weights prevents the reported Confidence Level from changing due to random governance draws in the unified Bayesian synthesis.

Split:

\[
\mathbf z_P
=
\begin{pmatrix}
\mathbf z_{P,C}\\
\mathbf z_{P,R}
\end{pmatrix}.
\]

Methods 2 and 3 are treated as two related population-robust perspectives. Their equal transformed-space pool defines the reference population center for confidence calculation.

---

# 11. Authoritative deviation from the population

Define Challenge deviation:

\[
D_{A,C}
=
\left\|
\overline{\mathbf z}_{A,C}-
\mathbf z_{P,C}
\right\|_2,
\]

and Reward deviation:

\[
D_{A,R}
=
\left\|
\overline{\mathbf z}_{A,R}-
\mathbf z_{P,R}
\right\|_2.
\]

Define combined authoritative-population deviation:

\[
\boxed{
D_A
=
\sqrt{
\frac{
D_{A,C}^2+D_{A,R}^2
}{2}
}.
}
\]

Equivalently:

\[
D_A
=
\sqrt{
\frac{
\left\|
\overline{\mathbf z}_{A,C}-\mathbf z_{P,C}
\right\|_2^2
+
\left\|
\overline{\mathbf z}_{A,R}-\mathbf z_{P,R}
\right\|_2^2
}{2}
}.
\]

Interpretation:

- \(D_A=0\) means the authoritative center and robust population center are identical;
- a larger \(D_A\) means greater separation between the two legitimate perspectives;
- \(D_A\) is not an error score;
- \(D_A\) does not identify which perspective is correct.

---

# 12. Internal authoritative variance

When at least two authoritative respondents exist, define weighted authoritative dispersion:

\[
\boxed{
V_A
=
\frac{
\displaystyle
\sum_{i\in\mathcal A}
w_i
\left\|
\mathbf z_i-
\overline{\mathbf z}_A
\right\|_2^2
}{
4\displaystyle\sum_{i\in\mathcal A}w_i
}.
}
\]

The divisor \(4\) converts total squared deviation across four ilr coordinates into mean squared deviation per coordinate.

If:

\[
n_A\le1,
\]

set:

\[
V_A=0.
\]

This does not assert that one authoritative respondent is perfectly reliable. It means that internal authoritative disagreement is not observable from a sample of one. The authoritative sample-size term ensures that one respondent receives only a modest positive uplift.

Interpretation:

- \(V_A=0\) means complete observed authoritative agreement;
- larger \(V_A\) means weaker internal coherence among authoritative respondents;
- the variance is joint across Challenge and Reward;
- variance is measured in the same ilr geometry as authoritative-population deviation.

---

# 13. Coherence factor

The complete coherence factor is:

\[
\boxed{
E_C
=
\exp
\left[
-\gamma_D
\frac{
D_A^2
}{
d_0^2+\dfrac{V_A}{\max(n_{\mathrm{eff}},1)}
}
-
\gamma_V
\left(
\frac{n_{\mathrm{eff}}}{n_{\mathrm{eff}}+n_V}
\right)
\frac{V_A}{v_0^2}
\right].
}
\]

It satisfies:

\[
0<E_C\le1.
\]

The coherence factor equals one only when:

\[
D_A=0
\quad\text{and}\quad
V_A=0.
\]

It approaches zero as authoritative-population separation or authoritative internal variance becomes sufficiently large.

---

# 14. Authoritative-population deviation penalty

The deviation penalty exponent is:

\[
P_D
=
\gamma_D
\frac{
D_A^2
}{
d_0^2+\dfrac{V_A}{\max(n_{\mathrm{eff}},1)}
}.
\]

For `CONFIDENCE_BASE_V1`:

\[
\gamma_D=0.50,
\qquad
d_0=0.25.
\]

The scale \(d_0\) prevents division by zero and establishes the reference magnitude for substantive authoritative-population deviation.

The term:

\[
\frac{V_A}{\max(n_{\mathrm{eff}},1)}
\]

acts as an uncertainty adjustment for the authoritative center.

Its implications are:

1. **Small authoritative sample with high internal variance:** the authoritative center is unstable, so an observed deviation from the population is not interpreted as a precisely established institutional conflict.
2. **Large authoritative sample with the same internal variance:** the authoritative center is estimated more stably, so a persistent deviation is more clearly established as a conflict between perspectives.
3. **Internally coherent authoritative sample:** the denominator approaches \(d_0^2\), so a large deviation is penalized directly.

A larger established deviation lowers confidence in the compromise score because the single unified midpoint is representing materially different authoritative and population judgments.

The penalty does not identify which side is correct.

---

# 15. Internal authoritative variance penalty

The variance penalty exponent is:

\[
P_V
=
\gamma_V
\left(
\frac{n_{\mathrm{eff}}}{n_{\mathrm{eff}}+n_V}
\right)
\frac{V_A}{v_0^2}.
\]

For `CONFIDENCE_BASE_V1`:

\[
\gamma_V=0.50,
\qquad
v_0=0.25,
\qquad
n_V=3.
\]

The factor:

\[
\frac{n_{\mathrm{eff}}}{n_{\mathrm{eff}}+n_V}
\]

controls how strongly the observed authoritative variance is trusted as evidence of role-level incoherence.

It is close to zero for very small authoritative samples and increases toward one as the effective authoritative sample grows.

This behavior is required because:

- disagreement between two authoritative respondents is informative but provides limited evidence about the wider authoritative perspective;
- disagreement across many authoritative respondents is more credible evidence of genuine authoritative pluralism;
- a large authoritative group with substantial variance must reduce confidence more strongly than the same sample variance calculated from only two respondents.

The variance penalty is separate from the deviation penalty. Therefore, confidence can fall because authoritative respondents disagree with the population, because they disagree among themselves, or because both conditions occur.

---

# 16. Frozen parameter table

| Parameter | Symbol | Value | Function |
|---|---:|---:|---|
| Population reference size |  | 500 | Produces 95% population-only confidence |
| Population curvature | \(\alpha\) | 0.60 | Rapid early growth with diminishing returns |
| Maximum authoritative uplift | \(\rho\) | 0.25 | Caps authoritative sample support at 25% |
| Authoritative sample saturation | \(n_0\) | 5 | Controls diminishing returns in expert count |
| Deviation penalty coefficient | \(\gamma_D\) | 0.50 | Controls sensitivity to expert-population separation |
| Deviation reference scale | \(d_0\) | 0.25 | Aitchison-distance scale |
| Variance penalty coefficient | \(\gamma_V\) | 0.50 | Controls sensitivity to expert disagreement |
| Variance reference scale | \(v_0\) | 0.25 | ilr variance scale |
| Variance credibility sample size | \(n_V\) | 3 | Controls trust in observed expert variance |
| Zero replacement mass | \(\delta\) | \(10^{-6}\) | Enables ilr transformation for zero components |

Changing any frozen parameter creates a new calculation version.

---

# 17. Required special cases

## 17.1 No authoritative respondents

If:

\[
n_A=0,
\]

set:

\[
n_{\mathrm{eff}}=0,
\qquad
D_A=0,
\qquad
V_A=0.
\]

The complete equation then reduces exactly to:

\[
\boxed{
C_0_{\mathrm{population}}
=
100
\left[
1-
\exp
\left(
-\ln(20)
\left(\frac{N}{500}\right)^{0.60}
\right)
\right].
}
\]

The absence of authoritative respondents does not imply zero confidence. It means the score receives no authoritative sample uplift and no authoritative coherence adjustment.

## 17.2 Exactly one authoritative respondent

If:

\[
n_A=1,
\]

then:

\[
n_{\mathrm{eff}}=1,
\qquad
V_A=0.
\]

The respondent's deviation from the robust population center still affects confidence. No internal authoritative variance conclusion is drawn.

## 17.3 Zero validated submissions

If:

\[
N=0,
\]

then:

\[
C_0=0.
\]

No other term may override this result.

## 17.4 Missing Method 2 or Method 3 output

If either Method 2 or Method 3 lacks a ready continuous result, \(\mathbf z_P\) is undefined. The Confidence Level status must be non-ready and the numeric Confidence Level must be null.

No single-method population fallback is permitted in `CONFIDENCE_BASE_V1`.

## 17.5 Non-finite quantities

If any of the following is non-finite, return a calculation error and a null Confidence Level:

- \(N\);
- \(n_{\mathrm{eff}}\);
- \(D_A\);
- \(V_A\);
- any ilr coordinate;
- any method profile component;
- the confidence evidence quantity;
- the final Confidence Level.

## 17.6 Numerical clipping

After successful calculation, apply:

\[
C_0
\leftarrow
\min\left(100,\max(0,C_0)\right).
\]

This clipping is solely a numerical safeguard. The mathematical equation already lies in the required interval.

---

# 18. Population-only scaling

When the authoritative adjustment is neutral, the population curve is approximately:

| Validated population \(N\) | Population-only confidence |
|---:|---:|
| 1 | 6.9% |
| 5 | 17.2% |
| 10 | 24.9% |
| 25 | 39.1% |
| 50 | 52.9% |
| 100 | 68.2% |
| 250 | 86.3% |
| 400 | 92.8% |
| 500 | 95.0% |
| 750 | 97.8% |
| 1,000 | 99.0% |

The curve intentionally treats the increase from 10 to 100 respondents as much more important than the increase from 500 to 590 respondents.

---

# 19. Behavioral interpretation

## 19.1 Large population, coherent authoritative sample, low deviation

When:

- \(N\) is large;
- \(n_{\mathrm{eff}}\) is reasonably large;
- \(V_A\) is small;
- \(D_A\) is small;

confidence approaches 100 rapidly.

This means the unified score is supported by a large population and does not conceal serious disagreement within or between perspectives.

## 19.2 Large population, coherent authorities, large population deviation

When authoritative respondents agree strongly with one another but remain far from the robust population center, \(D_A\) is large and \(V_A\) is small.

The deviation penalty becomes strong. Confidence in the single compromise score falls because the unified value is combining two materially different perspectives.

The reduction does not imply that the authoritative respondents are wrong.

## 19.3 Large population, internally divided authorities

When \(V_A\) is large, the internal authoritative variance penalty reduces confidence.

This prevents the system from describing “authoritative judgment” as one coherent view when authoritative respondents materially disagree among themselves.

## 19.4 One authority aligned with the population

One authoritative respondent produces a small sample-size uplift. If the respondent is close to the population center, the deviation penalty is small.

Confidence may increase modestly, but one respondent is not treated as a broad authoritative consensus.

## 19.5 One authority far from the population

A single authoritative respondent cannot establish authoritative consensus. The sample-size uplift remains small, while the deviation penalty records unresolved authoritative-population separation.

## 19.6 Many coherent authorities far from the population

A large, internally coherent authoritative sample far from the population establishes a genuine institutional conflict. The confidence penalty becomes strong because the authoritative center is stable and materially separated from the population center.

The equation reduces confidence in the compromise score rather than deciding which group is correct.

## 19.7 Many internally divided authorities

A large authoritative group with substantial variance receives a strong internal-coherence penalty because its variance is supported by enough respondents to be treated as meaningful authoritative pluralism.

---

# 20. Historical/base confidence labels (not the final display rule)

The numeric Confidence Level is the primary output. If a categorical label is required, use:

| Confidence Level | Label |
|---:|---|
| \(0\%\leC_0<40\%\) | Low |
| \(40\%\leC_0<65\%\) | Moderate |
| \(65\%\leC_0<80\%\) | Substantial |
| \(80\%\leC_0<90\%\) | High |
| \(90\%\leC_0<97\%\) | Very high |
| \(97\%\leC_0\le100\%\) | Exceptional |

The label must be described as:

> Confidence in the stability and representativeness of the governed unified score under the specified population, authoritative role structure, and aggregation policy.

It must not be described as:

> Probability that the final score is objectively correct.

---

# 21. Required output fields

A complete Confidence Level result must include:

- `confidence_version`: `CONFIDENCE_BASE_V1`;
- `status`;
- `confidence_level_raw`;
- `confidence_level_reported`;
- `confidence_label`;
- `validated_population_size`;
- `authoritative_literal_count`;
- `authoritative_effective_sample_size`;
- `authoritative_challenge_deviation`;
- `authoritative_reward_deviation`;
- `authoritative_combined_deviation`;
- `authoritative_internal_variance`;
- `population_evidence_factor`;
- `authoritative_sample_support_factor`;
- `coherence_factor`;
- `deviation_penalty_exponent`;
- `variance_penalty_exponent`;
- `method_2_continuous_profile`;
- `method_3_continuous_profile`;
- `authoritative_center_profile`;
- `population_center_profile`;
- `role_counts`;
- `role_weight_sums`;
- `zero_replacement_count`;
- `input_population_hash`;
- `calculated_at`.

The reported Confidence Level should be rounded to one decimal place for display. The unrounded value must be retained for audit and comparison.

---

# 22. Mathematical invariants

Every conformant implementation must satisfy the following.

## 22.1 Range

\[
0\leC_0\le100.
\]

## 22.2 Zero-population invariant

\[
N=0\LongrightarrowC_0=0.
\]

## 22.3 Population monotonicity

Holding \(n_{\mathrm{eff}}\), \(D_A\), and \(V_A\) constant:

\[
N_2>N_1
\Longrightarrow
C_0(N_2)>
C_0(N_1).
\]

## 22.4 Authoritative sample monotonicity

Holding \(N\), \(D_A\), and \(V_A\) constant, an increase in \(n_{\mathrm{eff}}\) increases the authoritative support term. The total Confidence Level may nevertheless be affected through the variance-credibility and deviation-certainty terms. Therefore, total confidence is not required to be globally monotone in \(n_{\mathrm{eff}}\) when \(V_A>0\).

This is intentional. A larger authoritative sample makes observed disagreement more credible.

## 22.5 Deviation monotonicity

Holding all other quantities constant:

\[
D_{A,2}>D_{A,1}
\Longrightarrow
C_0(D_{A,2})<
C_0(D_{A,1}).
\]

## 22.6 Variance effect

Holding \(N\), \(n_{\mathrm{eff}}\), and \(D_A=0\) constant, increasing \(V_A\) must decrease confidence.

When \(D_A>0\), \(V_A\) simultaneously weakens the certainty of authoritative-population deviation and increases the internal-variance penalty. The net derivative may depend on the frozen parameters. This interaction is intentional and must not be simplified by removing either effect.

## 22.7 Weight-scale invariance

Multiplying every authoritative role weight by the same positive constant must not change:

- normalized authoritative weights;
- authoritative center;
- effective authoritative sample size;
- authoritative variance;
- final Confidence Level.

## 22.8 Perspective identity

If the authoritative center equals the population center, then:

\[
D_A=0.
\]

## 22.9 Complete observed authoritative agreement

If all authoritative transformed profiles are identical, then:

\[
V_A=0.
\]

## 22.10 Row-order invariance

Reordering submissions without changing their values or roles must not change the Confidence Level.

---

# 23. Acceptance tests

A conformant implementation must pass at least the following tests.

## 23.1 Population reference test

Set authoritative adjustment to neutral and \(N=500\). Confirm:

\[
C_0=95.
\]

within numerical tolerance.

## 23.2 No-authority test

Use no authoritative respondents. Confirm that the complete equation reduces exactly to the population-only equation.

## 23.3 One-authority test

Use one authoritative respondent. Confirm:

\[
n_{\mathrm{eff}}=1,
\qquad
V_A=0.
\]

## 23.4 Equal-authority-weight test

Use \(k\) authoritative respondents with equal weights. Confirm:

\[
n_{\mathrm{eff}}=k.
\]

## 23.5 Unequal-weight test

Use unequal authoritative weights. Confirm:

\[
n_{\mathrm{eff}}<n_A.
\]

unless the unequal values happen to be numerically equal after normalization.

## 23.6 Weight-rescaling test

Multiply all authoritative weights by the same positive constant. Confirm that the Confidence Level does not change.

## 23.7 Perfect-alignment test

Set authoritative and population centers equal. Confirm:

\[
D_A=0.
\]

## 23.8 Perfect-authoritative-agreement test

Set all authoritative profiles equal. Confirm:

\[
V_A=0.
\]

## 23.9 Deviation test

Increase \(D_A\) while holding all other quantities constant. Confirm confidence decreases strictly.

## 23.10 Variance test

Set \(D_A=0\), then increase \(V_A\) while holding all other quantities constant. Confirm confidence decreases strictly.

## 23.11 Population monotonicity test

Increase \(N\) while holding all other quantities fixed. Confirm confidence increases strictly and approaches 100 asymptotically.

## 23.12 Zero-component test

Use profiles containing zero components. Confirm that the fixed multiplicative zero-replacement rule produces finite ilr coordinates.

## 23.13 Missing-population-method test

Make either Method 2 or Method 3 non-ready. Confirm the Confidence Level is null rather than calculated from one population method.

## 23.14 Range test

Test extreme valid values of every term. Confirm the reported result remains in \([0,100]\).

---

# 24. Interpretation summary

The conceptual equation is:

\[
\boxed{
\operatorname{Confidence}
=
100
\left[
1-
\exp
\left(
-
\underbrace{\text{population evidence}}_{\text{rapid saturation}}
\times
\underbrace{\text{authoritative sample support}}_{\text{bounded uplift}}
\times
\underbrace{\text{perspective coherence}}_{\text{deviation and variance penalties}}
\right)
\right].
}
\]

The equation intentionally produces the following behavior:

- population size creates the primary confidence foundation;
- confidence rises quickly and is already approximately 95% at 500 submissions under neutral authoritative adjustment;
- authoritative sample size adds bounded support rather than unrestricted authority;
- effective sample size reflects unequal role weights;
- authoritative-population separation lowers confidence in the unified compromise;
- internal authoritative disagreement independently lowers confidence;
- small authoritative samples do not provide strong evidence of authoritative consensus or variance;
- large authoritative samples make sustained agreement and sustained conflict more consequential;
- no term is interpreted as evidence of an objective universal truth.

The resulting scalar is therefore a **confidence measure for governed synthesis stability and representativeness**, not a correctness probability.



---

# Part D — Final Confidence Architecture

## D.1 Layered definition

The final displayed Confidence Level is not identical to Method 1 population influence, a BHPCM governance weight, a posterior probability, or the embedded base-confidence value.

For `N >= 20`:

```text
BHPCM READY result
-> CONFIDENCE_BASE_V1 gives C0
-> CONFIDENCE_RESILIENCE_V1 gives C_res
-> BOUNDARY_CONTINUITY_V1 gives C_final
-> report C_final as Confidence Level
```

For `1 <= N < 20`, use `PROVISIONAL_CONFIDENCE_V1`.

## D.2 Final categorical labels

| Final Confidence Level | Label |
|---:|---|
| \(0\%\le C<40\%\) | Low |
| \(40\%\le C<65\%\) | Moderate |
| \(65\%\le C<80\%\) | Substantial |
| \(80\%\le C<90\%\) | High |
| \(90\%\le C<97\%\) | Very high |
| \(97\%\le C\le100\%\) | Exceptional |

A provisional result may use the same numeric labels, but its stored status must remain `PROVISIONAL_READY`.

---

# Part D1 — `CONFIDENCE_RESILIENCE_V1`

## D1.1 Purpose

`CONFIDENCE_BASE_V1` can approach zero when authoritative respondents are internally heterogeneous, materially separated from the robust population perspective, or both.

That is mathematically informative.

However, a literal near-zero user-facing value may understate the independent informational support supplied by a large validated population.

The resilience layer:

- does not change BHPCM scores;
- does not change posterior intervals;
- does not change Method 1/2/3 outputs;
- does not claim the majority is objectively correct;
- does not remove expert disagreement from the base confidence equation;
- cannot by itself convert a base result below 50 into a result of 50 or above.

## D1.2 Base value

Let \(C_0\) be the `CONFIDENCE_BASE_V1` result from Part C.

## D1.3 Population-resilience capacity

\[
A(N)
=
25
\min
\left(
1,
\left[
\frac{\ln(1+N)}{\ln(402)}
\right]^{3.5}
\right).
\]

Thus:

\[
0\le A(N)\le25.
\]

Frozen constants:

| Parameter | Value |
|---|---:|
| Maximum resilience capacity | 25 percentage points |
| Saturation population | \(N=401\) |
| Logarithmic curvature exponent | \(3.5\) |

Approximate values:

| N | \(A(N)\) |
|---:|---:|
| 1 | 0.01 pp |
| 5 | 0.36 pp |
| 10 | 1.01 pp |
| 20 | 2.33 pp |
| 50 | 5.71 pp |
| 100 | 10.00 pp |
| 250 | 18.78 pp |
| 400 | 24.96 pp |
| 401+ | 25.00 pp |

## D1.4 Tapered application

If:

\[
C_0\ge50,
\]

then:

\[
C_{\mathrm{res}}=C_0.
\]

If:

\[
0\le C_0<50,
\]

define:

\[
R(N,C_0)
=
A(N)
\left(
1-\frac{C_0}{50}
\right)
\]

and:

\[
\boxed{
C_{\mathrm{res}}
=
C_0
+
A(N)
\left(
1-\frac{C_0}{50}
\right)
}.
\]

## D1.5 Bound

For every \(C_0<50\):

\[
C_{\mathrm{res}}<50.
\]

At maximum capacity:

\[
C_{\mathrm{res}}
=
25+\frac{C_0}{2}
<50.
\]

Thus a Low base result remains Low after resilience.

## D1.6 Severe authoritative disagreement example

If \(N\ge401\) and \(C_0=0\):

\[
C_{\mathrm{res}}=25.
\]

A large population is therefore not presented as supplying literally zero support, but the result remains Low confidence.

---

# Part D2 — `PROVISIONAL_CONFIDENCE_V1`

## D2.1 Applicability

This model applies only when:

\[
1\le N<20
\]

and Method 1 is `READY`.

If Method 1 is not ready, provisional confidence is not calculated.

The stored confidence status is:

```text
PROVISIONAL_READY
```

A valid provisional result must satisfy:

\[
0\le C_{\mathrm{prov}}\le49.
\]

It can never equal or exceed 50.

## D2.2 Meaning

The model answers:

> With too few submissions for Isolation Forest, LoOP, and BHPCM, how much reliability should a user place in the Method 1 classification given sample size, whole-composition agreement, authoritative-role support, authoritative-population alignment, and authoritative internal coherence?

It deliberately allows perfect or near-perfect small-sample agreement to approach 50%.

It deliberately allows severe authoritative disagreement to reduce confidence strongly.

## D2.3 Compositional representation

Use the same zero replacement and fixed ilr basis as BHPCM.

For every valid submission:

\[
\mathbf z_i
=
\begin{pmatrix}
\operatorname{ilr}(C_i)\\
\operatorname{ilr}(R_i)
\end{pmatrix}
\in\mathbb R^4.
\]

Define pairwise whole-submission disagreement:

\[
\delta_{ij}
=
\sqrt{
\frac{
\left\|
\mathbf z_{i,C}-\mathbf z_{j,C}
\right\|_2^2
+
\left\|
\mathbf z_{i,R}-\mathbf z_{j,R}
\right\|_2^2
}{2}
}.
\]

Challenge and Reward therefore receive equal normative importance.

## D2.4 Qn-style robust Aitchison pairwise dispersion

For \(N=1\):

\[
Q_A=0.
\]

For \(2\le N<20\):

\[
h=\left\lfloor\frac N2\right\rfloor+1,
\qquad
k=\binom h2.
\]

Sort all \(\binom N2\) pairwise distances \(\delta_{ij}\) ascending.

Let \(\delta_{(k)}\) be the \(k\)-th order statistic.

Define:

\[
\boxed{
Q_A
=
2.2191\,d_N\,\delta_{(k)}
}.
\]

This is a product-defined multivariate extension of the Rousseeuw-Croux \(Q_n\) pairwise-distance concept into this project's Aitchison/ilr distance.

It must be called **Qn-style Aitchison pairwise dispersion**, not standard scalar \(Q_n\).

Finite-sample factors are frozen:

| N | \(d_N\) |
|---:|---:|
| 2 | 0.3995 |
| 3 | 0.9937 |
| 4 | 0.5132 |
| 5 | 0.8440 |
| 6 | 0.6122 |
| 7 | 0.8588 |
| 8 | 0.6699 |
| 9 | 0.8734 |
| 10 | 0.7201 |
| 11 | 0.8891 |
| 12 | 0.7575 |
| 13 | 0.9023 |
| 14 | 0.7855 |
| 15 | 0.9125 |
| 16 | 0.8078 |
| 17 | 0.9210 |
| 18 | 0.8260 |
| 19 | 0.9279 |

## D2.5 Whole-population agreement factor

Freeze:

\[
q_{1/2}=0.50.
\]

Define:

\[
\boxed{
E_P
=
2^{-(Q_A/q_{1/2})^2}
}.
\]

Therefore:

- \(Q_A=0\Rightarrow E_P=1\);
- \(Q_A=0.5\Rightarrow E_P=0.5\);
- increasing robust compositional dispersion drives \(E_P\) continuously toward zero.

## D2.6 Saturating sample-support ceiling

\[
\boxed{
S(N)
=
45
\frac{
1-\exp(-N/8)
}{
1-\exp(-19/8)
}
}.
\]

For \(1\le N\le19\):

\[
0<S(N)\le45.
\]

Approximate values:

| N | \(S(N)\) |
|---:|---:|
| 1 | 5.83% |
| 2 | 10.97% |
| 5 | 23.06% |
| 10 | 35.40% |
| 15 | 42.01% |
| 19 | 45.00% |

This is the population-only provisional ceiling before role uplift and disagreement penalties.

## D2.7 Authoritative role evidence

The authoritative roles are:

| Role | Weight |
|---|---:|
| Community Leader | 0.65 |
| Moderator | 0.95 |
| Superuser | 1.00 |

Community submissions do not contribute to authoritative role mass.

Define:

\[
H_A=\sum_{i\in\mathcal A}w_i.
\]

Define:

\[
\boxed{
E_R
=
1+
\frac4{45}
\left[
1-\exp\left(-\frac{H_A}{3}\right)
\right]
}.
\]

Then:

\[
1\le E_R<\frac{49}{45}.
\]

Consequences:

- no authoritative respondents: no role uplift;
- stronger/more authoritative evidence increases the attainable provisional confidence;
- the role term cannot push the zero-dispersion \(N=19\) ceiling beyond 49.

## D2.8 Effective authoritative sample size

For a nonempty authoritative set:

\[
n_{\mathrm{eff}}
=
\frac{
\left(\sum_{i\in\mathcal A}w_i\right)^2
}{
\sum_{i\in\mathcal A}w_i^2
}.
\]

If no authoritative respondent exists:

\[
n_{\mathrm{eff}}=0.
\]

## D2.9 Provisional population center

Define the equal-user ilr center:

\[
\mathbf z_{P,\mathrm{prov}}
=
\frac1N
\sum_{i=1}^{N}\mathbf z_i.
\]

## D2.10 Authoritative center

If authoritative submissions exist:

\[
\widetilde w_i
=
\frac{w_i}{\sum_{h\in\mathcal A}w_h},
\]

\[
\overline{\mathbf z}_A
=
\sum_{i\in\mathcal A}
\widetilde w_i\mathbf z_i.
\]

## D2.11 Authoritative-population deviation

When authorities exist:

\[
D_{A,C}
=
\left\|
\overline{\mathbf z}_{A,C}
-
\mathbf z_{P,\mathrm{prov},C}
\right\|_2,
\]

\[
D_{A,R}
=
\left\|
\overline{\mathbf z}_{A,R}
-
\mathbf z_{P,\mathrm{prov},R}
\right\|_2,
\]

\[
D_A
=
\sqrt{
\frac{D_{A,C}^2+D_{A,R}^2}{2}
}.
\]

If no authoritative respondents exist:

\[
D_A=0.
\]

## D2.12 Internal authoritative variance

For at least two authoritative respondents:

\[
V_A
=
\frac{
\sum_{i\in\mathcal A}
w_i
\left\|
\mathbf z_i-\overline{\mathbf z}_A
\right\|_2^2
}{
4\sum_{i\in\mathcal A}w_i
}.
\]

For \(n_A\le1\):

\[
V_A=0.
\]

## D2.13 Authoritative coherence factor

Freeze:

\[
\gamma_D=0.50,
\quad
\gamma_V=0.50,
\quad
d_0=0.25,
\quad
v_0=0.25,
\quad
n_V=3.
\]

When authoritative submissions exist:

\[
\boxed{
E_C^{(\mathrm{prov})}
=
\exp
\left[
-0.50
\frac{
D_A^2
}{
0.25^2+V_A/\max(n_{\mathrm{eff}},1)
}
-
0.50
\left(
\frac{
n_{\mathrm{eff}}
}{
n_{\mathrm{eff}}+3
}
\right)
\frac{V_A}{0.25^2}
\right]
}.
\]

If no authoritative respondents exist:

\[
E_C^{(\mathrm{prov})}=1.
\]

## D2.14 Complete provisional equation

\[
\boxed{
C_{\mathrm{prov}}
=
\min
\left[
49,
S(N)\,
E_R\,
E_P\,
E_C^{(\mathrm{prov})}
\right]
}.
\]

Required range:

\[
0\le C_{\mathrm{prov}}\le49.
\]

## D2.15 Zero-dispersion behavior

If every valid submission has exactly the same Challenge and Reward profiles:

\[
Q_A=0
\Rightarrow
E_P=1.
\]

If authoritative respondents also agree exactly with that common profile:

\[
D_A=0,
\qquad
V_A=0,
\qquad
E_C^{(\mathrm{prov})}=1.
\]

At \(N=19\), the raw sample-support ceiling is 45%.

However, a published provisional result still requires Method 1 to be `READY`. Under the Method 1 anchor rules, an all-Community population below 50 has no qualifying anchor and therefore returns `INSUFFICIENT_ANCHOR`; it does **not** publish a 45% provisional Confidence Level.

When a qualifying privileged anchor exists and all submissions agree exactly, authoritative role mass can raise the provisional Confidence Level above the 45% sample-only ceiling toward, but never beyond, 49%.

## D2.16 Extreme-dispersion behavior

As:

\[
Q_A\to\infty,
\]

\[
E_P\to0
\]

and:

\[
C_{\mathrm{prov}}\to0.
\]

Sufficiently extreme authoritative-population separation or authoritative internal variance may also drive provisional confidence toward zero.

---

# Part D3 — `BOUNDARY_CONTINUITY_V1`

## D3.1 Purpose

At \(N=20\), the product changes regimes:

```text
N=19 -> Method 1 + provisional confidence
N=20 -> Methods 1/2/3 + BHPCM + full confidence
```

A real statistical regime change may legitimately increase or decrease confidence.

However, a purely model-induced negative cliff should be calibrated rather than blindly displayed.

This layer:

- only corrects negative threshold discontinuity;
- does not force linearity;
- does not force confidence to increase with every new submission;
- does not change any classification score.

## D3.2 Exactly N=20

Let the actual 20-submission dataset be \(S_{20}\).

Calculate \(C_{20}\) from the 20-submission set using:

```text
Method 1 original-data continuous output
Method 2 original-data continuous output
Method 3 original-data continuous output
-> CONFIDENCE_BASE_V1
-> CONFIDENCE_RESILIENCE_V1
```

before boundary correction.

The full-production-count BHPCM posterior bootstrap is **not** rerun merely to calibrate each 20-submission boundary subset. `CONFIDENCE_BASE_V1` is defined from the original-data Method 2/3 population center plus authoritative evidence and therefore can be evaluated from the three deterministic original-data method calculations. The parent Game's normal unified snapshot still requires BHPCM_V1 to be READY before a unified score/confidence is published.

For each submission \(j\in S_{20}\), define:

\[
S_{19}^{(-j)}=S_{20}\setminus\{j\}.
\]

Calculate each:

\[
C_{19}^{(-j)}
\]

using `PROVISIONAL_CONFIDENCE_V1`.

A leave-one-out set may lose the qualifying Method 1 anchor. Such a leave-one-out set is then non-ready and contributes no numeric provisional confidence to the boundary median.

Let:

\[
\mathcal J_{\mathrm{ready}}
=
\{j:C_{19}^{(-j)}\text{ is PROVISIONAL\_READY}\}.
\]

If:

\[
|\mathcal J_{\mathrm{ready}}|<10,
\]

the 20-submission calibration set is considered insufficiently stable for boundary estimation and produces:

```text
BOUNDARY_CALIBRATION_UNAVAILABLE
```

with:

\[
\Delta_{20}=0.
\]

If at least 10 leave-one-out values are ready, define:

\[
C_{19}^{*}
=
\operatorname{median}_{j\in\mathcal J_{\mathrm{ready}}}
C_{19}^{(-j)}.
\]

Define:

\[
\boxed{
\Delta_{20}
=
\max
\left(
0,
C_{19}^{*}-C_{20}
\right)
}.
\]

If the full model naturally has equal or higher confidence, the correction is zero.

## D3.3 N greater than 20 and static calibration

The boundary correction is a **static per-Game, per-calculation-version calibration constant**. It is not recomputed on every daily epoch.

### D3.3.1 Calibration moment

A Game is calibrated when one of the following first occurs:

1. it crosses from \(N<20\) to \(N\ge20\) under the current master calculation version;
2. this master calculation version is deployed for a Game that already has \(N>20\);
3. a future explicit calculation-version migration requires recalibration.

Ordinary later submission additions, edits, or deletions do not silently change the stored boundary constant within the same calculation version.

If a Game later falls below 20, the provisional regime applies. If it subsequently returns to \(N\ge20\) under the same version, the previously stored boundary constant remains the canonical constant unless an explicit recalibration rule/version says otherwise.

### D3.3.2 Exact crossing at N=20

If calibration occurs at exactly \(N=20\), the actual current 20-submission population is the sole calibration set and:

\[
\Delta_{20}^{*}=\Delta_{20}.
\]

### D3.3.3 Calibration when the Game already has N>20

Let:

\[
M=\binom N{20}.
\]

If:

\[
M\le256,
\]

use every distinct 20-submission subset.

If:

\[
M>256,
\]

use exactly 256 distinct 20-submission subsets sampled without replacement by the versioned deterministic sampler `BOUNDARY_SUBSAMPLE_V1`.

The sampler must use:

- canonical submission ordering;
- Game identifier;
- exact calibration input-population hash;
- master calculation version;
- recorded deterministic seed/stream identifier.

The same Game, calibration population and calculation version must reproduce the same subset collection.

For each subset \(b\):

1. calculate original-data Method 1, Method 2 and Method 3 outputs;
2. if any method required by `CONFIDENCE_BASE_V1` is non-ready, mark that subset calibration non-ready;
3. otherwise calculate \(C_{20}^{(b)}\) through `CONFIDENCE_RESILIENCE_V1`, without running a BHPCM posterior bootstrap;
4. calculate the twenty leave-one-out provisional candidates;
5. retain only leave-one-out candidates whose Method 1 and provisional confidence are ready;
6. if fewer than 10 leave-one-out candidates are ready, mark subset \(b\) calibration non-ready;
7. otherwise define:

\[
C_{19}^{*(b)}
=
\operatorname{median}
\left(
C_{19}^{(b,-j)}
:
j\in\mathcal J_{\mathrm{ready}}^{(b)}
\right);
\]

8. define:

\[
\Delta_{20}^{(b)}
=
\max
\left(
0,
C_{19}^{*(b)}-C_{20}^{(b)}
\right).
\]

Let \(\mathcal B_{\mathrm{ready}}\) be the ready 20-submission calibration subsets.

If:

\[
|\mathcal B_{\mathrm{ready}}|
<
\max
\left(
1,
\left\lceil0.80B_{\mathrm{attempted}}\right\rceil
\right),
\]

then calibration is considered unstable and returns:

```text
BOUNDARY_CALIBRATION_UNAVAILABLE
```

with:

\[
\Delta_{20}^{*}=0.
\]

Otherwise define the static Game/version constant:

\[
\boxed{
\Delta_{20}^{*}
=
\operatorname{median}_{b\in\mathcal B_{\mathrm{ready}}}
\Delta_{20}^{(b)}
}.
\]

Persist this value with:

- calibration population hash;
- N at calibration;
- number of attempted subsets;
- number of ready subsets;
- sampler version;
- seed/stream identifier;
- calculation version;
- calibrated-at timestamp.

### D3.3.4 Why the constant is static

The boundary layer corrects a structural discontinuity between two model regimes. It is not a continuously re-estimated statistical feature.

Keeping \(\Delta_{20}^{*}\) static:

- matches its role as a regime-transition calibration constant;
- prevents current high-N data from retrospectively redefining the historical N=20 boundary;
- avoids multiplying the already expensive daily BHPCM workload;
- keeps confidence reproducible;
- allows its influence to disappear naturally through the decay factor below.

## D3.4 Decay with mature sample size

Freeze:

\[
\tau_B=100.
\]

Define:

\[
\boxed{
g(N)
=
\exp
\left(
-\frac{N-20}{100}
\right),
\qquad N\ge20.
}
\]

Approximate retained correction:

| N | \(g(N)\) |
|---:|---:|
| 20 | 1.000 |
| 50 | 0.741 |
| 100 | 0.449 |
| 250 | 0.100 |
| 500 | 0.008 |

## D3.5 Final full-regime Confidence Level

Let \(C_{\mathrm{res}}\) be the result after `CONFIDENCE_RESILIENCE_V1`.

Then:

\[
\boxed{
C_{\mathrm{final}}(N)
=
\min
\left[
100,
C_{\mathrm{res}}(N)
+
\Delta_{20}^{*}g(N)
\right].
}
\]

This is `CONFIDENCE_V2` for \(N\ge20\).

## D3.6 Boundary provenance

Record:

- `confidence_base`;
- `population_resilience_capacity`;
- `population_resilience_applied`;
- `confidence_after_resilience`;
- `boundary_calibration_status`;
- `boundary_calibrated_at`;
- `boundary_calibration_population_hash`;
- `boundary_calibration_population_size`;
- `boundary_subset_count_attempted`;
- `boundary_subset_count_ready`;
- `boundary_sampling_version`;
- `boundary_sampling_seed_or_stream`;
- `boundary_delta`;
- `boundary_decay_factor`;
- `boundary_adjustment_applied`;
- `confidence_final_unrounded`;
- `confidence_final_displayed`.

---

# Part E — Unified End-to-End Calculation Contract

## E.1 Daily calculation epoch

Derived scores are calculated in daily batches.

A calculation epoch has:

- `epoch_id`;
- `cutoff_at`;
- `started_at`;
- `completed_at`;
- master calculation version;
- exact input-population hashes per Game;
- success/failure status.

The scheduler should normally initiate one epoch per calendar day around 00:00 application/system time, but scheduler implementation is operational rather than mathematical.

The cutoff semantics are normative.

## E.2 Snapshot eligibility

For a Game, epoch \(e\) uses the canonical state of every valid submission whose effective state is committed at or before:

\[
\mathrm{cutoff}_e.
\]

Changes after the cutoff belong to the next epoch.

An edit replaces the previous effective submission state for the new epoch; it does not create two simultaneous valid submissions for one user/Game pair.

## E.3 Atomic publication

A new Final Classification becomes visible only after every required component for the applicable regime has completed successfully and invariants pass.

Partial publication is prohibited.

For \(N<20\):

```text
Method 1 score + provisional confidence
```

must publish together.

For \(N\ge20\):

```text
Method 1
Method 2
Method 3
BHPCM unified score
CONFIDENCE_V2
required provenance
```

must publish as one coherent versioned snapshot.

If the current epoch fails for a Game, the previous successful snapshot remains visible and is marked stale internally.

## E.4 Read-only derived output

A Final Classification is a mathematical output.

No administrator, Superuser, Moderator, API consumer, migration utility, or UI form may manually edit its calculated scores, confidence, method outputs, posterior summaries, or provenance as if they were editorial inputs.

Corrections are made through source submissions, source metadata, or a calculation-version change followed by recalculation.

## E.5 Ordinary-user presentation

The ordinary product prioritizes:

```text
Final Classification
Challenge: Micro / Macro / Mystiko
Reward: Micro / Macro / Mystiko
Confidence Level: X%
```

For \(N<20\), also indicate provisional status concisely.

Ordinary users do not need three competing headline method scores.

## E.6 Advanced/Admin presentation

A read-only advanced view may expose:

- Method 1 continuous and reconciled scores;
- Method 2 continuous and reconciled scores;
- Method 3 continuous and reconciled scores;
- BHPCM unified continuous and reconciled scores;
- posterior credible intervals;
- method-weight summaries;
- expert-population conflict;
- population influence;
- rejection diagnostics;
- provisional/full confidence factors;
- boundary correction;
- calculation versions;
- input counts/hashes;
- stale/fresh state.

## E.7 Method similarity is not a defect

Methods 2 and 3 may often return similar outputs because they use the same bounded, compositional, repeated-integer submission population.

Agreement is valid.

Disagreement is also valid.

Neither outcome is tuned away.

---

# Part F — Required Simulation and Mathematical Validation Program

## F.1 Purpose

Before production acceptance, the implementation must produce a reproducible simulation report.

Simulation is required to demonstrate actual behavior, expose pathological interactions, validate invariants, and give the product owner understandable evidence.

Simulation must not tune thresholds merely to force aesthetically preferred rejection counts or outcomes.

If frozen behavior is unacceptable, the specification must be intentionally revised and versioned.

## F.2 Required N boundaries

At minimum:

```text
0, 1, 2, 5, 6, 8, 9, 10, 15, 18, 19, 20, 21,
25, 26, 50, 51, 100, 250, 400, 401, 500, 1000, 1001
```

## F.3 Required population scenarios

Include:

1. perfect unanimous agreement;
2. tight unimodal agreement;
3. moderate symmetric dispersion;
4. one extreme high-tail respondent;
5. one extreme low-tail respondent;
6. symmetric 0/100 extremes;
7. several isolated extremes;
8. bimodal 50/50 population;
9. 75/25 majority/minority population;
10. dense minority cluster;
11. sparse bridge observations;
12. uniformly spaced scalar values;
13. many duplicate integer profiles;
14. zero-heavy compositions such as `100/0/0`;
15. approximately balanced `33/33/34`;
16. expert/population near-perfect agreement;
17. moderate expert/population conflict;
18. severe expert/population conflict;
19. internally unanimous experts;
20. internally highly divided experts;
21. no authoritative respondents;
22. exactly one authoritative respondent;
23. multiple Superusers giving mutually opposite profiles;
24. all Community respondents, including explicit confirmation that N<20 cannot publish Method 1 without a qualifying anchor;
25. one Superuser plus a large Community population;
26. role changes with identical score values;
27. Method 2 and Method 3 near-identical outputs;
28. Method 2 and Method 3 materially divergent outputs;
29. Method 1 materially divergent from both population methods;
30. all three methods nearly identical.

## F.4 Required role structures

Explicitly simulate:

- Superuser anchor;
- two-Moderator substitute;
- five-Community-Leader substitute;
- one Moderator + three Community Leaders;
- one Moderator + four Community Leaders;
- one Moderator + five Community Leaders;
- no privileged anchor below 50;
- Community fallback at 50;
- Community fallback at 401;
- mixed role populations with unequal counts.

## F.5 Required outputs per scenario

Record all applicable:

- raw N and role counts;
- Method 1 population influence;
- Method 1A/1B diagnostics and flags;
- detector agreement weights;
- anchor type/membership/reliability;
- Method 1 coefficients and score;
- Method 2 anomaly distributions, flags, survivors and score;
- Method 3 LoOP distributions, flags, survivors and score;
- three continuous method profiles;
- BHPCM bootstrap valid/invalid counts;
- posterior draw count;
- population-balance summaries;
- expert-influence summaries;
- implied method weights;
- conflict category;
- unified score;
- 50% and 90% credible intervals;
- most probable integer triplets;
- base confidence;
- resilience adjustment;
- provisional confidence where applicable;
- boundary delta/decay/adjustment;
- final displayed confidence;
- all invariant results.

## F.6 Mandatory 19-to-20 boundary study

Construct matched families where a twentieth submission is added without materially changing the underlying population.

Test:

- perfect agreement;
- modest disagreement;
- strong disagreement;
- expert/population disagreement;
- no authorities;
- one authority;
- multiple authorities;
- strong expert internal conflict.

Report corrected and uncorrected confidence.

Verify:

- positive natural transitions are not reduced;
- negative threshold gaps yield nonnegative \(\Delta_{20}\);
- exact \(N=20\) uses all 20 leave-one-out datasets;
- correction decays with N;
- mature high-N confidence is not permanently dominated by threshold calibration.

## F.7 Population-resilience pathological study

Include:

```text
large N
population broadly coherent
authoritative respondents in extreme internal disagreement
base confidence approximately 0
```

Verify:

- the base remains low;
- resilience is bounded;
- at N >= 401 a zero base becomes 25 before boundary adjustment;
- expert conflict remains visible;
- the adjustment does not imply majority correctness.

## F.8 Required invariants under random simulation

Verify:

- every valid input Challenge/Reward totals 100;
- every READY method raw profile totals 100 within tolerance;
- every READY integer profile totals exactly 100;
- every BHPCM posterior draw totals 100;
- coefficients are nonnegative;
- required coefficient sets sum to 1;
- no non-finite value is silently coerced;
- identical provenance is deterministic;
- row-order permutations do not change results;
- role changes affect only role-sensitive mathematics;
- provisional confidence never reaches 50;
- boundary calibration is never negative.

## F.9 Simulation deliverable

Produce a human-readable report with:

- scenario description;
- input generation rule;
- random seed;
- role structure;
- key population summary;
- method outputs;
- unified output;
- confidence;
- rejections;
- conflict;
- interpretation;
- invariant result.

Charts may supplement but must not replace numerical tables.

---

# Part G — Final Master Invariants and Prohibitions

## G.1 Score invariants

Every READY Challenge and Reward output must:

- have exactly three components;
- have finite nonnegative continuous components;
- total 100 within numerical tolerance before reconciliation;
- have integer displayed components after reconciliation;
- total exactly 100 after reconciliation.

## G.2 No partial score

Challenge and Reward availability are inseparable.

## G.3 Submission integrity

No method may:

- impute missing submitted components;
- repair an invalid submitted total;
- partially remove one score component;
- use current role instead of immutable role snapshot;
- count duplicate same-user/Game submissions as independent valid submissions.

## G.4 Outlier integrity

Outlier filtering is single-pass.

Complete submissions are retained/rejected by the detector's 2-of-6 rule.

## G.5 No hidden consensus

Prohibited:

- arithmetic mean of Methods 1/2/3 headline scores;
- arbitrary method weights;
- treating Methods 2/3 as independent top-level votes in addition to their BHPCM population node;
- using rounded method outputs as BHPCM inputs.

## G.6 No manual derived editing

Final derived classifications, confidence, credible intervals, conflicts and statistical provenance are read-only.

## G.7 No threshold tuning by desired outcome

A threshold may not be changed because a simulation rejected “too many” or “too few” submissions or gave an inconvenient score.

A model change requires a new version, rationale, simulation comparison and regression fixtures.

## G.8 Determinism

Identical population, stable identifiers, role snapshots, model versions and randomization provenance must reproduce identical stored outputs.

## G.9 Confidence semantics

The product may call the scalar output **Confidence Level**.

It must not be represented as probability that:

- a subjective score is universally true;
- an outlier is wrong;
- an expert is correct;
- the majority is correct.

## G.10 Calculation errors

Undefined branches outside explicit special cases are errors.

They must not be coerced to zero, one, a mean, a prior result, or an arbitrary fallback.

## G.11 Versioning

Any change to a normative:

- formula;
- numerical threshold;
- sample boundary;
- role weight;
- seed;
- randomization schedule;
- bootstrap count;
- governance draws;
- zero replacement;
- ilr basis;
- confidence cap;
- boundary decay;
- finite-sample Qn factor;
- tie priority;
- status condition;

requires a calculation-version change.

---

# Part H — Compact End-to-End Algorithm

## H.1 Validate

For each Game:

1. obtain the daily-epoch submission snapshot;
2. remove invalid submissions before N;
3. enforce one submission per user/Game;
4. use immutable role snapshots;
5. canonicalize stable identifier ordering;
6. hash the exact input population.

## H.2 Branch on N

### N = 0

Status:

```text
NO_SUBMISSIONS
```

No score.

### 1 <= N < 20

1. calculate Method 1;
2. if non-ready, publish no derived score;
3. if ready:
   - reconcile Method 1 display profile;
   - calculate `PROVISIONAL_CONFIDENCE_V1`;
   - publish a provisional Final Classification.

### N >= 20

1. calculate Method 1;
2. calculate Method 2;
3. calculate Method 3;
4. apply BHPCM status rules;
5. when BHPCM is usable:
   - stratified bootstrap;
   - governance draws;
   - unified posterior;
   - official ilr-space point estimate;
   - inverse transform;
   - largest-remainder reconciliation;
6. calculate `CONFIDENCE_BASE_V1`;
7. apply `CONFIDENCE_RESILIENCE_V1`;
8. obtain the persisted `BOUNDARY_CONTINUITY_V1` calibration constant, calibrating it only when the explicit calibration-moment rule requires;
9. apply the current-N decay to that static boundary constant;
10. cap at 100;
11. publish one atomic unified snapshot.

## H.3 Persist provenance

Persist every mandatory field from:

- Method 1;
- Method 2;
- Method 3;
- BHPCM;
- confidence base;
- resilience layer;
- provisional layer where applicable;
- boundary layer where applicable;
- epoch metadata;
- version identifiers.

---

# Part I — Consolidated Scientific and Specification References

1. **Rousseeuw, P. J. & Croux, C. (1993).** “Alternatives to the Median Absolute Deviation.” *Journal of the American Statistical Association*, 88(424), 1273–1283.  
   Foundation for robust \(S_n\) and \(Q_n\)-family scale ideas.

2. **Akinshin, A. (2022).** “Finite-sample Rousseeuw-Croux scale estimators.”  
   Used for finite-sample discussion and the frozen small-N \(d_N\) factors in `PROVISIONAL_CONFIDENCE_V1`.

3. **Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008).** “Isolation Forest.” *IEEE International Conference on Data Mining*.  
   Foundation for Method 2.

4. **Kriegel, H.-P., Kröger, P., Schubert, E., & Zimek, A. (2009).** “LoOP: Local Outlier Probabilities.”  
   Foundation for Method 3.

5. **Aitchison, J. (1982).** “The Statistical Analysis of Compositional Data.” *Journal of the Royal Statistical Society, Series B*, 44(2), 139–160.  
   Foundation for treating fixed-sum profiles as compositional data on a simplex.

Scientific literature motivates techniques; exact product parameters in this file are governed by this specification, not third-party defaults.

---

# Part J — Authority Statement

`statistical_model.md` is the mathematical bible of the project.

An implementation is non-conformant if it:

- needs to guess a branch this file defines;
- silently substitutes library defaults;
- omits required provenance;
- changes because database row order changed;
- performs synchronous user-visible recalculation contrary to daily epoch semantics;
- uses the provisional model at N >= 20 as the normal full confidence model;
- uses BHPCM confidence below N = 20;
- arithmetically averages Methods 1, 2 and 3;
- manually edits a derived Final Classification;
- changes thresholds to make simulations “look better” without a version change.

If a genuinely new mathematical edge case is discovered that is unresolved anywhere in this file, the correct behavior is:

```text
CALCULATION_ERROR
```

plus a deliberate specification amendment.

The implementation must never guess.
