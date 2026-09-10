// @vitest-environment jsdom
/**
 * Unit tests for the live questionnaire radar bridge (SBGC-179).
 *
 * The bridge mutates a static SVG shell in response to `questionnaire:*` window
 * events, so these tests mount a minimal real DOM and drive it through the
 * phase matrix, the boundary swap, the Q15 dual-layer/raw-benchmark state, and
 * the vertex-anchored barycentric fill.
 */
import { afterEach, describe, expect, it } from "vitest";

import {
  QUESTIONNAIRE_RADAR_EVENTS,
  RadarLiveBridge,
  type QuestionnaireBoundarySwapDetail,
  type QuestionnairePhaseChangeDetail,
  type QuestionnaireScoreUpdateDetail,
} from "../radar-live-bridge";

const SIZE = 320;

function buildNodeMarkup(): string {
  return ["micro", "mystiko", "macro"]
    .flatMap((dimension) =>
      ["challenge", "reward"].map(
        (profile) =>
          `<circle class="radar-node--${profile}-${dimension}" data-node-profile="${profile}" data-node-dimension="${dimension}" r="4.5"><title></title></circle>`,
      ),
    )
    .join("");
}

function buildLabelMarkup(): string {
  return ["challenge", "reward"]
    .flatMap((profile) =>
      ["micro", "mystiko", "macro"].map(
        (dimension) =>
          `<text class="radar-axis-label" data-profile="${profile}" data-dimension="${dimension}">${dimension}</text>`,
      ),
    )
    .join("");
}

function buildDefsMarkup(): string {
  return ["challenge", "reward"]
    .flatMap((kind) => [
      `<clipPath id="q-radar-clip-${kind}"><path class="q-radar-clip--${kind}"></path></clipPath>`,
      ...[0, 1, 2].map(
        (index) =>
          `<linearGradient id="q-radar-grad-${kind}-${index}" gradientUnits="userSpaceOnUse"></linearGradient>`,
      ),
    ])
    .join("");
}

function buildLayerMarkup(): string {
  return ["challenge", "reward"]
    .map(
      (kind) => `
      <g class="q-radar-layer q-radar-layer--${kind}" style="opacity:0">
        <g clip-path="url(#q-radar-clip-${kind})" class="radar-polygon-fill">
          ${[0, 1, 2]
            .map(
              (index) =>
                `<path class="radar-polygon-gradient q-radar-fill--${kind}" fill="url(#q-radar-grad-${kind}-${index})"></path>`,
            )
            .join("")}
        </g>
        <path class="radar-polygon--${kind} q-radar-polygon"></path>
      </g>`,
    )
    .join("");
}

function mountContainer(): HTMLElement {
  const container = document.createElement("div");
  container.className = "questionnaire-radar-container";
  container.innerHTML = `
    <svg class="radar-chart__svg" viewBox="0 0 ${SIZE} ${SIZE}">
      <defs>${buildDefsMarkup()}</defs>
      <path class="radar-polygon--raw-benchmark" style="display:none"></path>
      ${buildLayerMarkup()}
      <g>${buildNodeMarkup()}</g>
      <g>${buildLabelMarkup()}</g>
    </svg>
    <div class="radar-toggle-group" style="display:none">
      <button type="button" class="radar-profile-btn is-active" data-toggle-target="challenge" aria-pressed="true">Challenge</button>
      <button type="button" class="radar-profile-btn" data-toggle-target="reward" aria-pressed="false">Reward</button>
    </div>`;
  document.body.appendChild(container);
  return container;
}

let container: HTMLElement | null = null;
let bridge: RadarLiveBridge | null = null;

function setup(): HTMLElement {
  container = mountContainer();
  bridge = new RadarLiveBridge(container, SIZE);
  return container;
}

afterEach(() => {
  bridge?.destroy();
  bridge = null;
  container?.remove();
  container = null;
});

function layer(root: HTMLElement, which: "challenge" | "reward"): SVGGElement {
  const element = root.querySelector<SVGGElement>(`.q-radar-layer--${which}`);
  if (!element) throw new Error(`missing ${which} layer`);
  return element;
}

