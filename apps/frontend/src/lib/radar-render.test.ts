// @vitest-environment jsdom
/**
 * DOM & accessibility contract tests for the radar markup (SBGC-88).
 *
 * `RadarChart.astro` is a thin `set:html` passthrough over `buildRadarHtml`,
 * so the single source of truth for the component's server-rendered markup is
 * asserted here directly against real parsed DOM nodes.
 */
import { describe, expect, it } from "vitest";

import {
  barycentricColor,
  buildRadarHtml,
  polygonColorVertices,
} from "./radar-render";

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

describe("vertex-anchored barycentric fill (SBGC-210)", () => {
  const REFERENCE_TRIANGLE: Array<{
    x: number;
    y: number;
    color: [number, number, number];
  }> = [
    { x: 0, y: 0, color: [0x58, 0xa6, 0xff] },
    { x: 100, y: 0, color: [0xbc, 0x8c, 0xff] },
    { x: 0, y: 100, color: [0xff, 0xa6, 0x57] },
  ];

  it("returns the exact vertex color at each vertex", () => {
    expect(barycentricColor(REFERENCE_TRIANGLE, 0, 0)).toBe("rgb(88,166,255)");
    expect(barycentricColor(REFERENCE_TRIANGLE, 100, 0)).toBe(
      "rgb(188,140,255)",
    );
    expect(barycentricColor(REFERENCE_TRIANGLE, 0, 100)).toBe(
      "rgb(255,166,87)",
    );
  });

  it("blends all three vertex colors at the centroid", () => {
    expect(barycentricColor(REFERENCE_TRIANGLE, 100 / 3, 100 / 3)).toBe(
      "rgb(177,157,199)",
    );
  });

  it("orders challenge vertices with their dimension colors", () => {
    const vertices = polygonColorVertices(
      { micro: 100, mystiko: 50, macro: 0 },
      "challenge",
      { x: 160, y: 160 },
      100,
    );
    expect(vertices).toHaveLength(3);
    expect(vertices.map((v) => v.color)).toEqual([
      [0x58, 0xa6, 0xff], // micro (0°, top) → blue
      [0xbc, 0x8c, 0xff], // mystiko (120°) → purple
      [0xff, 0xa6, 0x57], // macro (240°) → orange
    ]);
    expect(vertices[0].y).toBeLessThan(160);
  });

  it("orders reward vertices with their dimension colors", () => {
    const vertices = polygonColorVertices(
      { micro: 100, mystiko: 50, macro: 0 },
      "reward",
      { x: 160, y: 160 },
      100,
    );
    expect(vertices.map((v) => v.color)).toEqual([
      [0xff, 0xa6, 0x57], // macro (60°) → orange
      [0x58, 0xa6, 0xff], // micro (180°, bottom) → blue
      [0xbc, 0x8c, 0xff], // mystiko (300°) → purple
    ]);
    expect(vertices[1].y).toBeGreaterThan(160);
  });

  it("emits a barycentric fill mesh and drops the radial gradient", () => {
    const html = buildRadarHtml({ challenge: CHALLENGE, reward: REWARD });
    const doc = parse(html);
    expect(
      doc.querySelectorAll(".radar-polygon-fill rect").length,
    ).toBeGreaterThan(0);
    expect(html).not.toContain("radar-fill");
    expect(
      doc
        .querySelector(".radar-polygon-challenge")
        ?.classList.contains("radar-polygon--active"),
    ).toBe(true);
    expect(
      doc
        .querySelector(".radar-polygon-reward")
        ?.classList.contains("radar-polygon--inactive"),
    ).toBe(true);
    // The stroke is a distinct element so the glow never touches the mesh cells.
    expect(
      doc.querySelector(".radar-polygon-challenge .radar-polygon-stroke"),
    ).not.toBeNull();
  });

  it("anchors blue at the Micro vertex in the rendered fill", () => {
    const doc = parse(
      buildRadarHtml({
        challenge: { micro: 60, mystiko: 20, macro: 20 },
        reward: null,
      }),
    );
    const microNode = doc.querySelector<SVGCircleElement>(
      '.radar-vertex-node[data-profile="challenge"][data-dimension="micro"]',
    )!;
    const cx = Number(microNode.getAttribute("cx"));
    const cy = Number(microNode.getAttribute("cy"));
    const rects = Array.from(
      doc.querySelectorAll<SVGRectElement>(".radar-polygon-fill rect"),
    );
    expect(rects.length).toBeGreaterThan(0);

    let best: SVGRectElement | null = null;
    let bestDist = Number.POSITIVE_INFINITY;
    for (const rect of rects) {
      const rx =
        Number(rect.getAttribute("x")) + Number(rect.getAttribute("width")) / 2;
      const ry =
        Number(rect.getAttribute("y")) +
        Number(rect.getAttribute("height")) / 2;
      const d = (rx - cx) ** 2 + (ry - cy) ** 2;
      if (d < bestDist) {
        bestDist = d;
        best = rect;
      }
    }
    const [, r, , b] = best!
      .getAttribute("fill")!
      .match(/rgb\((\d+),(\d+),(\d+)\)/)!
      .map(Number);
    expect(b).toBeGreaterThan(r);
  });

  it("renders a blue-dominated fill for a 90/5/5 Micro profile", () => {
    const doc = parse(
      buildRadarHtml({
        challenge: { micro: 90, mystiko: 5, macro: 5 },
        reward: null,
      }),
    );
    const rects = Array.from(
      doc.querySelectorAll<SVGRectElement>(".radar-polygon-fill rect"),
    );
    expect(rects.length).toBeGreaterThan(0);

    let totalR = 0;
    let totalB = 0;
    for (const rect of rects) {
      const m = rect.getAttribute("fill")?.match(/rgb\((\d+),(\d+),(\d+)\)/);
      if (m) {
        totalR += Number(m[1]);
        totalB += Number(m[3]);
      }
    }
    expect(totalB).toBeGreaterThan(totalR);
  });
});
