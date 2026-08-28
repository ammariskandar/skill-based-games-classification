// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { initRadarChart, prefersReducedMotion } from "./radar-controller";
import { buildRadarHtml } from "./radar-render";
import {
  buildRadarDescription,
  buildRadarSummaryRows,
  buildRadarTitle,
  buildVertexAriaLabel,
  buildVertexLabel,
  getDimensionDescription,
  type SkillProfileVector,
} from "./skill-dimensions";

describe("prefersReducedMotion", () => {
  it("is true when the media query matches reduce", () => {
    expect(prefersReducedMotion(() => ({ matches: true }))).toBe(true);
  });

  it("is false when the media query does not match reduce", () => {
    expect(prefersReducedMotion(() => ({ matches: false }))).toBe(false);
  });
});

describe("buildRadarTitle", () => {
  it("includes the game title when provided", () => {
    expect(buildRadarTitle("Portal 2")).toBe(
      "Portal 2 Skill Classification Radar",
    );
  });

  it("falls back to a generic title", () => {
    expect(buildRadarTitle()).toBe("Skill Classification Radar Chart");
  });
});

describe("buildRadarDescription", () => {
  const challenge: SkillProfileVector = { micro: 60, mystiko: 20, macro: 20 };
  const reward: SkillProfileVector = { micro: 30, mystiko: 40, macro: 30 };

  it("describes both complete profiles", () => {
    const description = buildRadarDescription(challenge, reward);
    expect(description).toContain(
      "Challenge profile (Micro: 60, Mystiko: 20, Macro: 20)",
    );
    expect(description).toContain(
      "Reward profile (Micro: 30, Mystiko: 40, Macro: 30)",
    );
  });

  it("describes a partial profile set", () => {
    const description = buildRadarDescription(challenge, null);
    expect(description).toContain("Challenge profile");
    expect(description).not.toContain("Reward profile");
  });

  it("describes an empty profile set", () => {
    const description = buildRadarDescription(null, null);
    expect(description).toContain("no available skill classification profiles");
  });
});

describe("buildRadarSummaryRows", () => {
  const challenge: SkillProfileVector = { micro: 10, mystiko: 20, macro: 70 };
  const reward: SkillProfileVector = { micro: 40, mystiko: 30, macro: 30 };

  it("returns exact numeric rows for both profiles", () => {
    const rows = buildRadarSummaryRows(challenge, reward);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      profile: "challenge",
      label: "Challenge",
      micro: 10,
      mystiko: 20,
      macro: 70,
    });
    expect(rows[1]).toMatchObject({
      profile: "reward",
      label: "Reward",
      micro: 40,
      mystiko: 30,
      macro: 30,
    });
  });

  it("omits null profiles", () => {
    const rows = buildRadarSummaryRows(challenge, null);
    expect(rows).toHaveLength(1);
    expect(rows[0].profile).toBe("challenge");
  });
});

describe("buildVertexLabel / buildVertexAriaLabel", () => {
  it("builds the profile-dimension label", () => {
    expect(buildVertexLabel("challenge", "micro")).toBe("Challenge Micro");
    expect(buildVertexLabel("reward", "mystiko")).toBe("Reward Mystiko");
  });

  it("builds an aria-label that includes the score", () => {
    expect(buildVertexAriaLabel("challenge", "micro", 45)).toBe(
      "Challenge Micro: 45",
    );
  });
});

/* ── DOM lifecycle & interaction (SBGC-88) ─────────────────────────────── */

const CHALLENGE: SkillProfileVector = { micro: 60, mystiko: 20, macro: 20 };
const REWARD: SkillProfileVector = { micro: 30, mystiko: 40, macro: 30 };

function mountChart(): HTMLElement {
  document.body.innerHTML = buildRadarHtml({
    challenge: CHALLENGE,
    reward: REWARD,
    gameTitle: "Portal 2",
  });
  const container = document.querySelector<HTMLElement>("[data-radar-chart]");
  if (!container) throw new Error("radar chart markup not rendered");
  return container;
}

beforeEach(() => {
  // jsdom omits matchMedia/requestAnimationFrame; the controller reads them.
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: true })),
  );
  vi.stubGlobal(
    "requestAnimationFrame",
    vi.fn(() => 1),
  );
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
});

afterEach(() => {
  document.body.innerHTML = "";
});

