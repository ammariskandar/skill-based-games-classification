/**
 * Live questionnaire radar bridge — SBGC-179.
 *
 * The `QuestionnaireRadar` Astro component renders a static SVG shell once; this
 * DOM-free-of-framework controller subscribes to the `questionnaire:*` window
 * events emitted by `QuestionnaireRoot` and mutates vertex coordinates and
 * `<path d>` attributes in place, so every answer re-shapes the chart without
 * an Astro re-render.
 *
 * Profile visibility is phase-driven:
 *
 * - AESTHETICS → neutral empty grid (nothing plotted).
 * - CHALLENGE  → challenge polygon only.
 * - REWARD     → reward polygon only.
 * - REVIEW_Q15 → both overlaid, a segmented toggle picks the active layer, and
 *                the active layer's pinned normalized benchmark is drawn
 *                desaturated behind its live adjusted polygon.
 *
 * Geometry is delegated to the shared `radar-geometry` helpers so the
 * questionnaire chart uses the exact same six canonical spokes as every other
 * radar in the product.
 */

import {
  SPOKES,
  generateSplinePath,
  getSpokeAngle,
  polarToCartesian,
  type Point,
} from "../radar-geometry";
import {
  VERTEX_COLOR,
  polygonIsDegenerate,
  vertexGradientAxis,
} from "../radar-render";
import {
  DIMENSIONS,
  type DimensionId,
  type SkillProfileKind,
  type SkillProfileVector,
} from "../skill-dimensions";

export type QuestionnaireRadarProfile = "CHALLENGE" | "REWARD";

export type QuestionnaireRadarPhase =
  | "AESTHETICS"
  | "CHALLENGE"
  | "REWARD"
  | "REVIEW_Q15"
  | "SUBMITTING"
  | "COMPLETED";

export interface QuestionnaireScoreUpdateDetail {
  profile: QuestionnaireRadarProfile;
  raw?: SkillProfileVector;
  normalized: SkillProfileVector;
  adjusted?: SkillProfileVector;
  /** Softened, progress-blended vector for the live preview (phases 2–3). */
  live?: SkillProfileVector;
}

export interface QuestionnaireBoundarySwapDetail {
  targetProfile: QuestionnaireRadarProfile;
}

export interface QuestionnairePhaseChangeDetail {
  phase: QuestionnaireRadarPhase;
}

export const QUESTIONNAIRE_RADAR_EVENTS = {
  challengeUpdate: "questionnaire:challenge-update",
  rewardUpdate: "questionnaire:reward-update",
  boundarySwap: "questionnaire:boundary-swap",
  phaseChange: "questionnaire:phase-change",
} as const;

const PROFILE_KIND: Record<QuestionnaireRadarProfile, SkillProfileKind> = {
  CHALLENGE: "challenge",
  REWARD: "reward",
};

/** Opacity of the non-active polygon while both are overlaid in Phase 4. */
const DUAL_INACTIVE_OPACITY = 0.2;

interface ProfileState {
  normalized: SkillProfileVector;
  adjusted: SkillProfileVector;
  live: SkillProfileVector;
}

const ZERO: SkillProfileVector = { micro: 0, mystiko: 0, macro: 0 };

function clampScore(value: unknown): number {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(100, numeric));
}

function sanitizeVector(
  input?: Partial<SkillProfileVector> | null,
): SkillProfileVector {
  return {
    micro: clampScore(input?.micro),
    mystiko: clampScore(input?.mystiko),
    macro: clampScore(input?.macro),
  };
}

function fmt(value: number): string {
  return String(Math.round(value * 10) / 10);
}

/** DOM handles for one profile's polygon: stroke, clip, and gradient fill. */
interface ProfileLayerRefs {
  group: SVGGElement | null;
  stroke: SVGPathElement | null;
  clipPath: SVGPathElement | null;
  fillPaths: SVGPathElement[];
  gradients: SVGLinearGradientElement[];
  dimensions: readonly DimensionId[];
}

function buildProfileLayer(
  container: HTMLElement,
  kind: SkillProfileKind,
): ProfileLayerRefs {
  return {
    group: container.querySelector<SVGGElement>(`.q-radar-layer--${kind}`),
    stroke: container.querySelector<SVGPathElement>(`.radar-polygon--${kind}`),
    clipPath: container.querySelector<SVGPathElement>(`.q-radar-clip--${kind}`),
    fillPaths: Array.from(
      container.querySelectorAll<SVGPathElement>(`.q-radar-fill--${kind}`),
    ),
    gradients: Array.from(
      container.querySelectorAll<SVGLinearGradientElement>(
        `linearGradient[id^="q-radar-grad-${kind}-"]`,
      ),
    ),
    dimensions: SPOKES.filter((spoke) => spoke.kind === kind).map(
      (spoke) => spoke.dimension,
    ),
  };
}