function polygon(
  root: HTMLElement,
  which: "challenge" | "reward" | "raw",
): SVGPathElement {
  const selector =
    which === "raw"
      ? ".radar-polygon--raw-benchmark"
      : `.radar-polygon--${which}`;
  const element = root.querySelector<SVGPathElement>(selector);
  if (!element) throw new Error(`missing ${selector}`);
  return element;
}

function toggleGroup(root: HTMLElement): HTMLElement {
  const element = root.querySelector<HTMLElement>(".radar-toggle-group");
  if (!element) throw new Error("missing toggle group");
  return element;
}

function emitScore(
  event: string,
  detail: QuestionnaireScoreUpdateDetail,
): void {
  window.dispatchEvent(new CustomEvent(event, { detail }));
}

function emitPhase(phase: QuestionnairePhaseChangeDetail["phase"]): void {
  window.dispatchEvent(
    new CustomEvent<QuestionnairePhaseChangeDetail>(
      QUESTIONNAIRE_RADAR_EVENTS.phaseChange,
      { detail: { phase } },
    ),
  );
}

function emitBoundarySwap(targetProfile: "CHALLENGE" | "REWARD"): void {
  window.dispatchEvent(
    new CustomEvent<QuestionnaireBoundarySwapDetail>(
      QUESTIONNAIRE_RADAR_EVENTS.boundarySwap,
      { detail: { targetProfile } },
    ),
  );
}

