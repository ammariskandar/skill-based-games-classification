// @vitest-environment jsdom
/**
 * DOM & accessibility contract tests for the radar markup (SBGC-88).
 *
 * `RadarChart.astro` is a thin `set:html` passthrough over `buildRadarHtml`,
 * so the single source of truth for the component's server-rendered markup is
 * asserted here directly against real parsed DOM nodes.
 */
import { describe, expect, it } from "vitest";

import { buildRadarHtml } from "./radar-render";

const CHALLENGE = { micro: 60, mystiko: 20, macro: 20 };
const REWARD = { micro: 30, mystiko: 40, macro: 30 };

function parse(html: string): Document {
  return new DOMParser().parseFromString(html, "text/html");
}

describe("SVG accessibility metadata", () => {
  it("binds role, aria-labelledby, title and desc consistently", () => {
    const doc = parse(
      buildRadarHtml({
        challenge: CHALLENGE,
        reward: REWARD,
        gameTitle: "Portal 2",
      }),
    );
    const svg = doc.querySelector<SVGSVGElement>(".radar-chart__svg");
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute("role")).toBe("img");

    const ids = (svg!.getAttribute("aria-labelledby") ?? "")
      .split(/\s+/)
      .filter(Boolean);
    expect(ids).toHaveLength(2);

    const title = doc.getElementById(ids[0]);
    const desc = doc.getElementById(ids[1]);
    expect(title).not.toBeNull();
    expect(desc).not.toBeNull();
    expect(title!.textContent).toBe("Portal 2 Skill Classification Radar");
    expect(desc!.textContent).toContain("Challenge profile");
    expect(desc!.textContent).toContain("Reward profile");
  });

  it("falls back to the generic title when no game title is provided", () => {
    const doc = parse(buildRadarHtml({ challenge: CHALLENGE, reward: REWARD }));
    const svg = doc.querySelector<SVGSVGElement>(".radar-chart__svg")!;
    const firstId = (svg.getAttribute("aria-labelledby") ?? "").split(/\s+/)[0];
    expect(doc.getElementById(firstId)?.textContent).toBe(
      "Skill Classification Radar Chart",
    );
  });
});

describe("screen-reader fallback table parity", () => {
  it("reports exact scores for both profiles", () => {
    const doc = parse(buildRadarHtml({ challenge: CHALLENGE, reward: REWARD }));
    const table = doc.querySelector<HTMLTableElement>("table.sr-only");
    expect(table).not.toBeNull();

    const rows = Array.from(table!.querySelectorAll("tbody tr"));
    expect(rows).toHaveLength(2);

    const cells = rows.map((row) =>
      Array.from(row.querySelectorAll("th, td")).map(
        (cell) => cell.textContent,
      ),
    );
    expect(cells).toEqual([
      ["Challenge", "60", "20", "20"],
      ["Reward", "30", "40", "30"],
    ]);
  });

  it("omits a null profile from the table", () => {
    const doc = parse(buildRadarHtml({ challenge: CHALLENGE, reward: null }));
    const rows = Array.from(
      doc.querySelectorAll<HTMLTableRowElement>(".sr-only tbody tr"),
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].textContent).toContain("Challenge");
    expect(rows[0].textContent).not.toContain("Reward");
  });
});

describe("unavailable fallback state", () => {
  it("renders an accessible empty state with no broken SVG when both profiles are null", () => {
    const html = buildRadarHtml({ challenge: null, reward: null });
    const doc = parse(html);

    const root = doc.querySelector<HTMLElement>(".radar-chart--unavailable");
    expect(root).not.toBeNull();
    expect(root!.getAttribute("role")).toBe("img");
    expect(root!.getAttribute("aria-label")).toBe(
      "Skill classification unavailable",
    );
    expect(doc.body.textContent).toContain("Classification unavailable");
    // No interactive layers, polygons, nodes, or switch can exist in the empty state.
    expect(doc.querySelector("[data-radar-layers]")).toBeNull();
    expect(doc.querySelector(".radar-polygon")).toBeNull();
    expect(doc.querySelector(".radar-vertex-node")).toBeNull();
    expect(doc.querySelector(".radar-toggle")).toBeNull();
  });
});

describe("design-token binding", () => {
  it("references CSS variables and never hardcodes hex colors", () => {
    const html = buildRadarHtml({ challenge: CHALLENGE, reward: REWARD });
    expect(html).toContain("var(--color-micro)");
    expect(html).toContain("var(--color-mystiko)");
    expect(html).toContain("var(--color-macro)");
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe("vertex node data contract", () => {
  it("exposes profile, dimension, score, label and aria-label on every node", () => {
    const doc = parse(buildRadarHtml({ challenge: CHALLENGE, reward: REWARD }));
    const nodes = Array.from(
      doc.querySelectorAll<SVGCircleElement>(".radar-vertex-node"),
    );
    expect(nodes).toHaveLength(6);

    for (const node of nodes) {
      expect(["challenge", "reward"]).toContain(node.dataset.profile);
      expect(["micro", "mystiko", "macro"]).toContain(node.dataset.dimension);
      expect(Number(node.dataset.score)).toBeGreaterThanOrEqual(0);
      expect(node.getAttribute("tabindex")).toBe("0");
      expect(node.getAttribute("aria-label")).toMatch(
        /^(Challenge|Reward) (Micro|Mystiko|Macro): \d+$/,
      );
    }
  });
});

describe("profile switch contract", () => {
  it("renders a role=switch with the active profile label underneath", () => {
    const doc = parse(buildRadarHtml({ challenge: CHALLENGE, reward: REWARD }));
    const switchEl = doc.querySelector<HTMLButtonElement>(".radar-toggle");
    expect(switchEl).not.toBeNull();
    expect(switchEl!.getAttribute("role")).toBe("switch");
    expect(switchEl!.getAttribute("aria-checked")).toBe("false");
    expect(doc.querySelector("[data-toggle-label]")?.textContent).toBe(
      "Challenge",
    );
  });

  it("omits the switch when only one profile is present", () => {
    const doc = parse(buildRadarHtml({ challenge: CHALLENGE, reward: null }));
    expect(doc.querySelector(".radar-toggle")).toBeNull();
  });

  it("omits the switch when showToggle is disabled", () => {
    const doc = parse(
      buildRadarHtml({
        challenge: CHALLENGE,
        reward: REWARD,
        showToggle: false,
      }),
    );
    expect(doc.querySelector(".radar-toggle")).toBeNull();
  });
});
