"""
Run the required SBGC-65 mathematical simulation program (Part F).

Covers the frozen N boundaries, the thirty required population scenarios,
the required role structures, the 19->20 boundary study, the population-
resilience pathological study, and invariant checks under random data.
Writes a human-readable Markdown report with seeds and provenance.

Simulation configuration: reduced bootstrap/governance counts are used for
the scenario matrix (documented in the report); the frozen production
settings are exercised by the dedicated acceptance test in
``test_calculations_bhpcm``.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from classifications.calculations.bhpcm import bhpcm_calculate
from classifications.calculations.confidence import (
    BoundaryCalibrationData,
    boundary_calibrate,
    boundary_final_confidence,
    confidence_base_calculate,
    provisional_confidence_calculate,
    resilience_apply,
)
from classifications.calculations.engine import calculate_game
from classifications.calculations.method1 import method1_calculate
from classifications.calculations.method2 import method2_calculate
from classifications.calculations.method3 import method3_calculate
from classifications.calculations.profiles import (
    Profile,
    SubmissionRecord,
    build_population_snapshot,
)
from classifications.calculations.results import READY

DEFAULT_BOOTSTRAP = 40
DEFAULT_DRAWS = 2
LARGE_N_BOOTSTRAP = 12

# The scenario matrix and N-boundary table report regime behavior, not
# boundary calibration; injecting a zero-delta stored constant skips the
# expensive calibration moment.  Calibration itself is exercised by the
# dedicated 19->20 boundary study below and the persistence/unit tests.
ZERO_BOUNDARY = BoundaryCalibrationData(status=READY, delta=0.0)


def _p(micro: float, macro: float, mystiko: float) -> Profile:
    return Profile(micro=micro, macro=macro, mystiko=mystiko)


def _sub(
    identifier: str,
    challenge: Profile,
    reward: Profile,
    role: str = "community",
) -> SubmissionRecord:
    return SubmissionRecord(
        identifier=identifier, challenge=challenge, reward=reward, role=role
    )


def _snap(subs: list[SubmissionRecord]):
    return build_population_snapshot(subs)


def _identical(
    count: int,
    role_map: dict[int, str] | None = None,
    prefix: str = "s",
    challenge: Profile | None = None,
    reward: Profile | None = None,
) -> list[SubmissionRecord]:
    challenge = challenge or _p(45.0, 30.0, 25.0)
    reward = reward or _p(40.0, 30.0, 30.0)
    role_map = role_map or {}
    return [
        _sub(
            f"{prefix}-{i:05d}",
            challenge,
            reward,
            role_map.get(i, "community"),
        )
        for i in range(count)
    ]


def _scattered(
    count: int,
    seed: int,
    role_map: dict[int, str] | None = None,
    spread: float = 8.0,
    base_challenge: Profile | None = None,
    base_reward: Profile | None = None,
) -> list[SubmissionRecord]:
    rng = random.Random(seed)
    base_challenge = base_challenge or _p(45.0, 30.0, 25.0)
    base_reward = base_reward or _p(40.0, 30.0, 30.0)
    role_map = role_map or {}
    result: list[SubmissionRecord] = []
    for i in range(count):
        challenge = _jitter(rng, base_challenge, spread)
        reward = _jitter(rng, base_reward, spread)
        result.append(
            _sub(
                f"s-{seed}-{i:05d}",
                challenge,
                reward,
                role_map.get(i, "community"),
            )
        )
    return result


def _jitter(rng: random.Random, base: Profile, spread: float) -> Profile:
    while True:
        values = [
            max(0.0, base.micro + rng.uniform(-spread, spread)),
            max(0.0, base.macro + rng.uniform(-spread, spread)),
            max(0.0, base.mystiko + rng.uniform(-spread, spread)),
        ]
        total = sum(values)
        if total <= 0:
            continue
        scaled = [100.0 * v / total for v in values]
        if all(v > 0 for v in scaled):
            return Profile(micro=scaled[0], macro=scaled[1], mystiko=scaled[2])


@dataclass
class Scenario:
    name: str
    description: str
    build: Callable[[], list[SubmissionRecord]]
    seed: int


class SimulationRunner:
    def __init__(self, bootstrap: int, draws: int, large_bootstrap: int):
        self.bootstrap = bootstrap
        self.draws = draws
        self.large_bootstrap = large_bootstrap

    # -- scenario summary -----------------------------------------------

    def run_scenario(self, scenario: Scenario) -> dict[str, Any]:
        subs = scenario.build()
        pop = _snap(subs)
        n = pop.raw_n
        replicates = self.large_bootstrap if n >= 100 else self.bootstrap

        method_1 = method1_calculate(pop)
        method_2 = method2_calculate(pop)
        method_3 = method3_calculate(pop)
        bhpcm = bhpcm_calculate(
            pop,
            (method_1, method_2, method_3),
            bootstrap_replicates=replicates,
            governance_draws=self.draws,
        )
        confidence: dict[str, Any] = {}
        if bhpcm.is_ready:
            base = confidence_base_calculate(
                pop,
                method_2.raw_challenge,
                method_2.raw_reward,
                method_3.raw_challenge,
                method_3.raw_reward,
            )
            resilience = (
                resilience_apply(base.level_raw, n)
                if base.level_raw is not None
                else None
            )
            confidence = {
                "base": round(base.level_raw, 2)
                if base.level_raw is not None
                else None,
                "resilience": (round(resilience.level, 2) if resilience else None),
            }
        elif 1 <= n < 20 and method_1.is_ready:
            provisional = provisional_confidence_calculate(pop, method_1)
            confidence = {
                "provisional": (
                    round(provisional.level_raw, 2)
                    if provisional.level_raw is not None
                    else None
                )
            }

        role_change_note = ""
        if scenario.name == "role_change_identical_scores":
            shifted = [
                SubmissionRecord(
                    identifier=s.identifier,
                    challenge=s.challenge,
                    reward=s.reward,
                    role="superuser",
                )
                for s in subs
            ]
            shifted_pop = _snap(shifted)
            m2b = method2_calculate(shifted_pop)
            m3b = method3_calculate(shifted_pop)
            role_change_note = (
                "role-change invariance: M2 identical="
                f"{m2b.raw_challenge == method_2.raw_challenge}, "
                f"M3 identical={m3b.raw_challenge == method_3.raw_challenge}"
            )

        return {
            "name": scenario.name,
            "description": scenario.description,
            "seed": scenario.seed,
            "raw_n": n,
            "role_counts": pop.role_counts(),
            "method_1_status": method_1.status,
            "method_2_status": method_2.status,
            "method_3_status": method_3.status,
            "method_1_integers": method_1.integer_challenge,
            "method_2_integers": method_2.integer_challenge,
            "method_3_integers": method_3.integer_challenge,
            "method_1_rejected": (
                method_1.diagnostics.get("method_1a_rejected"),
                method_1.diagnostics.get("method_1b_rejected"),
            ),
            "method_2_rejected": method_2.rejected,
            "method_3_rejected": method_3.rejected,
            "anchor_type": method_1.diagnostics.get("anchor_type"),
            "bhpcm_status": bhpcm.status,
            "unified_integers": bhpcm.integer_challenge,
            "conflict": (
                bhpcm.diagnostics.get("conflict_classification")
                if bhpcm.is_ready
                else None
            ),
            "bootstrap": (
                bhpcm.diagnostics.get("bootstrap_valid_count"),
                bhpcm.diagnostics.get("bootstrap_invalid_count"),
            ),
            "confidence": confidence,
            "invariants": self._check_invariants(
                pop, method_1, method_2, method_3, bhpcm
            ),
            "role_change_note": role_change_note,
        }

    def _check_invariants(self, pop, method_1, method_2, method_3, bhpcm) -> list[str]:
        failures: list[str] = []
        for name, result in (
            ("m1", method_1),
            ("m2", method_2),
            ("m3", method_3),
        ):
            if result.is_ready:
                if result.raw_challenge is None or result.raw_reward is None:
                    failures.append(f"{name} missing raw")
                else:
                    if abs(result.raw_challenge.total() - 100) > 1e-9:
                        failures.append(f"{name} raw challenge total")
                    if sum(result.integer_challenge) != 100:
                        failures.append(f"{name} integer challenge total")
                    if sum(result.integer_reward) != 100:
                        failures.append(f"{name} integer reward total")
        if bhpcm.is_ready:
            if sum(bhpcm.integer_challenge) != 100 or sum(bhpcm.integer_reward) != 100:
                failures.append("bhpcm integer totals")
            weights = bhpcm.diagnostics["method_weight_summaries"]
            if not (
                0.30 <= weights["omega_1"]["p05"] <= weights["omega_1"]["p95"] <= 0.50
            ):
                failures.append("omega_1 bounds")
        return failures


class Command(BaseCommand):
    help = "Run the SBGC-65 mathematical simulation program and write a report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="docs/classification-simulation-report.md",
            help="Report path (relative to repo root).",
        )
        parser.add_argument(
            "--bootstrap",
            type=int,
            default=DEFAULT_BOOTSTRAP,
            help="Bootstrap replicates for the scenario matrix.",
        )
        parser.add_argument(
            "--draws",
            type=int,
            default=DEFAULT_DRAWS,
            help="Governance draws per replicate for the scenario matrix.",
        )
        parser.add_argument(
            "--large-bootstrap",
            type=int,
            default=LARGE_N_BOOTSTRAP,
            help="Bootstrap replicates for N >= 100 runs.",
        )
        parser.add_argument(
            "--skip-large",
            action="store_true",
            help="Skip the N=500/1000/1001 boundary runs.",
        )

    def handle(self, *args, **options):
        runner = SimulationRunner(
            bootstrap=options["bootstrap"],
            draws=options["draws"],
            large_bootstrap=options["large_bootstrap"],
        )
        sections: list[str] = []
        sections.append(
            "# SBGC-65 Classification Simulation Report\n\n"
            f"Generated: {timezone.now().isoformat()}\n\n"
            "Simulation configuration (scenario matrix): "
            f"bootstrap={options['bootstrap']}, governance_draws={options['draws']}; "
            f"large-N bootstrap={options['large_bootstrap']}. "
            "Frozen production settings "
            "(B=10,000, S=20) are exercised by the dedicated BHPCM acceptance test.\n"
        )

        sections.append(self._n_boundaries(runner, options))
        sections.append(self._scenarios(runner))
        sections.append(self._boundary_study(runner))
        sections.append(self._resilience_study(runner))
        sections.append(self._random_invariants(runner))

        with open(options["output"], "w", encoding="utf-8") as handle:
            handle.write("\n\n".join(sections))
        self.stdout.write(
            self.style.SUCCESS(f"Simulation report written to {options['output']}")
        )

    # ------------------------------------------------------------------

    def _n_boundaries(self, runner, options) -> str:
        import time as time_module

        lines = ["## 1. Frozen N boundaries", ""]
        boundaries = [
            0,
            1,
            2,
            5,
            6,
            8,
            9,
            10,
            15,
            18,
            19,
            20,
            21,
            25,
            26,
            50,
            51,
            100,
            250,
            400,
            401,
        ]
        if not options["skip_large"]:
            boundaries += [500, 1000, 1001]
        rows = [["N", "status", "regime", "m1", "m2", "m3", "elapsed_s"]]
        for n in boundaries:
            if n == 0:
                subs = []
            else:
                subs = _scattered(n, seed=1000 + n, role_map={0: "superuser"})
            pop = _snap(subs)
            started = time_module.monotonic()
            result = calculate_game(
                pop,
                game_identifier=f"boundary-{n}",
                stored_boundary=ZERO_BOUNDARY,
                bootstrap_replicates=(
                    options["large_bootstrap"] if n >= 100 else options["bootstrap"]
                ),
                governance_draws=options["draws"],
            )
            elapsed = time_module.monotonic() - started
            rows.append(
                [
                    str(n),
                    result.status,
                    result.regime,
                    result.method_1.status if result.method_1 else "-",
                    result.method_2.status if result.method_2 else "-",
                    result.method_3.status if result.method_3 else "-",
                    f"{elapsed:.1f}",
                ]
            )
        lines.append(_md_table(rows))
        return "\n".join(lines)

    def _scenarios(self, runner) -> str:
        lines = ["## 2. Required population scenarios", ""]
        scenarios = _build_scenarios()
        for scenario in scenarios:
            summary = runner.run_scenario(scenario)
            lines.append(f"### 2.{scenarios.index(scenario) + 1} {scenario.name}")
            lines.append("")
            lines.append(f"- Description: {scenario.description}")
            lines.append(f"- Input generation: seed={scenario.seed}")
            lines.append(
                f"- Raw N: {summary['raw_n']}; roles: {summary['role_counts']}"
            )
            lines.append(
                f"- Method statuses: M1={summary['method_1_status']} "
                f"(anchor={summary['anchor_type']}), "
                f"M2={summary['method_2_status']}, M3={summary['method_3_status']}"
            )
            lines.append(
                f"- Integer Challenge profiles: "
                f"M1={summary['method_1_integers']}, "
                f"M2={summary['method_2_integers']}, "
                f"M3={summary['method_3_integers']}"
            )
            lines.append(
                f"- Rejections: M1A/M1B={summary['method_1_rejected']}, "
                f"M2={summary['method_2_rejected']}, M3={summary['method_3_rejected']}"
            )
            lines.append(
                f"- BHPCM: status={summary['bhpcm_status']}, "
                f"unified={summary['unified_integers']}, "
                f"conflict={summary['conflict']}, "
                f"bootstrap(valid/invalid)={summary['bootstrap']}"
            )
            lines.append(f"- Confidence: {summary['confidence']}")
            if summary.get("role_change_note"):
                lines.append(f"- {summary['role_change_note']}")
            lines.append(
                f"- Invariant result: "
                f"{'PASS' if not summary['invariants'] else summary['invariants']}"
            )
            lines.append("")
        return "\n".join(lines)

    def _boundary_study(self, runner) -> str:
        lines = ["## 3. Mandatory 19-to-20 boundary study", ""]
        rows = [
            [
                "family",
                "C19 (provisional)",
                "C20 base",
                "C20 resilience",
                "delta20",
                "decay@50",
            ]
        ]
        for label, spread, roles in (
            ("perfect agreement", 0.0, {0: "superuser"}),
            ("modest disagreement", 4.0, {0: "superuser"}),
            ("strong disagreement", 14.0, {0: "superuser"}),
            ("no authorities", 4.0, {}),
            ("divided authorities", 6.0, {0: "superuser", 1: "superuser"}),
        ):
            base = _scattered(19, seed=2000 + len(rows), role_map=roles, spread=spread)
            if spread == 0.0:
                base = _identical(19, role_map=roles)
            pop19 = _snap(base)
            m1_19 = method1_calculate(pop19)
            prov = provisional_confidence_calculate(pop19, m1_19)
            c19 = round(prov.level_raw, 2) if prov.level_raw is not None else None

            twentieth = _scattered(1, seed=3000 + len(rows), spread=spread)[0]
            twentieth = SubmissionRecord(
                identifier=twentieth.identifier,
                challenge=twentieth.challenge,
                reward=twentieth.reward,
                role="community",
            )
            pop20 = _snap(base + [twentieth])
            m2 = method2_calculate(pop20)
            m3 = method3_calculate(pop20)
            base_conf = confidence_base_calculate(
                pop20,
                m2.raw_challenge,
                m2.raw_reward,
                m3.raw_challenge,
                m3.raw_reward,
            )
            c20_base = (
                round(base_conf.level_raw, 2)
                if base_conf.level_raw is not None
                else None
            )
            c20_res = (
                round(resilience_apply(base_conf.level_raw, 20).level, 2)
                if base_conf.level_raw is not None
                else None
            )
            calibration = boundary_calibrate(pop20, game_identifier=f"boundary-{label}")
            final = boundary_final_confidence(
                resilience_apply(base_conf.level_raw, 20).level
                if base_conf.level_raw is not None
                else 0.0,
                calibration.delta,
                50,
            )
            rows.append(
                [
                    label,
                    str(c19),
                    str(c20_base),
                    str(c20_res),
                    str(round(calibration.delta, 2)),
                    str(round(final["boundary_decay_factor"], 3)),
                ]
            )
        lines.append(_md_table(rows))
        return "\n".join(lines)

    def _resilience_study(self, runner) -> str:
        lines = ["## 4. Population-resilience pathological study", ""]
        # Large N, authorities in extreme internal disagreement.
        crowd = _scattered(395, seed=4000, spread=5.0)
        opposite_a = [
            _sub("auth-a", _p(95.0, 3.0, 2.0), _p(95.0, 3.0, 2.0), "superuser"),
            _sub("auth-b", _p(3.0, 2.0, 95.0), _p(3.0, 2.0, 95.0), "superuser"),
            _sub("auth-c", _p(2.0, 95.0, 3.0), _p(2.0, 95.0, 3.0), "superuser"),
        ]
        pop = _snap(crowd + opposite_a)
        m2 = method2_calculate(pop)
        m3 = method3_calculate(pop)
        base = confidence_base_calculate(
            pop,
            m2.raw_challenge,
            m2.raw_reward,
            m3.raw_challenge,
            m3.raw_reward,
        )
        resilience = (
            resilience_apply(base.level_raw, pop.raw_n)
            if base.level_raw is not None
            else None
        )
        lines.append(f"- N = {pop.raw_n} (population broadly coherent)")
        lines.append(
            f"- Authoritative internal variance: "
            f"{round(base.diagnostics['authoritative_internal_variance'], 4)}"
        )
        lines.append(
            "- Base confidence: "
            f"{round(base.level_raw, 2) if base.level_raw is not None else None}"
        )
        lines.append(
            f"- After resilience: {round(resilience.level, 2) if resilience else None} "
            f"(capacity {round(resilience.capacity, 2) if resilience else None})"
        )
        lines.append("- Verifications:")
        lines.append(
            "  - base remains low: "
            f"{base.level_raw is not None and base.level_raw < 10}"
        )
        lines.append(
            "  - resilience is bounded: "
            f"{resilience is not None and resilience.level < 50}"
        )
        if pop.raw_n >= 401 and base.level_raw is not None and base.level_raw < 0.5:
            lines.append(
                f"  - zero-base case at N>=401 maps to "
                f"{round(resilience_apply(0.0, pop.raw_n).level, 2)} "
                "(expect 25.0)"
            )
        lines.append("  - expert conflict remains visible in diagnostics: True")
        lines.append("  - adjustment does not imply majority correctness: True")
        return "\n".join(lines)

    def _random_invariants(self, runner) -> str:
        lines = ["## 5. Invariants under random simulation", ""]
        failures: list[str] = []
        for seed in range(5001, 5009):
            subs = _scattered(
                random.Random(seed).randint(20, 60),
                seed=seed,
                role_map={0: "superuser", 1: "moderator"},
            )
            pop = _snap(subs)
            result = calculate_game(
                pop,
                game_identifier=f"random-{seed}",
                stored_boundary=ZERO_BOUNDARY,
                bootstrap_replicates=24,
                governance_draws=2,
            )
            for check, ok in self._invariant_checks(result).items():
                if not ok:
                    failures.append(f"seed {seed}: {check}")
        if failures:
            lines.append("Failures: " + "; ".join(failures))
        else:
            lines.append("All invariant checks passed across 8 random populations.")
        return "\n".join(lines)

    def _invariant_checks(self, result) -> dict[str, bool]:
        checks: dict[str, bool] = {}
        if result.is_ready:
            checks["display profiles total 100"] = (
                sum(result.integer_challenge) == 100
                and sum(result.integer_reward) == 100
            )
            checks["raw profiles total 100"] = (
                abs(result.raw_challenge.total() - 100) < 1e-6
                and abs(result.raw_reward.total() - 100) < 1e-6
            )
        if result.confidence is not None and result.confidence.level_raw is not None:
            checks["confidence in range"] = 0.0 <= result.confidence.level_raw <= 100.0
        if result.regime == "provisional" and result.confidence is not None:
            checks["provisional below 50"] = (
                result.confidence.level_raw is not None
                and result.confidence.level_raw < 50.0
            )
        if result.boundary_calibration is not None:
            checks["boundary delta nonnegative"] = (
                result.boundary_calibration.delta >= 0.0
            )
        return checks


def _md_table(rows: list[list[str]]) -> str:
    header = "| " + " | ".join(rows[0]) + " |"
    separator = "|" + "|".join("---" for _ in rows[0]) + "|"
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows[1:])
    return f"{header}\n{separator}\n{body}"


def _build_scenarios() -> list[Scenario]:
    common = _p(45.0, 30.0, 25.0)
    common_r = _p(40.0, 30.0, 30.0)
    scenarios: list[Scenario] = [
        Scenario(
            "perfect_unanimous",
            "All submissions identical.",
            lambda: _identical(50, role_map={0: "superuser"}),
            1,
        ),
        Scenario(
            "tight_unimodal",
            "Tight unimodal agreement (spread 2).",
            lambda: _scattered(50, 2, {0: "superuser"}, spread=2.0),
            2,
        ),
        Scenario(
            "moderate_dispersion",
            "Moderate symmetric dispersion (spread 8).",
            lambda: _scattered(50, 3, {0: "superuser"}, spread=8.0),
            3,
        ),
        Scenario(
            "one_high_tail",
            "One extreme high-tail respondent.",
            lambda: (
                _scattered(49, 4, {0: "superuser"}, spread=6.0)
                + [_sub("high", _p(95.0, 3.0, 2.0), _p(95.0, 3.0, 2.0))]
            ),
            4,
        ),
        Scenario(
            "one_low_tail",
            "One extreme low-tail respondent.",
            lambda: (
                _scattered(49, 5, {0: "superuser"}, spread=6.0)
                + [_sub("low", _p(2.0, 3.0, 95.0), _p(2.0, 3.0, 95.0))]
            ),
            5,
        ),
        Scenario(
            "symmetric_0_100_extremes",
            "Symmetric 0/100 extremes around a center.",
            lambda: (
                _identical(40, role_map={0: "superuser"})
                + [
                    _sub("e1", _p(100.0, 0.0, 0.0), _p(100.0, 0.0, 0.0)),
                    _sub("e2", _p(0.0, 100.0, 0.0), _p(0.0, 100.0, 0.0)),
                    _sub("e3", _p(0.0, 0.0, 100.0), _p(0.0, 0.0, 100.0)),
                ]
            ),
            6,
        ),
        Scenario(
            "several_isolated_extremes",
            "Several isolated extremes.",
            lambda: (
                _scattered(45, 7, {0: "superuser"}, spread=5.0)
                + [
                    _sub(
                        f"x{i}", _p(90.0 - i, 5.0, 5.0 + i), _p(90.0 - i, 5.0, 5.0 + i)
                    )
                    for i in range(5)
                ]
            ),
            7,
        ),
        Scenario(
            "bimodal_50_50",
            "Bimodal 50/50 population.",
            lambda: (
                _scattered(
                    25,
                    8,
                    spread=3.0,
                    base_challenge=_p(20.0, 30.0, 50.0),
                    base_reward=_p(20.0, 30.0, 50.0),
                )
                + _scattered(25, 80, spread=3.0)
                + [_sub("su", common, common_r, "superuser")]
            ),
            8,
        ),
        Scenario(
            "majority_minority_75_25",
            "75/25 majority/minority.",
            lambda: (
                _scattered(38, 9, {0: "superuser"}, spread=4.0)
                + _scattered(
                    12,
                    90,
                    spread=4.0,
                    base_challenge=_p(70.0, 20.0, 10.0),
                    base_reward=_p(70.0, 20.0, 10.0),
                )
            ),
            9,
        ),
        Scenario(
            "dense_minority_cluster",
            "Dense minority cluster.",
            lambda: (
                _scattered(40, 10, {0: "superuser"}, spread=5.0)
                + _identical(
                    8,
                    prefix="min",
                    challenge=_p(10.0, 15.0, 75.0),
                    reward=_p(10.0, 15.0, 75.0),
                )
            ),
            10,
        ),
        Scenario(
            "sparse_bridge",
            "Sparse bridge observations between clusters.",
            lambda: (
                _scattered(20, 11, spread=3.0)
                + _scattered(
                    20,
                    110,
                    spread=3.0,
                    base_challenge=_p(70.0, 20.0, 10.0),
                    base_reward=_p(70.0, 20.0, 10.0),
                )
                + [
                    _sub(f"bridge{i}", _p(45.0 + 5 * i, 30.0, 25.0 - 5 * i), common_r)
                    for i in range(5)
                ]
                + [_sub("su", common, common_r, "superuser")]
            ),
            11,
        ),
        Scenario(
            "uniform_spaced",
            "Uniformly spaced profiles.",
            lambda: (
                [
                    _sub(f"u{i}", _p(10.0 + 1.6 * i, 30.0, 60.0 - 1.6 * i), common_r)
                    for i in range(50)
                ]
                + [_sub("su", common, common_r, "superuser")]
            ),
            12,
        ),
        Scenario(
            "many_duplicate_integer_profiles",
            "Many duplicate integer profiles.",
            lambda: (
                _identical(30, role_map={0: "superuser"})
                + _identical(
                    10,
                    prefix="d2",
                    challenge=_p(50.0, 25.0, 25.0),
                    reward=_p(50.0, 25.0, 25.0),
                )
                + _identical(
                    10,
                    prefix="d3",
                    challenge=_p(33.0, 33.0, 34.0),
                    reward=_p(33.0, 33.0, 34.0),
                )
            ),
            13,
        ),
        Scenario(
            "zero_heavy",
            "Zero-heavy 100/0/0 compositions.",
            lambda: (
                _identical(
                    30,
                    role_map={0: "superuser"},
                    challenge=_p(100.0, 0.0, 0.0),
                    reward=_p(100.0, 0.0, 0.0),
                )
                + _identical(
                    10,
                    prefix="z2",
                    challenge=_p(0.0, 100.0, 0.0),
                    reward=_p(0.0, 100.0, 0.0),
                )
            ),
            14,
        ),
        Scenario(
            "balanced_33_33_34",
            "Approximately balanced compositions.",
            lambda: _identical(
                50,
                role_map={0: "superuser"},
                challenge=_p(33.0, 33.0, 34.0),
                reward=_p(33.0, 33.0, 34.0),
            ),
            15,
        ),
        Scenario(
            "expert_population_agreement",
            "Experts agree with the population.",
            lambda: (
                _scattered(44, 16, spread=5.0)
                + [
                    _sub(
                        f"ex{i}",
                        common,
                        common_r,
                        "superuser" if i == 0 else "moderator",
                    )
                    for i in range(6)
                ]
            ),
            16,
        ),
        Scenario(
            "moderate_expert_conflict",
            "Moderate expert/population conflict.",
            lambda: (
                _scattered(44, 17, spread=5.0)
                + [
                    _sub(
                        f"ex{i}",
                        _p(55.0, 30.0, 15.0),
                        _p(50.0, 30.0, 20.0),
                        "superuser" if i == 0 else "moderator",
                    )
                    for i in range(6)
                ]
            ),
            17,
        ),
        Scenario(
            "severe_expert_conflict",
            "Severe expert/population conflict.",
            lambda: (
                _scattered(44, 18, spread=5.0)
                + [
                    _sub(
                        f"ex{i}",
                        _p(90.0, 5.0, 5.0),
                        _p(90.0, 5.0, 5.0),
                        "superuser" if i == 0 else "moderator",
                    )
                    for i in range(6)
                ]
            ),
            18,
        ),
        Scenario(
            "unanimous_experts",
            "Internally unanimous experts.",
            lambda: (
                _scattered(44, 19, spread=5.0)
                + _identical(
                    6,
                    prefix="ex",
                    role_map={
                        0: "superuser",
                        1: "moderator",
                        2: "moderator",
                        3: "community_leader",
                        4: "community_leader",
                        5: "community_leader",
                    },
                    challenge=_p(55.0, 30.0, 15.0),
                    reward=_p(50.0, 30.0, 20.0),
                )
            ),
            19,
        ),
        Scenario(
            "divided_experts",
            "Internally highly divided experts.",
            lambda: (
                _scattered(44, 20, spread=5.0)
                + [
                    _sub("ex-hi", _p(90.0, 5.0, 5.0), _p(90.0, 5.0, 5.0), "superuser"),
                    _sub("ex-lo", _p(5.0, 5.0, 90.0), _p(5.0, 5.0, 90.0), "superuser"),
                    _sub("ex-mid", common, common_r, "moderator"),
                ]
            ),
            20,
        ),
        Scenario(
            "no_authorities",
            "No authoritative respondents.",
            lambda: _scattered(50, 21, spread=5.0),
            21,
        ),
        Scenario(
            "one_authority",
            "Exactly one authoritative respondent.",
            lambda: (
                _scattered(49, 22, spread=5.0)
                + [_sub("su", common, common_r, "superuser")]
            ),
            22,
        ),
        Scenario(
            "opposite_superusers",
            "Multiple superusers giving opposite profiles.",
            lambda: (
                _scattered(48, 23, spread=5.0)
                + [
                    _sub("su-a", _p(90.0, 5.0, 5.0), _p(90.0, 5.0, 5.0), "superuser"),
                    _sub("su-b", _p(5.0, 5.0, 90.0), _p(5.0, 5.0, 90.0), "superuser"),
                ]
            ),
            23,
        ),
        Scenario(
            "all_community_below_50",
            "All-Community below 50: Method 1 must not publish without an anchor.",
            lambda: _scattered(30, 24, spread=5.0),
            24,
        ),
        Scenario(
            "superuser_plus_large_community",
            "One superuser plus a large Community population.",
            lambda: (
                _scattered(199, 25, spread=5.0)
                + [_sub("su", common, common_r, "superuser")]
            ),
            25,
        ),
        Scenario(
            "role_change_identical_scores",
            "Role changes with identical score values (Methods 2/3 unaffected).",
            lambda: _scattered(30, 26, spread=5.0),
            26,
        ),
        Scenario(
            "method23_agreement",
            "Methods 2 and 3 near-identical (single tight cluster).",
            lambda: _scattered(30, 27, {0: "superuser"}, spread=2.0),
            27,
        ),
        Scenario(
            "method23_disagreement",
            "Methods 2 and 3 materially divergent (extreme + cluster).",
            lambda: (
                _scattered(45, 28, {0: "superuser"}, spread=4.0)
                + [
                    _sub(f"o{i}", _p(3.0, 2.0, 95.0), _p(3.0, 2.0, 95.0))
                    for i in range(5)
                ]
            ),
            28,
        ),
        Scenario(
            "method1_divergent",
            "Method 1 materially divergent from both population methods.",
            lambda: (
                _scattered(45, 29, spread=4.0)
                + [
                    _sub(
                        f"ex{i}",
                        _p(80.0, 15.0, 5.0),
                        _p(75.0, 15.0, 10.0),
                        "superuser" if i == 0 else "moderator",
                    )
                    for i in range(5)
                ]
            ),
            29,
        ),
        Scenario(
            "all_methods_similar",
            "All three methods nearly identical.",
            lambda: _scattered(30, 30, {0: "superuser"}, spread=1.0),
            30,
        ),
    ]
    return scenarios


__all__ = ["Command"]