describe("RadarLiveBridge", () => {
  it("mounts in the neutral AESTHETICS state with both layers hidden", () => {
    const root = setup();
    expect(layer(root, "challenge").style.opacity).toBe("0");
    expect(layer(root, "reward").style.opacity).toBe("0");
    expect(toggleGroup(root).style.display).toBe("none");
    expect(polygon(root, "raw").style.display).toBe("none");
  });

  it("plots the challenge polygon on the first challenge update", () => {
    const root = setup();
    emitPhase("CHALLENGE");
    emitScore(QUESTIONNAIRE_RADAR_EVENTS.challengeUpdate, {
      profile: "CHALLENGE",
      normalized: { micro: 50, macro: 30, mystiko: 20 },
    });

    const challenge = polygon(root, "challenge");
    expect(layer(root, "challenge").style.opacity).toBe("1");
    expect(challenge.getAttribute("d")).toBeTruthy();
    expect(challenge.getAttribute("d")).not.toContain("NaN");
    expect(layer(root, "reward").style.opacity).toBe("0");
  });

  it("crossfades to the reward polygon on a boundary swap", () => {
    const root = setup();
    emitPhase("CHALLENGE");
    emitScore(QUESTIONNAIRE_RADAR_EVENTS.challengeUpdate, {
      profile: "CHALLENGE",
      normalized: { micro: 50, macro: 30, mystiko: 20 },
    });
    emitBoundarySwap("REWARD");
    emitScore(QUESTIONNAIRE_RADAR_EVENTS.rewardUpdate, {
      profile: "REWARD",
      normalized: { micro: 20, macro: 40, mystiko: 40 },
    });

    expect(layer(root, "challenge").style.opacity).toBe("0");
    expect(layer(root, "reward").style.opacity).toBe("1");
  });

  it("reveals the dual layer, toggle, and raw benchmark in REVIEW_Q15", () => {
    const root = setup();
    emitPhase("CHALLENGE");
    emitScore(QUESTIONNAIRE_RADAR_EVENTS.challengeUpdate, {
      profile: "CHALLENGE",
      normalized: { micro: 50, macro: 30, mystiko: 20 },
    });
    emitPhase("REVIEW_Q15");

    expect(toggleGroup(root).style.display).toBe("flex");
    expect(polygon(root, "raw").style.display).toBe("block");
    expect(layer(root, "challenge").style.opacity).toBe("1");
    expect(layer(root, "reward").style.opacity).toBe("0.2");
  });

  it("keeps the raw benchmark pinned while the adjusted polygon morphs", () => {
    const root = setup();
    emitPhase("REVIEW_Q15");
    emitScore(QUESTIONNAIRE_RADAR_EVENTS.challengeUpdate, {
      profile: "CHALLENGE",
      normalized: { micro: 50, macro: 30, mystiko: 20 },
      adjusted: { micro: 45, macro: 30, mystiko: 25 },
    });

    const rawBefore = polygon(root, "raw").getAttribute("d");
    const adjustedBefore = polygon(root, "challenge").getAttribute("d");

    emitScore(QUESTIONNAIRE_RADAR_EVENTS.challengeUpdate, {
      profile: "CHALLENGE",
      normalized: { micro: 50, macro: 30, mystiko: 20 },
      adjusted: { micro: 30, macro: 30, mystiko: 40 },
    });

    expect(polygon(root, "challenge").getAttribute("d")).not.toBe(
      adjustedBefore,
    );
    expect(polygon(root, "raw").getAttribute("d")).toBe(rawBefore);
  });

  it("plots the soft live vector while answering and the accurate one in Q15", () => {
    const root = setup();
    emitPhase("CHALLENGE");
    emitScore(QUESTIONNAIRE_RADAR_EVENTS.challengeUpdate, {
      profile: "CHALLENGE",
      normalized: { micro: 80, macro: 10, mystiko: 10 },
      live: { micro: 44, macro: 28, mystiko: 28 },
    });
    const livePath = polygon(root, "challenge").getAttribute("d");

    emitPhase("REVIEW_Q15");
    const accuratePath = polygon(root, "challenge").getAttribute("d");

    expect(livePath).toBeTruthy();
    expect(accuratePath).not.toBe(livePath);
  });

  it("draws the barycentric fill and anchors its gradient axes on the vertices", () => {
    const root = setup();
    emitPhase("CHALLENGE");
    emitScore(QUESTIONNAIRE_RADAR_EVENTS.challengeUpdate, {
      profile: "CHALLENGE",
      normalized: { micro: 80, macro: 10, mystiko: 10 },
    });

    const fills = root.querySelectorAll(".q-radar-fill--challenge");
    expect(fills).toHaveLength(3);
    for (const fill of fills) {
      expect(fill.getAttribute("d")).toBeTruthy();
      expect(fill.getAttribute("d")).not.toContain("NaN");
    }

    const gradients = root.querySelectorAll(
      'linearGradient[id^="q-radar-grad-challenge-"]',
    );
    expect(gradients).toHaveLength(3);
    for (const gradient of gradients) {
      expect(Number.isFinite(Number(gradient.getAttribute("x1")))).toBe(true);
      expect(Number.isFinite(Number(gradient.getAttribute("y2")))).toBe(true);
    }
  });

  it("emphasises the active profile's axis labels", () => {
    const root = setup();
    emitPhase("REVIEW_Q15");

    const activeProfiles = () =>
      Array.from(
        root.querySelectorAll<SVGTextElement>(".radar-axis-label--active"),
      ).map((label) => label.dataset.profile);

    expect(activeProfiles()).toEqual(["challenge", "challenge", "challenge"]);

    root
      .querySelector<HTMLButtonElement>("[data-toggle-target='reward']")!
      .click();

    expect(activeProfiles()).toEqual(["reward", "reward", "reward"]);
  });

  it("switches the active layer when a toggle button is pressed", () => {
    const root = setup();
    emitPhase("REVIEW_Q15");
    emitScore(QUESTIONNAIRE_RADAR_EVENTS.challengeUpdate, {
      profile: "CHALLENGE",
      normalized: { micro: 50, macro: 30, mystiko: 20 },
    });
    emitScore(QUESTIONNAIRE_RADAR_EVENTS.rewardUpdate, {
      profile: "REWARD",
      normalized: { micro: 20, macro: 40, mystiko: 40 },
    });

    const rewardButton = root.querySelector<HTMLButtonElement>(
      "[data-toggle-target='reward']",
    )!;
    rewardButton.click();

    expect(layer(root, "reward").style.opacity).toBe("1");
    expect(layer(root, "challenge").style.opacity).toBe("0.2");
    expect(rewardButton.getAttribute("aria-pressed")).toBe("true");
  });
});
