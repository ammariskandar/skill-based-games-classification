/**
 * Reusable radar markup builder (SBGC-87).
 *
 * Pure string generation with no DOM dependency. It is the single source of
 * truth for the `<RadarChart>` markup so the same geometry + accessibility
 * markup can be rendered server-side (Astro) and client-side (rankings dynamic
 * selection) without drifting.
 */

import {
  DIMENSIONS,
  buildRadarDescription,
  buildRadarSummaryRows,
  buildRadarTitle,
  buildVertexAriaLabel,
  buildVertexLabel,
  type DimensionId,
  type SkillProfileKind,
  type SkillProfileVector,
} from "./skill-dimensions";
import {
  SPOKES,
  generateSplinePath,
  getSpokePoints,
  polarToCartesian,
  type Point,
} from "./radar-geometry";

export interface RadarRenderData {
  challenge: SkillProfileVector | null;
  reward: SkillProfileVector | null;
  initialProfile?: SkillProfileKind;
  size?: number;
  gameTitle?: string;
  class?: string;
  showToggle?: boolean;
}

const escapeHtml = (value: string): string =>
  value.replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });

const unavailableHtml = (className: string): string =>
  `<div class="radar-chart radar-chart--unavailable${className}" role="img" aria-label="Skill classification unavailable"><div class="radar-chart__unavailable"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="8.5" cy="10" r="1.5" /><path d="M21 15l-5-5L5 20" /></svg><span>Classification unavailable</span></div></div>`;

/**
 * Horizontal anchor for a spoke label so its leading/trailing glyph sits on the
 * spoke tip and the text flows outward (never into the chart).
 */
function textAnchorFor(angleDegrees: number): "start" | "middle" | "end" {
  const radians = (angleDegrees * Math.PI) / 180;
  const x = Math.sin(radians);
  if (Math.abs(x) < 1e-9) return "middle";
  return x > 0 ? "start" : "end";
}

/* ── SBGC-210: vertex-anchored barycentric fill ──
   Replaces the radial gradient with a Gouraud-style fill: each polygon vertex
   carries its dimension's color (Micro → blue, Mystiko → purple, Macro →
   orange) and the interior is interpolated by barycentric weight.  Pure SVG
   (a clipped mesh of solid rects) so SSR and Vitest stay DOM-free. */

/**
 * Base colors for the vertex-anchored fill.  These mirror the
 * `--color-micro` / `--color-mystiko` / `--color-macro` theme tokens so the
 * pure string generator can interpolate fills without a DOM.
 */
const VERTEX_COLOR: Record<DimensionId, [number, number, number]> = {
  micro: [0x58, 0xa6, 0xff], // --color-micro
  mystiko: [0xbc, 0x8c, 0xff], // --color-mystiko
  macro: [0xff, 0xa6, 0x57], // --color-macro
};

/** Cells per side of the barycentric fill mesh (N² cells per polygon). */
const FILL_GRID_CELLS = 16;

export interface PolygonVertex {
  x: number;
  y: number;
  color: [number, number, number];
}

/**
 * A polygon's three dimension vertices with their anchor colors, ordered by
 * spoke angle — identical geometry to `getSpokePoints`, plus the color.
 */
export function polygonColorVertices(
  profile: SkillProfileVector | null,
  kind: SkillProfileKind,
  center: Point,
  maxRadius: number,
): PolygonVertex[] {
  return SPOKES.filter((spoke) => spoke.kind === kind).map((spoke) => {
    const score = profile ? profile[spoke.dimension] : 0;
    const radius = ((Number.isFinite(score) ? score : 0) / 100) * maxRadius;
    return {
      ...polarToCartesian(center.x, center.y, radius, spoke.angleDegrees),
      color: VERTEX_COLOR[spoke.dimension],
    };
  });
}

/**
 * Barycentric color at a point relative to the polygon's reference triangle.
 *
 * Each vertex contributes its anchor color weighted by the signed sub-triangle
 * area opposite it, so the color at a vertex is that vertex's color and the
 * interior is a smooth Gouraud blend.  Points outside the triangle (the spline
 * bulge) extrapolate via signed weights; channels are clamped to the valid
 * range so no out-of-gamut color escapes.
 */
export function barycentricColor(
  vertices: PolygonVertex[],
  px: number,
  py: number,
): string {
  const [a, b, c] = vertices;
  const denom = (b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y);
  if (Math.abs(denom) < 1e-9) {
    const [r, g, bl] = a.color;
    return `rgb(${r},${g},${bl})`;
  }
  const wA = ((b.x - px) * (c.y - py) - (c.x - px) * (b.y - py)) / denom;
  const wB = ((c.x - px) * (a.y - py) - (a.x - px) * (c.y - py)) / denom;
  const wC = 1 - wA - wB;
  const clamp = (v: number): number =>
    Math.max(0, Math.min(255, Math.round(v)));
  return `rgb(${clamp(wA * a.color[0] + wB * b.color[0] + wC * c.color[0])},${clamp(
    wA * a.color[1] + wB * b.color[1] + wC * c.color[1],
  )},${clamp(wA * a.color[2] + wB * b.color[2] + wC * c.color[2])})`;
}