describe("initRadarChart lifecycle", () => {
  it("returns a handle whose destroy detaches listeners", () => {
    const container = mountChart();
    const handle = initRadarChart(container);
    const toggle = container.querySelector<HTMLButtonElement>(".radar-toggle");
    const toggleLabel = container.querySelector<HTMLElement>(
      "[data-toggle-label]",
    );

    expect(toggle).not.toBeNull();
    expect(toggleLabel).not.toBeNull();
    expect(toggle!.getAttribute("aria-checked")).toBe("false");
    expect(toggleLabel!.textContent).toBe("Challenge");

    toggle!.click();
    expect(toggle!.getAttribute("aria-checked")).toBe("true");
    expect(toggleLabel!.textContent).toBe("Reward");

    handle.destroy();

    // Listeners are detached: a further click must not change state.
    toggle!.click();
    expect(toggle!.getAttribute("aria-checked")).toBe("true");
    expect(toggleLabel!.textContent).toBe("Reward");
  });

  it("is idempotent under repeated destroy calls", () => {
    const container = mountChart();
    const handle = initRadarChart(container);
    expect(() => {
      handle.destroy();
      handle.destroy();
    }).not.toThrow();
  });

  it("setProfile forces the active layer without the toggle", () => {
    const container = mountChart();
    const handle = initRadarChart(container);

    handle.setProfile("reward");

    const rewardPath = container.querySelector<SVGPathElement>(
      ".radar-polygon-reward",
    );
    const challengePath = container.querySelector<SVGPathElement>(
      ".radar-polygon-challenge",
    );
    const toggle = container.querySelector<HTMLButtonElement>(".radar-toggle");
    const activeLabel = container.querySelector<SVGTextElement>(
      ".radar-axis-label--active",
    );
    expect(rewardPath!.classList.contains("radar-polygon--active")).toBe(true);
    expect(challengePath!.classList.contains("radar-polygon--active")).toBe(
      false,
    );
    expect(toggle!.getAttribute("aria-checked")).toBe("true");
    expect(activeLabel!.dataset.profile).toBe("reward");

    handle.setProfile("challenge");
    expect(challengePath!.classList.contains("radar-polygon--active")).toBe(
      true,
    );
    expect(rewardPath!.classList.contains("radar-polygon--active")).toBe(false);
    expect(toggle!.getAttribute("aria-checked")).toBe("false");
  });
});

describe("profile layer switching", () => {
  it("moves the selected polygon to the top and dims the other", () => {
    const container = mountChart();
    initRadarChart(container);

    const challengePath = container.querySelector<SVGPathElement>(
      ".radar-polygon-challenge",
    );
    const rewardPath = container.querySelector<SVGPathElement>(
      ".radar-polygon-reward",
    );
    expect(challengePath).not.toBeNull();
    expect(rewardPath).not.toBeNull();

    // Initial state: Challenge is active.
    expect(challengePath!.classList.contains("radar-polygon--active")).toBe(
      true,
    );
    expect(rewardPath!.classList.contains("radar-polygon--inactive")).toBe(
      true,
    );

    container.querySelector<HTMLButtonElement>(".radar-toggle")!.click();

    expect(rewardPath!.classList.contains("radar-polygon--active")).toBe(true);
    expect(challengePath!.classList.contains("radar-polygon--inactive")).toBe(
      true,
    );

    // The active path is painted last so it sits on top.
    const polygonGroup = container.querySelector<SVGGElement>(
      "[data-radar-polygons]",
    )!;
    expect(polygonGroup.lastElementChild).toBe(rewardPath);
  });

  it("moves vertex-node and axis-label active classes to the selected profile", () => {
    const container = mountChart();
    initRadarChart(container);

    const activeNodesBefore = Array.from(
      container.querySelectorAll<SVGCircleElement>(
        ".radar-vertex-node--active",
      ),
    );
    const activeLabelsBefore = Array.from(
      container.querySelectorAll<SVGTextElement>(".radar-axis-label--active"),
    );
    expect(activeNodesBefore.map((node) => node.dataset.profile)).toEqual([
      "challenge",
      "challenge",
      "challenge",
    ]);
    expect(activeLabelsBefore.map((label) => label.dataset.profile)).toEqual([
      "challenge",
      "challenge",
      "challenge",
    ]);

    container.querySelector<HTMLButtonElement>(".radar-toggle")!.click();

    const activeNodes = Array.from(
      container.querySelectorAll<SVGCircleElement>(
        ".radar-vertex-node--active",
      ),
    );
    const activeLabels = Array.from(
      container.querySelectorAll<SVGTextElement>(".radar-axis-label--active"),
    );
    expect(activeNodes.map((node) => node.dataset.profile)).toEqual([
      "reward",
      "reward",
      "reward",
    ]);
    expect(activeLabels.map((label) => label.dataset.profile)).toEqual([
      "reward",
      "reward",
      "reward",
    ]);
  });
});