export class RadarLiveBridge {
  private readonly container: HTMLElement;
  private readonly center: Point;
  private readonly maxRadius: number;

  private readonly layers: Record<QuestionnaireRadarProfile, ProfileLayerRefs>;
  private readonly rawBenchmarkPath: SVGPathElement | null;
  private readonly toggleContainer: HTMLElement | null;
  private readonly toggleButtons: HTMLButtonElement[];
  private readonly vertexNodes: SVGCircleElement[];
  private readonly axisLabels: SVGTextElement[];

  private readonly challengeState: ProfileState = {
    normalized: { ...ZERO },
    adjusted: { ...ZERO },
    live: { ...ZERO },
  };
  private readonly rewardState: ProfileState = {
    normalized: { ...ZERO },
    adjusted: { ...ZERO },
    live: { ...ZERO },
  };

  private activeProfile: QuestionnaireRadarProfile = "CHALLENGE";
  private phase: QuestionnaireRadarPhase = "AESTHETICS";

  constructor(container: HTMLElement, size = 320) {
    this.container = container;

    const svg = container.querySelector<SVGSVGElement>(".radar-chart__svg");
    if (!svg) throw new Error("Radar SVG element not found");

    this.center = { x: size / 2, y: size / 2 };
    this.maxRadius = size / 2 - 56; // 56px label/glow margin

    this.layers = {
      CHALLENGE: buildProfileLayer(container, "challenge"),
      REWARD: buildProfileLayer(container, "reward"),
    };
    this.rawBenchmarkPath = container.querySelector<SVGPathElement>(
      ".radar-polygon--raw-benchmark",
    );
    this.toggleContainer = container.querySelector<HTMLElement>(
      ".radar-toggle-group",
    );
    this.toggleButtons = Array.from(
      container.querySelectorAll<HTMLButtonElement>("[data-toggle-target]"),
    );
    this.vertexNodes = Array.from(
      container.querySelectorAll<SVGCircleElement>("[data-node-profile]"),
    );
    this.axisLabels = Array.from(
      container.querySelectorAll<SVGTextElement>(".radar-axis-label"),
    );

    this.bindEvents();
    this.applyPhase();
  }

  /** Swap a profile's plotted polygon to a fresh normalized/adjusted snapshot. */
  public updateProfile(
    profile: QuestionnaireRadarProfile,
    normalized: SkillProfileVector,
    adjusted?: SkillProfileVector,
    live?: SkillProfileVector,
  ): void {
    const state = this.stateFor(profile);
    state.normalized = sanitizeVector(normalized);
    state.adjusted = sanitizeVector(adjusted ?? normalized);
    state.live = sanitizeVector(live ?? adjusted ?? normalized);

    this.renderAdjusted(profile);
    if (this.isDualPhase() && this.activeProfile === profile) {
      this.renderRawBenchmark(profile);
    }
  }

  /** Pin a profile's desaturated benchmark to its normalized vector. */
  public setRawBenchmark(
    profile: QuestionnaireRadarProfile,
    normalized: SkillProfileVector,
  ): void {
    const state = this.stateFor(profile);
    state.normalized = sanitizeVector(normalized);
    if (this.isDualPhase() && this.activeProfile === profile) {
      this.renderRawBenchmark(profile);
    }
  }

  /** Detach every listener (component teardown / unit-test hygiene). */
  public destroy(): void {
    window.removeEventListener(
      QUESTIONNAIRE_RADAR_EVENTS.challengeUpdate,
      this.onChallengeUpdate,
    );
    window.removeEventListener(
      QUESTIONNAIRE_RADAR_EVENTS.rewardUpdate,
      this.onRewardUpdate,
    );
    window.removeEventListener(
      QUESTIONNAIRE_RADAR_EVENTS.boundarySwap,
      this.onBoundarySwap,
    );
    window.removeEventListener(
      QUESTIONNAIRE_RADAR_EVENTS.phaseChange,
      this.onPhaseChange,
    );
    this.toggleContainer?.removeEventListener("click", this.onToggleClick);
  }

  // ── event wiring ──

  private bindEvents(): void {
    window.addEventListener(
      QUESTIONNAIRE_RADAR_EVENTS.challengeUpdate,
      this.onChallengeUpdate,
    );
    window.addEventListener(
      QUESTIONNAIRE_RADAR_EVENTS.rewardUpdate,
      this.onRewardUpdate,
    );
    window.addEventListener(
      QUESTIONNAIRE_RADAR_EVENTS.boundarySwap,
      this.onBoundarySwap,
    );
    window.addEventListener(
      QUESTIONNAIRE_RADAR_EVENTS.phaseChange,
      this.onPhaseChange,
    );
    this.toggleContainer?.addEventListener("click", this.onToggleClick);
  }