function fmt(v: number): string {
  return String(Math.round(v * 10) / 10);
}

/** Emit the clipped rect mesh that paints the barycentric fill. */
function polygonFillHtml(
  uid: string,
  kind: SkillProfileKind,
  vertices: PolygonVertex[],
): string {
  const xs = vertices.map((v) => v.x);
  const ys = vertices.map((v) => v.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = maxX - minX;
  const height = maxY - minY;
  // Degenerate (zero-area) polygons get no fill; the stroke path still renders.
  if (width < 0.5 || height < 0.5) return "";

  const n = FILL_GRID_CELLS;
  const cellW = width / n;
  const cellH = height / n;
  const rects: string[] = [];
  for (let j = 0; j < n; j += 1) {
    for (let i = 0; i < n; i += 1) {
      const x = minX + i * cellW;
      const y = minY + j * cellH;
      rects.push(
        `<rect x="${fmt(x)}" y="${fmt(y)}" width="${fmt(cellW)}" height="${fmt(cellH)}" fill="${barycentricColor(
          vertices,
          x + cellW / 2,
          y + cellH / 2,
        )}"/>`,
      );
    }
  }
  return `<g clip-path="url(#radar-clip-${uid}-${kind})" class="radar-polygon-fill">${rects.join("")}</g>`;
}

/** Clip path matching the polygon spline so the mesh never overdraws the stroke. */
function polygonClipHtml(
  uid: string,
  kind: SkillProfileKind,
  pathD: string,
): string {
  return `<clipPath id="radar-clip-${uid}-${kind}"><path d="${pathD}" /></clipPath>`;
}

/** One polygon layer: barycentric fill mesh + stroke path in a `<g>` layer. */
function polygonLayerHtml(
  kind: SkillProfileKind,
  profile: SkillProfileVector | null,
  pathD: string,
  center: Point,
  dataMaxRadius: number,
  uid: string,
  active: boolean,
): string {
  const fill = polygonFillHtml(
    uid,
    kind,
    polygonColorVertices(profile, kind, center, dataMaxRadius),
  );
  return `<g class="radar-polygon radar-polygon-${kind} ${
    active ? "radar-polygon--active" : "radar-polygon--inactive"
  }">${fill}<path class="radar-polygon-stroke" d="${pathD}" /></g>`;
}

export function buildRadarHtml(data: RadarRenderData): string {
  const {
    challenge,
    reward,
    initialProfile = "challenge",
    size = 320,
    gameTitle,
    class: className = "",
    showToggle = true,
  } = data;

  const classSuffix = className ? ` ${className}` : "";

  if (challenge === null && reward === null) {
    return unavailableHtml(classSuffix);
  }

  const center: Point = { x: size / 2, y: size / 2 };
  // 56 viewBox units of padding (was 48) around the grid gives the axis labels
  // breathing room before the SVG viewBox edge clips their text (SBGC-209).
  const maxRadius = size / 2 - 56;
  const labelRadius = maxRadius + 24;

  // The outermost ring is the highest score across present profiles, rounded
  // up to the nearest 10; inner rings are linear divisions of that maximum.
  const scores: number[] = [];
  if (challenge) {
    scores.push(challenge.micro, challenge.mystiko, challenge.macro);
  }
  if (reward) {
    scores.push(reward.micro, reward.mystiko, reward.macro);
  }
  const highestScore = scores.length > 0 ? Math.max(...scores) : 0;
  const maxScore = Math.max(10, Math.ceil(highestScore / 10) * 10);

  // `getSpokePoints` maps `score / 100` to a radius; scale the radius so that
  // `maxScore` (not 100) lands on the outermost ring.
  const dataMaxRadius = maxRadius * (100 / maxScore);

  const challengePath =
    challenge === null
      ? ""
      : generateSplinePath(
          getSpokePoints(challenge, "challenge", center, dataMaxRadius),
        );
  const rewardPath =
    reward === null
      ? ""
      : generateSplinePath(
          getSpokePoints(reward, "reward", center, dataMaxRadius),
        );

  const gridRadii = [0.2, 0.4, 0.6, 0.8, 1].map((factor) => factor * maxRadius);

  const spokes = SPOKES.map((spoke) => {
    const profile = spoke.kind === "challenge" ? challenge : reward;
    const score = profile ? profile[spoke.dimension] : 0;
    const dimension = DIMENSIONS[spoke.dimension];
    const textAnchor = textAnchorFor(spoke.angleDegrees);
    const symbolFirst = textAnchor !== "end";
    return {
      kind: spoke.kind,
      dimension: spoke.dimension,
      hasProfile: profile !== null,
      score,
      vertex: polarToCartesian(
        center.x,
        center.y,
        (score / maxScore) * maxRadius,
        spoke.angleDegrees,
      ),
      label: polarToCartesian(
        center.x,
        center.y,
        labelRadius,
        spoke.angleDegrees,
      ),
      colorVar: `--color-${dimension.token}`,
      labelText: symbolFirst
        ? `${dimension.symbol} ${dimension.label}`
        : `${dimension.label} ${dimension.symbol}`,
      textAnchor,
    };
  });

  const uid = crypto.randomUUID();
  const titleId = `radar-title-${uid}`;
  const descId = `radar-desc-${uid}`;

  const title = buildRadarTitle(gameTitle);
  const description = buildRadarDescription(challenge, reward);
  const summaryRows = buildRadarSummaryRows(challenge, reward);

  const gridHtml = gridRadii
    .map(
      (radius) =>
        `<circle class="radar-grid-circle" cx="${center.x}" cy="${center.y}" r="${radius}" />`,
    )
    .join("");

  const labelHtml = spokes
    .map((spoke) => {
      const active = spoke.kind === initialProfile;
      return `<text class="radar-axis-label${
        active ? " radar-axis-label--active" : ""
      }" data-profile="${spoke.kind}" data-dimension="${spoke.dimension}" x="${
        spoke.label.x
      }" y="${spoke.label.y}" text-anchor="${
        spoke.textAnchor
      }" dominant-baseline="middle" style="fill: var(${spoke.colorVar});">${
        spoke.labelText
      }</text>`;
    })
    .join("");

  const challengeLayerHtml =
    challenge === null
      ? ""
      : polygonLayerHtml(
          "challenge",
          challenge,
          challengePath,
          center,
          dataMaxRadius,
          uid,
          initialProfile === "challenge",
        );
  const rewardLayerHtml =
    reward === null
      ? ""
      : polygonLayerHtml(
          "reward",
          reward,
          rewardPath,
          center,
          dataMaxRadius,
          uid,
          initialProfile === "reward",
        );
  const polygonClipDefs =
    (challenge === null
      ? ""
      : polygonClipHtml(uid, "challenge", challengePath)) +
    (reward === null ? "" : polygonClipHtml(uid, "reward", rewardPath));

  const nodeHtml = spokes
    .filter((spoke) => spoke.hasProfile)
    .map(
      (spoke) =>
        `<circle class="radar-vertex-node${
          spoke.kind === initialProfile ? " radar-vertex-node--active" : ""
        }" cx="${spoke.vertex.x}" cy="${spoke.vertex.y}" r="4" tabindex="0" role="img" data-profile="${spoke.kind}" data-dimension="${spoke.dimension}" data-score="${spoke.score}" data-label="${escapeHtml(
          buildVertexLabel(spoke.kind, spoke.dimension),
        )}" aria-label="${escapeHtml(
          buildVertexAriaLabel(spoke.kind, spoke.dimension, spoke.score),
        )}" style="fill: var(${spoke.colorVar});" />`,
    )
    .join("");

  const tableRowsHtml = summaryRows
    .map(
      (row) =>
        `<tr><th scope="row">${row.label}</th><td>${row.micro}</td><td>${row.mystiko}</td><td>${row.macro}</td></tr>`,
    )
    .join("");

  const hasToggle = showToggle && challenge !== null && reward !== null;

  const toggleHtml = hasToggle
    ? `<div class="radar-toggle-group"><button type="button" class="radar-toggle" role="switch" aria-checked="${
        initialProfile === "reward"
      }" aria-label="Active radar profile"><span class="radar-toggle__track" aria-hidden="true"><span class="radar-toggle__thumb"></span></span></button><span class="radar-toggle__label" data-toggle-label>${
        initialProfile === "challenge" ? "Challenge" : "Reward"
      }</span></div>`
    : "";

  return `<div class="radar-chart${classSuffix}" data-radar-chart data-size="${size}" data-initial-profile="${initialProfile}"><svg class="radar-chart__svg" viewBox="0 0 ${size} ${size}" preserveAspectRatio="xMidYMid meet" role="img" aria-labelledby="${titleId} ${descId}"><title id="${titleId}">${escapeHtml(
    title,
  )}</title><desc id="${descId}">${escapeHtml(
    description,
  )}</desc><defs><filter id="radar-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>${polygonClipDefs}</defs><g class="radar-grid">${gridHtml}</g><g class="radar-labels">${labelHtml}</g><g class="radar-layers" data-radar-layers><g class="radar-polygons" data-radar-polygons>${challengeLayerHtml}${rewardLayerHtml}</g><g class="radar-nodes">${nodeHtml}</g></g></svg><table class="sr-only"><caption>Skill classification scores</caption><thead><tr><th scope="col">Profile</th><th scope="col">Micro</th><th scope="col">Mystiko</th><th scope="col">Macro</th></tr></thead><tbody>${tableRowsHtml}</tbody></table><div class="radar-tooltip" role="tooltip" aria-hidden="true"><span class="radar-tooltip-header"></span><span class="radar-tooltip-value"></span><p class="radar-tooltip-description"></p></div>${toggleHtml}</div>`;
}