describe("vertex tooltips (hover and keyboard focus)", () => {
  it("reveals the tooltip on hover and hides it on leave", () => {
    const container = mountChart();
    initRadarChart(container);

    const node = container.querySelector<SVGCircleElement>(
      ".radar-vertex-node[data-profile='challenge'][data-dimension='micro']",
    )!;
    const tooltip = container.querySelector<HTMLElement>(".radar-tooltip")!;
    const header = tooltip.querySelector<HTMLElement>(".radar-tooltip-header")!;
    const value = tooltip.querySelector<HTMLElement>(".radar-tooltip-value")!;
    const description = tooltip.querySelector<HTMLElement>(
      ".radar-tooltip-description",
    )!;

    node.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));

    expect(tooltip.getAttribute("aria-hidden")).toBe("false");
    expect(tooltip.style.opacity).toBe("1");
    expect(header.textContent).toBe("Challenge Micro");
    expect(header.style.color).toBe("var(--color-micro)");
    expect(value.textContent).toBe("60%");
    expect(description.textContent).toBe(
      getDimensionDescription("challenge", "micro"),
    );
    expect(tooltip.style.top).toMatch(/^\d+px$/);
    expect(tooltip.style.left).toMatch(/^\d+px$/);
    expect(node.getAttribute("r")).toBe("7");
    expect(node.classList.contains("radar-vertex-node--hovered")).toBe(true);

    node.dispatchEvent(new MouseEvent("mouseleave", { bubbles: true }));

    expect(tooltip.getAttribute("aria-hidden")).toBe("true");
    expect(tooltip.style.opacity).toBe("0");
    expect(node.getAttribute("r")).toBe("4");
    expect(node.classList.contains("radar-vertex-node--hovered")).toBe(false);
  });

  it("reveals the tooltip on keyboard focus and hides it on blur", () => {
    const container = mountChart();
    initRadarChart(container);

    const node = container.querySelector<SVGCircleElement>(
      ".radar-vertex-node[data-profile='reward'][data-dimension='macro']",
    )!;
    const tooltip = container.querySelector<HTMLElement>(".radar-tooltip")!;
    const header = tooltip.querySelector<HTMLElement>(".radar-tooltip-header")!;
    const value = tooltip.querySelector<HTMLElement>(".radar-tooltip-value")!;

    node.dispatchEvent(new FocusEvent("focus"));

    expect(tooltip.getAttribute("aria-hidden")).toBe("false");
    expect(header.textContent).toBe("Reward Macro");
    expect(value.textContent).toBe("30%");

    node.dispatchEvent(new FocusEvent("blur"));

    expect(tooltip.getAttribute("aria-hidden")).toBe("true");
  });
});

describe("reduced-motion branching", () => {
  it("applies final layout immediately when reduced motion is preferred", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: true })),
    );
    const rAF = vi.fn(() => 1);
    vi.stubGlobal("requestAnimationFrame", rAF);

    const container = mountChart();
    initRadarChart(container);

    const layers = container.querySelector<SVGGElement>("[data-radar-layers]");
    expect(layers).not.toBeNull();
    expect(layers!.hasAttribute("transform")).toBe(false);
    expect(rAF).not.toHaveBeenCalled();
  });

  it("starts the entrance animation when motion is allowed", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: false })),
    );
    const rAF = vi.fn(() => 1);
    vi.stubGlobal("requestAnimationFrame", rAF);

    const container = mountChart();
    initRadarChart(container);

    const layers = container.querySelector<SVGGElement>("[data-radar-layers]");
    expect(layers).not.toBeNull();
    expect(layers!.hasAttribute("transform")).toBe(true);
    expect(rAF).toHaveBeenCalledTimes(1);
  });
});