  private readonly onChallengeUpdate = (event: Event): void => {
    const detail = (event as CustomEvent<QuestionnaireScoreUpdateDetail>)
      .detail;
    if (!detail) return;
    this.updateProfile(
      "CHALLENGE",
      detail.normalized,
      detail.adjusted,
      detail.live,
    );
  };

  private readonly onRewardUpdate = (event: Event): void => {
    const detail = (event as CustomEvent<QuestionnaireScoreUpdateDetail>)
      .detail;
    if (!detail) return;
    this.updateProfile(
      "REWARD",
      detail.normalized,
      detail.adjusted,
      detail.live,
    );
  };

  private readonly onBoundarySwap = (event: Event): void => {
    const detail = (event as CustomEvent<QuestionnaireBoundarySwapDetail>)
      .detail;
    const target = detail?.targetProfile ?? "REWARD";
    // A boundary swap moves the live phase to the newly-mounted profile; the
    // event doubles as the crossfade trigger for the CHALLENGE → REWARD handoff.
    this.phase = target;
    this.applyPhase();
  };

  private readonly onPhaseChange = (event: Event): void => {
    const detail = (event as CustomEvent<QuestionnairePhaseChangeDetail>)
      .detail;
    if (!detail?.phase) return;
    this.phase = detail.phase;
    this.applyPhase();
  };

  private readonly onToggleClick = (event: Event): void => {
    const button = (
      event.target as HTMLElement | null
    )?.closest<HTMLButtonElement>("[data-toggle-target]");
    const target = button?.dataset.toggleTarget;
    if (target !== "challenge" && target !== "reward") return;
    this.setActiveProfile(target === "challenge" ? "CHALLENGE" : "REWARD");
  };

  // ── rendering ──

  private stateFor(profile: QuestionnaireRadarProfile): ProfileState {
    return profile === "CHALLENGE" ? this.challengeState : this.rewardState;
  }

  private isDualPhase(): boolean {
    return (
      this.phase === "REVIEW_Q15" ||
      this.phase === "SUBMITTING" ||
      this.phase === "COMPLETED"
    );
  }

  /** The vector a profile is currently plotted with. */
  private plotVector(profile: QuestionnaireRadarProfile): SkillProfileVector {
    const state = this.stateFor(profile);
    return this.isDualPhase() ? state.adjusted : state.live;
  }

  private applyPhase(): void {
    if (this.phase === "AESTHETICS") {
      this.setOpacity("CHALLENGE", 0);
      this.setOpacity("REWARD", 0);
      this.showRawBenchmark(false);
      this.showToggle(false);
    } else if (this.phase === "CHALLENGE") {
      this.activeProfile = "CHALLENGE";
      this.setOpacity("CHALLENGE", 1);
      this.setOpacity("REWARD", 0);
      this.showRawBenchmark(false);
      this.showToggle(false);
    } else if (this.phase === "REWARD") {
      this.activeProfile = "REWARD";
      this.setOpacity("CHALLENGE", 0);
      this.setOpacity("REWARD", 1);
      this.showRawBenchmark(false);
      this.showToggle(false);
    } else {
      this.showToggle(true);
      this.applyDualLayer();
    }
    this.refreshPolygons();
    this.applyNodeVisibility();
    this.updateLabels();
    this.syncToggle();
  }

  /** Re-plot the polygons for the current phase (soft live vs. accurate Q15). */
  private refreshPolygons(): void {
    if (this.phase === "CHALLENGE") {
      this.renderAdjusted("CHALLENGE");
    } else if (this.phase === "REWARD") {
      this.renderAdjusted("REWARD");
    } else if (this.isDualPhase()) {
      this.renderAdjusted("CHALLENGE");
      this.renderAdjusted("REWARD");
    }
  }

  private applyDualLayer(): void {
    this.setOpacity(
      "CHALLENGE",
      this.activeProfile === "CHALLENGE" ? 1 : DUAL_INACTIVE_OPACITY,
    );
    this.setOpacity(
      "REWARD",
      this.activeProfile === "REWARD" ? 1 : DUAL_INACTIVE_OPACITY,
    );
    this.renderRawBenchmark(this.activeProfile);
    this.showRawBenchmark(true);
  }

  private setActiveProfile(profile: QuestionnaireRadarProfile): void {
    this.activeProfile = profile;
    if (this.isDualPhase()) {
      this.applyDualLayer();
    }
    this.applyNodeVisibility();
    this.updateLabels();
    this.syncToggle();
  }

  private renderAdjusted(profile: QuestionnaireRadarProfile): void {
    const layer = this.layers[profile];
    const kind = PROFILE_KIND[profile];
    const vector = this.plotVector(profile);
    const points = this.outlinePoints(profile, vector);
    const spline = generateSplinePath(points);

    layer.stroke?.setAttribute("d", spline);
    layer.clipPath?.setAttribute("d", spline);

    const colored = points.map((point, index) => ({
      ...point,
      color: VERTEX_COLOR[layer.dimensions[index]],
    }));
    if (!polygonIsDegenerate(colored)) {
      for (const fill of layer.fillPaths) fill.setAttribute("d", spline);
      layer.gradients.forEach((gradient, index) => {
        const axis = vertexGradientAxis(
          colored[index],
          colored[(index + 1) % 3],
          colored[(index + 2) % 3],
        );
        gradient.setAttribute("x1", fmt(axis.x1));
        gradient.setAttribute("y1", fmt(axis.y1));
        gradient.setAttribute("x2", fmt(axis.x2));
        gradient.setAttribute("y2", fmt(axis.y2));
      });
    }

    this.updateVertexNodes(kind, layer.dimensions, points, vector);
  }

  private renderRawBenchmark(profile: QuestionnaireRadarProfile): void {
    if (!this.rawBenchmarkPath) return;
    const points = this.outlinePoints(
      profile,
      this.stateFor(profile).normalized,
    );
    this.rawBenchmarkPath.setAttribute("d", generateSplinePath(points));
  }

  /** Points for a profile's three vertices, in spoke order. */
  private outlinePoints(
    profile: QuestionnaireRadarProfile,
    vector: SkillProfileVector,
  ): Point[] {
    const kind = PROFILE_KIND[profile];
    return this.layers[profile].dimensions.map((dimension) =>
      polarToCartesian(
        this.center.x,
        this.center.y,
        (vector[dimension] / 100) * this.maxRadius,
        getSpokeAngle(kind, dimension),
      ),
    );
  }

  private updateVertexNodes(
    kind: SkillProfileKind,
    dimensions: readonly DimensionId[],
    points: Point[],
    vector: SkillProfileVector,
  ): void {
    dimensions.forEach((dimension, index) => {
      const node = this.container.querySelector<SVGCircleElement>(
        `.radar-node--${kind}-${dimension}`,
      );
      const point = points[index];
      if (!node || !point) return;
      node.setAttribute("cx", String(point.x));
      node.setAttribute("cy", String(point.y));
      node.dataset.score = String(vector[dimension]);
      const title = node.querySelector("title");
      if (title) {
        const profileLabel = kind === "challenge" ? "Challenge" : "Reward";
        title.textContent = `${profileLabel} ${DIMENSIONS[dimension].label}: ${vector[dimension]}`;
      }
    });
  }

  private applyNodeVisibility(): void {
    for (const node of this.vertexNodes) {
      const kind = node.dataset.nodeProfile;
      let opacity = 0;
      if (this.phase === "CHALLENGE") {
        opacity = kind === "challenge" ? 1 : 0;
      } else if (this.phase === "REWARD") {
        opacity = kind === "reward" ? 1 : 0;
      } else if (this.isDualPhase()) {
        opacity =
          kind === this.activeProfile.toLowerCase() ? 1 : DUAL_INACTIVE_OPACITY;
      }
      node.style.opacity = String(opacity);
    }
  }

  /** Emphasise the active profile's spoke labels, mirroring the slug radar. */
  private updateLabels(): void {
    const activeKind =
      this.phase === "AESTHETICS" ? null : this.activeProfile.toLowerCase();
    for (const label of this.axisLabels) {
      label.classList.toggle(
        "radar-axis-label--active",
        label.dataset.profile === activeKind,
      );
    }
  }

  private setOpacity(
    profile: QuestionnaireRadarProfile,
    opacity: number,
  ): void {
    const layer = this.layers[profile];
    const target = layer.group ?? layer.stroke;
    if (target) target.style.opacity = String(opacity);
  }

  private showRawBenchmark(visible: boolean): void {
    if (this.rawBenchmarkPath) {
      this.rawBenchmarkPath.style.display = visible ? "block" : "none";
    }
  }

  private showToggle(visible: boolean): void {
    if (this.toggleContainer) {
      this.toggleContainer.style.display = visible ? "flex" : "none";
    }
  }

  private syncToggle(): void {
    for (const button of this.toggleButtons) {
      const pressed =
        button.dataset.toggleTarget === this.activeProfile.toLowerCase();
      button.setAttribute("aria-pressed", String(pressed));
      button.classList.toggle("is-active", pressed);
    }
  }
}
